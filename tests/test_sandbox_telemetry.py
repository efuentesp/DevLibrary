# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Spool/retry behavior for the CLI sandbox telemetry sender."""

from __future__ import annotations

import json

from dev_library_cli import sandbox_telemetry as st

ENV_KEYS = ("OBSERVAL_SERVER", "OBSERVAL_KEY", "OBSERVAL_HARNESS", "OBSERVAL_AGENT_ID", "OBSERVAL_SESSION_ID")


def _clean_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _event(**overrides) -> dict:
    base = {
        "sandbox_id": "s-1",
        "image": "python:3.12-slim",
        "runtime_type": "docker",
        "command": "pytest -q",
        "exit_code": 0,
        "status": "success",
        "latency_ms": 10,
        "harness": "pi",
        "output": "ok",
        "start_time": "2026-09-06 10:00:00.123",
        "end_time": "2026-09-06 10:00:00.456",
    }
    base.update(overrides)
    return base


def test_send_and_spool_is_silent_noop_when_unauthenticated(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setattr(st, "post_events", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not post")))
    st.send_and_spool([_event()], home=tmp_path)
    assert not st._spool_path(tmp_path).exists()


def test_send_and_spool_spools_on_failure(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setattr(st, "post_events", lambda *a, **k: False)
    st.send_and_spool([_event()], server_url="http://srv", access_token="tok", home=tmp_path)
    spool = st._spool_path(tmp_path)
    assert spool.exists()
    lines = [line for line in spool.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["sandbox_id"] == "s-1"


def test_send_and_spool_flushes_backlog_before_current_event(tmp_path, monkeypatch):
    _clean_env(monkeypatch)
    st._spool_append([_event(sandbox_id="backlog-1"), _event(sandbox_id="backlog-2")], home=tmp_path)

    calls: list[list[dict]] = []

    def fake_post(server_url, access_token, events, **kwargs):
        calls.append(events)
        return True

    monkeypatch.setattr(st, "post_events", fake_post)
    st.send_and_spool([_event(sandbox_id="current")], server_url="http://srv", access_token="tok", home=tmp_path)

    assert [batch[0]["sandbox_id"] for batch in calls] == ["backlog-1", "current"]
    assert not [line for line in st._spool_path(tmp_path).read_text().splitlines() if line.strip()]


def test_flush_spooled_delivers_partial_batches(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "post_events", lambda *a, **k: True)
    st._spool_append([_event(sandbox_id=f"ev-{i}") for i in range(st.FLUSH_BATCH + 10)], home=tmp_path)
    delivered = st.flush_spooled("http://srv", "tok", home=tmp_path)
    assert delivered == st.FLUSH_BATCH
    remaining = [line for line in st._spool_path(tmp_path).read_text().splitlines() if line.strip()]
    assert len(remaining) == 10


def test_flush_spooled_keeps_spool_on_failure(tmp_path, monkeypatch):
    st._spool_append([_event(sandbox_id="ev-1")], home=tmp_path)
    monkeypatch.setattr(st, "post_events", lambda *a, **k: False)
    assert st.flush_spooled("http://srv", "tok", home=tmp_path) == 0
    remaining = [line for line in st._spool_path(tmp_path).read_text().splitlines() if line.strip()]
    assert len(remaining) == 1


def test_flush_spooled_drops_corrupt_lines(tmp_path, monkeypatch):
    path = st._spool_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json}\n" + json.dumps(_event()) + "\n", encoding="utf-8")
    monkeypatch.setattr(st, "post_events", lambda *a, **k: True)
    assert st.flush_spooled("http://srv", "tok", home=tmp_path) == 1
    assert not [line for line in path.read_text().splitlines() if line.strip()]


def test_spool_rotation_caps_line_count(tmp_path):
    total = st.MAX_SPOOL_LINES + 50
    st._spool_append([_event(sandbox_id=f"ev-{i}") for i in range(total)], home=tmp_path)
    lines = [line for line in st._spool_path(tmp_path).read_text().splitlines() if line.strip()]
    assert len(lines) == st.MAX_SPOOL_LINES
    assert json.loads(lines[0])["sandbox_id"] == f"ev-{total - st.MAX_SPOOL_LINES}"


def test_post_events_returns_true_on_2xx(monkeypatch):
    class _Response:
        status_code = 204

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, *args, **kwargs):
            return _Response()

    monkeypatch.setattr("httpx.Client", _Client)
    assert st.post_events("http://srv", "tok", [_event()])


def test_post_events_returns_false_on_transport_error(monkeypatch):
    def _boom():
        raise OSError("network down")

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, *args, **kwargs):
            _boom()

    monkeypatch.setattr("httpx.Client", _Client)
    assert not st.post_events("http://srv", "tok", [_event()])
