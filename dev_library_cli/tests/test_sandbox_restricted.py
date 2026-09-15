# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Restricted network policy: allowlist proxy + runner wiring."""

from __future__ import annotations

import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import dev_library_cli.sandbox_runner as runner
from dev_library_cli.sandbox_proxy import RestrictedProxy, host_allowed

# ── Allowlist matching ──────────────────────────────────────────────


def test_host_allowed_matches_exact_subdomain_and_rejects_lookalikes():
    assert host_allowed("pypi.org", ["pypi.org"])
    assert host_allowed("www.pypi.org", ["pypi.org"])
    assert host_allowed("FILES.Pythonhosted.org.", ["pythonhosted.org"])
    assert not host_allowed("notpypi.org", ["pypi.org"])
    assert not host_allowed("pypi.org.evil.com", ["pypi.org"])
    assert not host_allowed("pypi.org", [])
    assert not host_allowed("pypi.org", [""])


# ── Proxy behavior (offline: local upstreams only) ──────────────────


def _start_echo_server() -> tuple[int, socket.socket]:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    return port, listener


def _read_http_response(sock: socket.socket) -> bytes:
    sock.settimeout(5)
    data = b""
    while b"\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def test_proxy_connect_allowed_tunnels_to_upstream():
    upstream_port, listener = _start_echo_server()

    def echo():
        conn, _ = listener.accept()
        conn.sendall(b"echo:")
        while chunk := conn.recv(4096):
            conn.sendall(chunk)
        conn.close()

    server = threading.Thread(target=echo, daemon=True)
    server.start()

    with RestrictedProxy(["localhost"]) as proxy:
        client = socket.create_connection(("127.0.0.1", proxy.port), timeout=5)
        client.sendall(f"CONNECT localhost:{upstream_port} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
        response = _read_http_response(client)
        assert b" 200 " in response
        client.sendall(b"ping")
        client.settimeout(5)
        echoed = b""
        while b"ping" not in echoed:
            chunk = client.recv(4096)
            if not chunk:
                break
            echoed += chunk
        assert echoed.startswith(b"echo:")
        assert b"ping" in echoed
        client.close()

    listener.close()
    server.join(timeout=5)


def test_proxy_connect_denied_returns_403():
    with RestrictedProxy(["allowed.example"]) as proxy:
        client = socket.create_connection(("127.0.0.1", proxy.port), timeout=5)
        client.sendall(b"CONNECT evil.example:443 HTTP/1.1\r\nHost: evil.example\r\n\r\n")
        response = _read_http_response(client)
        assert b" 403 " in response
        client.close()


def test_proxy_absolute_get_forwards_to_allowed_upstream():
    class Upstream(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"upstream-ok"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    upstream = HTTPServer(("127.0.0.1", 0), Upstream)
    upstream_port = upstream.server_address[1]
    threading.Thread(target=upstream.serve_forever, daemon=True).start()

    with RestrictedProxy(["localhost"]) as proxy:
        client = socket.create_connection(("127.0.0.1", proxy.port), timeout=5)
        client.sendall(f"GET http://localhost:{upstream_port}/path HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
        response = _read_http_response(client)
        assert b" 200 " in response
        sock = client
        sock.settimeout(5)
        while b"upstream-ok" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        assert b"upstream-ok" in response
        client.close()

    upstream.shutdown()
    upstream.server_close()


def test_proxy_absolute_get_denied_returns_403():
    with RestrictedProxy(["allowed.example"]) as proxy:
        client = socket.create_connection(("127.0.0.1", proxy.port), timeout=5)
        client.sendall(b"GET http://evil.example/ HTTP/1.1\r\nHost: evil.example\r\n\r\n")
        response = _read_http_response(client)
        assert b" 403 " in response
        client.close()


# ── Runner wiring (fake docker) ─────────────────────────────────────


class FakeNetwork:
    def __init__(self, name: str, internal: bool = False):
        self.name = name
        self.internal = internal
        self.removed = False

    def remove(self):
        self.removed = True


class FakeNetworks:
    def __init__(self):
        self.created: list[FakeNetwork] = []

    def create(self, name, driver=None, internal=False):
        network = FakeNetwork(name, internal=internal)
        self.created.append(network)
        return network

    def get(self, name):
        for network in self.created:
            if network.name == name and not network.removed:
                return network
        raise KeyError(name)


class EphemeralContainer:
    short_id = "c9"
    attrs = {"State": {"Running": False, "OOMKilled": False}}

    def wait(self, timeout=None):
        return {"StatusCode": 0}

    def logs(self, stdout=True, stderr=True):
        return b"done"

    def reload(self):
        pass

    def remove(self, force=False):
        pass


class EphemeralClient:
    def __init__(self):
        self.networks = FakeNetworks()
        self.run_kwargs: dict | None = None

        client = self

        class Containers:
            @staticmethod
            def run(**kwargs):
                client.run_kwargs = kwargs
                return EphemeralContainer()

        self.containers = Containers()


@pytest.fixture()
def no_span(monkeypatch):
    monkeypatch.setattr(runner, "_send_span", lambda *args, **kwargs: None)


def _inject_docker(monkeypatch, client):
    """Point `import docker` at a fake module, immune to a broken/absent SDK."""
    import types

    fake = types.ModuleType("docker")
    fake.from_env = lambda: client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "docker", fake)


def test_docker_run_restricted_uses_proxy_and_dedicated_network(monkeypatch, no_span, capsys):
    client = EphemeralClient()
    _inject_docker(monkeypatch, client)

    with pytest.raises(SystemExit) as exc:
        runner._docker_run(
            "sb-r",
            "python:3.12-slim",
            "curl https://pypi.org",
            30,
            {"TOOL": "1"},
            "restricted",
            {},
            None,
            {"egress_allowlist": ["pypi.org"]},
        )

    assert exc.value.code == 0
    assert "done" in capsys.readouterr().out
    kwargs = client.run_kwargs
    assert kwargs is not None
    assert kwargs["network"].startswith("observal-sbx-")
    assert kwargs["extra_hosts"] == {"host.docker.internal": "host-gateway"}
    assert kwargs["environment"]["HTTP_PROXY"].startswith("http://host.docker.internal:")
    assert kwargs["environment"]["HTTPS_PROXY"] == kwargs["environment"]["HTTP_PROXY"]
    assert kwargs["environment"]["NO_PROXY"] == "localhost,127.0.0.1"
    assert kwargs["environment"]["TOOL"] == "1"
    assert client.networks.created[0].removed  # cleaned up in finally


def test_docker_run_restricted_without_allowlist_is_fully_isolated(monkeypatch, no_span):
    client = EphemeralClient()
    _inject_docker(monkeypatch, client)

    with pytest.raises(SystemExit):
        runner._docker_run("sb-r", "python:3.12-slim", "true", 30, None, "restricted", {}, None, {})

    assert client.run_kwargs is not None
    assert client.run_kwargs["network_mode"] == "none"
    assert client.networks.created == []


def test_session_start_restricted_uses_internal_network(tmp_path, monkeypatch, no_span, capsys):
    from dev_library_cli.tests.test_sandbox_sessions import FakeClient

    class NetworkedFakeClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.networks = FakeNetworks()

    client = NetworkedFakeClient()
    monkeypatch.setattr(runner, "_docker_client", lambda: client)

    with pytest.raises(SystemExit) as exc:
        runner.session_start(
            sandbox_id="sb-r",
            image="python:3.12-slim",
            network_policy="restricted",
            home=tmp_path,
        )

    assert exc.value.code == 0
    session_id = capsys.readouterr().out.strip()
    sessions = runner._load_sessions(tmp_path)
    network = sessions[session_id]["network"]
    assert network and network.startswith("observal-sbx-")
    created = client.networks.created[0]
    assert created.internal is True
    assert not created.removed  # alive for the session lifetime

    with pytest.raises(SystemExit):
        runner.session_stop(session_id, home=tmp_path)
    assert client.networks.created[0].removed  # removed with the session
