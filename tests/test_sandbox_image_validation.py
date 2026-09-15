# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Offline coverage for sandbox image reference validation."""

from __future__ import annotations

import httpx
import pytest

import services.sandbox_image_validation as sv

# ── Reference parsing ───────────────────────────────────────────────


def test_parse_normalizes_docker_hub_shorthand():
    assert sv.parse_image_ref("python") == ("registry-1.docker.io", "library/python", "latest")
    assert sv.parse_image_ref("python:3.12-slim") == ("registry-1.docker.io", "library/python", "3.12-slim")
    assert sv.parse_image_ref("docker.io/acme/tool:1.0") == ("registry-1.docker.io", "acme/tool", "1.0")


def test_parse_keeps_explicit_registries_ports_and_digests():
    assert sv.parse_image_ref("ghcr.io/acme/runner:1.0") == ("ghcr.io", "acme/runner", "1.0")
    assert sv.parse_image_ref("localhost:5000/tool") == ("localhost:5000", "tool", "latest")
    assert sv.parse_image_ref("registry.example.com:8443/team/img@sha256:abc") == (
        "registry.example.com:8443",
        "team/img",
        "sha256:abc",
    )


def test_parse_rejects_empty_reference():
    with pytest.raises(ValueError):
        sv.parse_image_ref("")


# ── Registry checks (MockTransport, no network) ─────────────────────


@pytest.fixture(autouse=True)
def _public_everywhere(monkeypatch):
    monkeypatch.setattr(sv, "is_private_url", lambda url: False)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)


async def test_check_follows_token_dance_and_summarizes_index():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/v2/":
            return httpx.Response(
                401,
                headers={
                    "WWW-Authenticate": (
                        'Bearer realm="https://auth.example/token",service="registry.example.com",'
                        'scope="repository:acme/runner:pull"'
                    )
                },
            )
        if request.url.host == "auth.example":
            assert request.url.params["scope"] == "repository:acme/runner:pull"
            assert request.url.params["service"] == "registry.example.com"
            return httpx.Response(200, json={"token": "tok123"})
        if request.url.path == "/v2/acme/runner/manifests/1.0":
            assert request.headers["authorization"] == "Bearer tok123"
            return httpx.Response(
                200,
                headers={"docker-content-digest": "sha256:deadbeef"},
                json={
                    "manifests": [
                        {"platform": {"architecture": "amd64", "os": "linux"}},
                        {"platform": {"architecture": "arm64", "os": "linux"}},
                        {"platform": {"architecture": "amd64", "os": "linux"}},
                    ]
                },
            )
        return httpx.Response(404)

    async with _client(handler) as client:
        result = await sv.check_image_ref("registry.example.com/acme/runner:1.0", client=client)

    assert result["status"] == "valid"
    assert result["registry"] == "registry.example.com"
    assert result["repository"] == "acme/runner"
    assert result["digest"] == "sha256:deadbeef"
    assert result["architectures"] == ["amd64/linux", "arm64/linux"]
    assert calls[0] == "/v2/"


async def test_check_open_registry_single_manifest_sums_sizes():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/":
            return httpx.Response(200)  # open registry: no auth dance
        if request.url.path == "/v2/library/python/manifests/3.12-slim":
            assert "authorization" not in request.headers
            return httpx.Response(
                200,
                json={
                    "config": {"size": 7000},
                    "layers": [{"size": 3_000_000}, {"size": 2_000_000}, {"size": "not-a-number"}],
                },
            )
        return httpx.Response(404)

    async with _client(handler) as client:
        result = await sv.check_image_ref("python:3.12-slim", client=client)

    assert result["status"] == "valid"
    assert result["registry"] == "registry-1.docker.io"
    assert result["size_bytes"] == 5_007_000  # malformed layer coerced to 0
    assert result["architectures"] == []


async def test_check_reports_missing_reference():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/":
            return httpx.Response(200)
        return httpx.Response(404, json={"errors": [{"code": "MANIFEST_UNKNOWN"}]})

    async with _client(handler) as client:
        result = await sv.check_image_ref("ghcr.io/acme/ghost:9.9", client=client)

    assert result["status"] == "missing"
    assert "not found" in result["detail"]


async def test_check_reports_unexpected_registry_status():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/":
            return httpx.Response(200)
        return httpx.Response(503)

    async with _client(handler) as client:
        result = await sv.check_image_ref("ghcr.io/acme/flaky:1.0", client=client)

    assert result["status"] == "error"
    assert "503" in result["detail"]


async def test_check_blocks_private_registries_without_any_request(monkeypatch):
    monkeypatch.setattr(sv, "is_private_url", lambda url: True)

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover — must not run
        raise AssertionError("no HTTP request may leave for a blocked registry")

    async with _client(handler) as client:
        result = await sv.check_image_ref("10.0.0.5:5000/internal/tool:1.0", client=client)

    assert result["status"] == "error"
    assert "not publicly reachable" in result["detail"]
