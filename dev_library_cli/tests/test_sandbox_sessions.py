# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Persistent sandbox session lifecycle: start/exec/files/stop/gc."""

from __future__ import annotations

import io
import tarfile
from datetime import UTC, datetime, timedelta

import pytest

import dev_library_cli.sandbox_runner as runner


class FakeContainer:
    _archive_content = b"hello workspace"

    def __init__(self, short_id="c1", exec_result=(0, (b"out", b""))):
        self.short_id = short_id
        self._exec_result = exec_result
        self.execs: list = []
        self.put_archives: list = []
        self.removed = False

    def exec_run(self, cmd, demux=False):
        self.execs.append(cmd)
        return self._exec_result

    def get_archive(self, path):
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w") as archive:
            info = tarfile.TarInfo(name="file.txt")
            data = self._archive_content
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        return iter([payload.getvalue()]), {}

    def put_archive(self, directory, data):
        self.put_archives.append((directory, data.read() if hasattr(data, "read") else data))

    def remove(self, force=False):
        self.removed = True


class FakeVolumes:
    def __init__(self):
        self.created: list[str] = []
        self.removed: list[str] = []

    def create(self, name):
        self.created.append(name)

    def get(self, name):
        volumes = self

        class Volume:
            def remove(self, force=False):
                volumes.removed.append(name)

        return Volume()


class _Containers:
    def __init__(self, client):
        self._client = client

    def run(self, image, command, **kwargs):
        container = FakeContainer()
        self._client.registered[container.short_id] = container
        return container

    def get(self, container_id):
        container = self._client.registered.get(container_id)
        if container is None:
            raise KeyError(container_id)
        return container


class FakeClient:
    def __init__(self, registered: dict[str, FakeContainer] | None = None):
        self.registered = registered if registered is not None else {}
        self.containers = _Containers(self)
        self.volumes = FakeVolumes()


@pytest.fixture()
def no_span(monkeypatch):
    monkeypatch.setattr(runner, "_send_span", lambda *args, **kwargs: None)


def test_session_start_registers_volume_and_entry(tmp_path, monkeypatch, no_span, capsys):
    client = FakeClient()
    monkeypatch.setattr(runner, "_docker_client", lambda: client)

    with pytest.raises(SystemExit) as exc:
        runner.session_start(
            sandbox_id="sb-1",
            image="python:3.12-slim",
            env={"A": "1"},
            network_policy="none",
            mounts=["./d:/d:ro"],
            home=tmp_path,
        )

    assert exc.value.code == 0
    session_id = capsys.readouterr().out.strip()
    assert session_id
    sessions = runner._load_sessions(tmp_path)
    entry = sessions[session_id]
    assert entry["sandbox_id"] == "sb-1"
    assert entry["volume"] == f"observal-ws-{session_id[:12]}"
    assert entry["container_id"]
    assert client.volumes.created == [entry["volume"]]


