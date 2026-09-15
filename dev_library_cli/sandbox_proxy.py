# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Restricted-egress proxy for sandbox executions.

When a sandbox declares ``network_policy: "restricted"``, the runner starts
one of these proxies on an ephemeral loopback port and points the container's
HTTP(S)_PROXY at it (``host.docker.internal``). Only hosts on the sandbox's
``runtime_config.egress_allowlist`` are reachable; everything else is
refused before any connection leaves the host.

Stdlib-only and offline-testable: CONNECT tunneling plus absolute-URI HTTP
forwarding, one worker thread per client connection.
"""

from __future__ import annotations

import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def host_allowed(host: str, allowlist: list[str]) -> bool:
    """Exact or dot-suffix match, e.g. allowlist ["pypi.org"] matches
    ``pypi.org`` and ``files.pythonhosted.org.pypi.org``? No — suffix match is
    segment-aligned: ``pypi.org`` matches ``pypi.org`` and ``www.pypi.org``,
    never ``notpypi.org``."""
    host = host.lower().rstrip(".")
    for allowed in allowlist:
        allowed = str(allowed).lower().rstrip(".")
        if not allowed:
            continue
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


class _ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass  # silence per-request logging; the runner owns stderr

    @property
    def allowlist(self) -> list[str]:
        return self.server.allowlist  # type: ignore[attr-defined]

    def _refuse(self, host: str) -> None:
        self.send_response(403)
        self.send_header("Content-Length", "0")
        self.end_headers()
        self.close_connection = True

    def do_CONNECT(self) -> None:
        host, _, port = self.path.partition(":")
        if not host_allowed(host, self.allowlist):
            self._refuse(host)
            return
        try:
            upstream = socket.create_connection((host, int(port or 443)), timeout=10)
        except OSError:
            self.send_response(502)
            self.send_header("Content-Length", "0")
            self.end_headers()
            self.close_connection = True
            return

        self.send_response(200, "Connection Established")
        self.end_headers()

        client = self.connection
        client.settimeout(None)
        upstream.settimeout(None)
        self._pump(client, upstream)

    def do_GET(self) -> None:
        self._forward_absolute()

    def do_HEAD(self) -> None:
        self._forward_absolute()

    def do_POST(self) -> None:
        self._forward_absolute()

    def _forward_absolute(self) -> None:
        """Forward proxy-style absolute-URI requests (plain HTTP)."""
        from urllib.parse import urlsplit

        target = urlsplit(self.path)
        host = target.hostname or ""
        port = target.port or 80
        if not host or not host_allowed(host, self.allowlist):
            self._refuse(host)
            return
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError:
            self.send_response(502)
            self.send_header("Content-Length", "0")
            self.end_headers()
            self.close_connection = True
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length > 0 else b""
        request_line = f"{self.command} {target.path or '/'}{f'?{target.query}' if target.query else ''} HTTP/1.1\r\n"
        headers = "".join(
            f"{key}: {value}\r\n" for key, value in self.headers.items() if key.lower() not in {"proxy-connection", "connection"}
        )
        upstream.sendall((request_line + headers + "\r\n").encode() + body)

        client = self.connection
        client.settimeout(None)
        upstream.settimeout(None)
        self._pump(client, upstream)

    @staticmethod
    def _pump(client: socket.socket, upstream: socket.socket) -> None:
        """Bidirectional byte pump until either side closes."""

        def relay(source: socket.socket, destination: socket.socket) -> None:
            try:
                while chunk := source.recv(65536):
                    destination.sendall(chunk)
            except OSError:
                pass
            finally:
                try:
                    destination.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        threads = [
            threading.Thread(target=relay, args=(client, upstream), daemon=True),
            threading.Thread(target=relay, args=(upstream, client), daemon=True),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()


class RestrictedProxy:
    """Loopback HTTP(S) proxy enforcing a host allowlist."""

    def __init__(self, allowlist: list[str]):
        self._allowlist = allowlist
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        if self._server is None:
            raise RuntimeError("proxy is not running")
        return self._server.server_address[1]

    def start(self) -> RestrictedProxy:
        handler = _ProxyHandler
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        server.allowlist = self._allowlist  # type: ignore[attr-defined]
        server.daemon_threads = True
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> RestrictedProxy:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
