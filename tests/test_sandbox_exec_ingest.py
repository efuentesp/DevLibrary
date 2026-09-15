# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Bounds and row mapping for the sandbox execution telemetry ingest."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.routes.ingest import (
    MAX_SANDBOX_EVENTS_PER_BATCH,
    MAX_SANDBOX_OUTPUT_CHARS,
    SandboxExecEvent,
    SandboxExecIngestRequest,
    _sandbox_exec_rows,
)


def _event(**overrides) -> SandboxExecEvent:
    base = {
        "sandbox_id": "s-1",
        "image": "python:3.12-slim",
        "runtime_type": "docker",
        "command": "pytest -q",
        "exit_code": 0,
        "status": "success",
        "latency_ms": 123,
        "output": "ok",
        "start_time": "2026-09-06 10:00:00.123",
        "end_time": "2026-09-06 10:00:01.456",
    }
    base.update(overrides)
    return SandboxExecEvent(**base)


def test_valid_event_roundtrip():
    req = SandboxExecIngestRequest(harness="claude-code", events=[_event()])
    assert req.events[0].sandbox_id == "s-1"
    assert req.harness == "claude-code"


def test_rejects_oversized_batch():
    with pytest.raises(ValidationError):
        SandboxExecIngestRequest(events=[_event()] * (MAX_SANDBOX_EVENTS_PER_BATCH + 1))


def test_rejects_empty_batch():
    with pytest.raises(ValidationError):
        SandboxExecIngestRequest(events=[])


def test_rejects_out_of_range_exit_code():
    with pytest.raises(ValidationError):
        _event(exit_code=300)
    with pytest.raises(ValidationError):
        _event(exit_code=-2)


def test_rejects_unknown_status():
    with pytest.raises(ValidationError):
        _event(status="crash")


def test_rejects_oversized_image():
    with pytest.raises(ValidationError):
        _event(image="a" * 501)


def test_rows_truncate_output_preview():
    event = _event(output="x" * (MAX_SANDBOX_OUTPUT_CHARS * 3))
    rows = _sandbox_exec_rows([event], user_id="user-1", harness="pi")
    assert len(rows[0]["output_preview"]) == MAX_SANDBOX_OUTPUT_CHARS


def test_rows_end_time_defaults_to_start_time():
    event = _event(end_time=None)
    rows = _sandbox_exec_rows([event], user_id="user-1", harness="")
    assert rows[0]["end_time"] == event.start_time


def test_rows_stamp_user_and_harness_and_keep_optional_fields():
    event = _event(agent_id="agent-uuid", session_id="session-uuid", container_id="abc123")
    rows = _sandbox_exec_rows([event], user_id="user-1", harness="kiro")
    row = rows[0]
    assert row["user_id"] == "user-1"
    assert row["harness"] == "kiro"
    assert row["agent_id"] == "agent-uuid"
    assert row["session_id"] == "session-uuid"
    assert row["container_id"] == "abc123"
    assert row["timed_out"] is False
    assert row["oom_killed"] is False
    assert row["event_id"]