def test_session_exec_runs_command_and_touches_last_used(tmp_path, monkeypatch, no_span, capsys):
    container = FakeContainer(exec_result=(0, (b"hello", b"")))
    monkeypatch.setattr(runner, "_docker_client", lambda: FakeClient({"c1": container}))
    # Fresh enough to survive the opportunistic GC that runs on every action.
    recent = (datetime.now(UTC) - timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    runner._save_sessions(
        {
            "sess-1": {
                "container_id": "c1",
                "sandbox_id": "sb-1",
                "image": "python:3.12-slim",
                "last_used": recent,
            }
        },
        home=tmp_path,
    )

    with pytest.raises(SystemExit) as exc:
        runner.session_exec("sess-1", "echo hello", home=tmp_path)

    assert exc.value.code == 0
    assert "hello" in capsys.readouterr().out
    assert container.execs == [["sh", "-lc", "echo hello"]]
    updated = runner._load_sessions(tmp_path)["sess-1"]
    assert updated["last_used"] != recent


def test_session_exec_unknown_session_exits_1(tmp_path, monkeypatch, no_span):
    monkeypatch.setattr(runner, "_docker_client", lambda: FakeClient({}))
    with pytest.raises(SystemExit) as exc:
        runner.session_exec("nope", "true", home=tmp_path)
    assert exc.value.code == 1


def test_session_exec_gone_container_deregisters(tmp_path, monkeypatch, no_span):
    monkeypatch.setattr(runner, "_docker_client", lambda: FakeClient({}))
    runner._save_sessions(
        {"sess-2": {"container_id": "gone", "sandbox_id": "sb", "image": "i", "last_used": runner._now_iso()}},
        home=tmp_path,
    )
    with pytest.raises(SystemExit) as exc:
        runner.session_exec("sess-2", "true", home=tmp_path)
    assert exc.value.code == 1
    assert "sess-2" not in runner._load_sessions(tmp_path)


def test_session_stop_removes_container_volume_and_entry(tmp_path, monkeypatch, no_span):
    container = FakeContainer()
    client = FakeClient({"c1": container})
    monkeypatch.setattr(runner, "_docker_client", lambda: client)
    runner._save_sessions(
        {
            "sess-3": {
                "container_id": "c1",
                "sandbox_id": "sb",
                "image": "i",
                "volume": "observal-ws-x",
                "last_used": runner._now_iso(),
            }
        },
        home=tmp_path,
    )

    with pytest.raises(SystemExit) as exc:
        runner.session_stop("sess-3", home=tmp_path)

    assert exc.value.code == 0
    assert container.removed
    assert client.volumes.removed == ["observal-ws-x"]
    assert "sess-3" not in runner._load_sessions(tmp_path)


def test_session_gc_stops_only_idle_sessions(tmp_path, monkeypatch, no_span):
    stale = FakeContainer(short_id="stale")
    fresh = FakeContainer(short_id="fresh")
    client = FakeClient({"stale": stale, "fresh": fresh})
    monkeypatch.setattr(runner, "_docker_client", lambda: client)
    old = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    runner._save_sessions(
        {
            "s-old": {"container_id": "stale", "sandbox_id": "sb", "image": "i", "volume": None, "last_used": old},
            "s-new": {
                "container_id": "fresh",
                "sandbox_id": "sb",
                "image": "i",
                "volume": None,
                "last_used": runner._now_iso(),
            },
        },
        home=tmp_path,
    )

    stopped = runner.session_gc(1800, home=tmp_path)

    assert stopped == ["s-old"]
    assert stale.removed
    assert not fresh.removed
    assert set(runner._load_sessions(tmp_path)) == {"s-new"}


def test_session_files_roundtrip(tmp_path, monkeypatch, no_span, capsys):
    container = FakeContainer()
    monkeypatch.setattr(runner, "_docker_client", lambda: FakeClient({"c1": container}))
    runner._save_sessions(
        {
            "sess-4": {
                "container_id": "c1",
                "sandbox_id": "sb",
                "image": "i",
                "volume": "v",
                "last_used": runner._now_iso(),
            }
        },
        home=tmp_path,
    )

    with pytest.raises(SystemExit) as exc:
        runner.session_files_put("sess-4", "src/main.py", "print('hi')", home=tmp_path)
    assert exc.value.code == 0

    directory, tar_bytes = container.put_archives[0]
    assert directory == "/workspace/src"
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as archive:
        member = archive.getmembers()[0]
        fileobj = archive.extractfile(member)
        assert fileobj is not None
        assert fileobj.read() == b"print('hi')"

    with pytest.raises(SystemExit) as exc:
        runner.session_files_get("sess-4", "src/main.py", home=tmp_path)
    assert exc.value.code == 0
    assert "hello workspace" in capsys.readouterr().out


def test_session_files_put_rejects_unsafe_paths(tmp_path, monkeypatch, no_span):
    container = FakeContainer()
    monkeypatch.setattr(runner, "_docker_client", lambda: FakeClient({"c1": container}))
    runner._save_sessions(
        {
            "sess-5": {
                "container_id": "c1",
                "sandbox_id": "sb",
                "image": "i",
                "volume": None,
                "last_used": runner._now_iso(),
            }
        },
        home=tmp_path,
    )

    with pytest.raises(SystemExit) as exc:
        runner.session_files_put("sess-5", "../../etc/cron/x", "boom", home=tmp_path)
    assert exc.value.code == 2
    assert container.put_archives == []
