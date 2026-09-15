# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Best-effort sandbox execution telemetry delivery.

``observal-sandbox-run`` emits one event per execution. This module POSTs
events to ``/api/v1/ingest/sandbox-exec``; on any failure it spools them to
``~/.observal/sandbox_spans.jsonl`` (bounded, newest kept) and retries the
spool on the next execution.

Contract: never raises, never writes to stdout/stderr — the runner's output
belongs to the sandbox caller.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

MAX_SPOOL_LINES = 2000
MAX_SPOOL_BYTES = 2 * 1024 * 1024
FLUSH_BATCH = 50
POST_TIMEOUT_S = 2.5


def _spool_path(home: Path | None = None) -> Path:
    base = home if home is not None else Path.home()
    return base / ".observal" / "sandbox_spans.jsonl"


def post_events(
    server_url: str,
    access_token: str,
    events: list[dict],
    *,
    harness: str = "",
    timeout: float = POST_TIMEOUT_S,
) -> bool:
    """POST one batch; True on any 2xx. Auth failures also return False so the
    caller spools for retry (the 30-day api_key path survives; a stale 1-hour
    access_token is retried after the next login refreshes it)."""
    import httpx

    url = f"{server_url.rstrip('/')}/api/v1/ingest/sandbox-exec"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                url,
                json={"harness": harness, "events": events},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return 200 <= response.status_code < 300
    except Exception:
        return False


def _rewrite_spool(lines: list[str], home: Path | None) -> None:
    """Write spool lines atomically, bounded by count and bytes (newest kept)."""
    while lines and (len(lines) > MAX_SPOOL_LINES or len("\n".join(lines).encode()) > MAX_SPOOL_BYTES):
        lines = lines[1:]
    path = _spool_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".jsonl.tmp")
    temporary.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    temporary.replace(path)


def _spool_append(events: list[dict], home: Path | None = None) -> None:
    path = _spool_path(home)
    existing: list[str] = []
    if path.exists():
        try:
            existing = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except OSError:
            existing = []
    _rewrite_spool(existing + [json.dumps(event) for event in events], home)


def flush_spooled(server_url: str, access_token: str, *, home: Path | None = None) -> int:
    """Retry previously spooled events; returns how many were delivered.

    Delivers at most FLUSH_BATCH per call so a recovered server drains
    gradually across executions instead of blocking one run. Corrupt spool
    lines are dropped at rewrite time.
    """
    path = _spool_path(home)
    if not path.exists():
        return 0
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return 0
    if not lines:
        return 0

    batch = lines[:FLUSH_BATCH]
    events: list[dict] = []
    for line in batch:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not events:
        _rewrite_spool(lines[len(batch) :], home)
        return 0

    harness = str(events[0].get("harness", "") or "")
    if not post_events(server_url, access_token, events, harness=harness):
        return 0

    _rewrite_spool(lines[len(batch) :], home)
    return len(events)


def send_and_spool(
    events: list[dict],
    *,
    server_url: str | None = None,
    access_token: str | None = None,
    home: Path | None = None,
) -> None:
    """Drain any spooled backlog, then deliver ``events`` (or spool them).

    Resolution order mirrors the runner: explicit args, then OBSERVAL_SERVER /
    OBSERVAL_KEY environment, then ~/.observal/config.json (api_key first).
    Not-logged-in is a silent no-op: telemetry never blocks execution.
    """
    if not events:
        return
    if not server_url or not access_token:
        try:
            from dev_library_cli.sessions.base import load_config

            cfg = load_config(home) or {}
        except Exception:
            cfg = {}
        server_url = server_url or os.environ.get("OBSERVAL_SERVER", "") or cfg.get("server_url", "")
        access_token = access_token or os.environ.get("OBSERVAL_KEY", "") or cfg.get("access_token", "")
    if not server_url or not access_token:
        return

    flush_spooled(server_url, access_token, home=home)

    harness = os.environ.get("OBSERVAL_HARNESS", "")
    if not post_events(server_url, access_token, events, harness=harness):
        _spool_append(events, home=home)
