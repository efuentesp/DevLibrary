# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Validate sandbox image references against their OCI registries.

Runs as an arq job after a sandbox version is approved: confirms the image
exists, captures digest/size/architectures, and stamps ``validated_at`` so
the review UI shows real supply-chain state instead of trusting the ref.

Uses the standard OCI distribution auth dance (anonymous pull tokens), goes
through the SSRF guard, and never raises — every outcome is a result dict.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from loguru import logger as optic

from services.ssrf_guard import is_private_url

DEFAULT_REGISTRY = "registry-1.docker.io"
REQUEST_TIMEOUT_S = 15.0

MANIFEST_ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)

_WWW_AUTH_RE = re.compile(
    r'Bearer\s+realm="(?P<realm>[^"]+)"(?:\s*,\s*service="(?P<service>[^"]+)")?(?:\s*,\s*scope="(?P<scope>[^"]+)")?'
)


def parse_image_ref(ref: str) -> tuple[str, str, str]:
    """Split an image reference into (registry_host, repository, reference).

    Docker Hub shorthand is normalized: ``python`` → ``registry-1.docker.io``
    + ``library/python``; a missing tag defaults to ``latest``.
    """
    ref = ref.strip().rstrip("/")
    if not ref:
        raise ValueError("empty image reference")

    digest = ""
    if "@" in ref:
        ref, digest = ref.rsplit("@", 1)

    registry = ""
    rest = ref
    first, _, remainder = ref.partition("/")
    if remainder and ("." in first or ":" in first or first == "localhost"):
        registry, rest = first, remainder
    if registry == "docker.io":
        registry = DEFAULT_REGISTRY

    tag = "latest"
    if not digest and ":" in rest.rsplit("/", 1)[-1]:
        rest, tag = rest.rsplit(":", 1)

    if not registry:
        registry = DEFAULT_REGISTRY
        if "/" not in rest:
            rest = f"library/{rest}"
    if digest:
        tag = digest
    return registry, rest, tag


def _result(status: str, registry: str, repository: str, reference: str, **extra) -> dict:
    return {
        "status": status,
        "registry": registry,
        "repository": repository,
        "reference": reference,
        "checked_at": datetime.now(UTC).isoformat(),
        **extra,
    }


def _int_or(value, default: int = 0) -> int:
    """Best-effort coercion for externally sourced manifest numbers."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _summarize_manifest(payload: dict, digest_header: str | None) -> dict:
    """Extract architectures and total layer size from a manifest response."""
    architectures: list[str] = []
    size_bytes = 0
    if isinstance(payload.get("manifests"), list):
        for entry in payload["manifests"]:
            platform = entry.get("platform") or {}
            arch = platform.get("architecture")
            operating_system = platform.get("os")
            label = f"{arch}/{operating_system}" if arch and operating_system else arch
            if label and label not in architectures:
                architectures.append(label)
    elif isinstance(payload.get("layers"), list):
        size_bytes = sum(_int_or(layer.get("size")) for layer in payload["layers"])
        config = payload.get("config") or {}
        size_bytes += _int_or(config.get("size"))
    return {"architectures": architectures, "size_bytes": size_bytes, "digest": digest_header}


async def _anonymous_token(client, base_url: str, repository: str) -> str | None:
    """Follow the WWW-Authenticate Bearer dance for an anonymous pull token."""
    probe = await client.get(f"{base_url}/v2/")
    www_authenticate = probe.headers.get("www-authenticate", "")
    if probe.status_code != 401 or not www_authenticate.lower().startswith("bearer"):
        return None
    match = _WWW_AUTH_RE.search(www_authenticate)
    if match is None:
        return None
    params = {"scope": f"repository:{repository}:pull"}
    if match.group("service"):
        params["service"] = match.group("service")
    try:
        token_response = await client.get(match.group("realm"), params=params)
        if token_response.status_code != 200:
            return None
        data = token_response.json()
        token = data.get("token") or data.get("access_token")
        return str(token) if token else None
    except Exception as exc:
        optic.debug("anonymous registry token fetch failed: {}", exc)
        return None


async def check_image_ref(ref: str, *, client=None) -> dict:
    """Probe the registry for one image ref; never raises.

    ``client`` accepts an injected httpx.AsyncClient (tests use MockTransport).
    """
    import httpx

    try:
        registry, repository, reference = parse_image_ref(ref)
    except ValueError as exc:
        return _result("error", "", "", "", detail=str(exc))

    base_url = f"https://{registry}"
    if is_private_url(base_url):
        return _result("error", registry, repository, reference, detail="registry host is not publicly reachable")

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S, follow_redirects=True)
    try:
        try:
            token = await _anonymous_token(client, base_url, repository)
            headers = {"Accept": MANIFEST_ACCEPT}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            response = await client.get(f"{base_url}/v2/{repository}/manifests/{reference}", headers=headers)
        except httpx.HTTPError as exc:
            optic.warning("sandbox image check transport error for {}: {}", ref, exc)
            return _result("error", registry, repository, reference, detail=f"registry unreachable: {exc}")

        if response.status_code == 200:
            summary = _summarize_manifest(response.json(), response.headers.get("docker-content-digest"))
            return _result("valid", registry, repository, reference, **summary)
        if response.status_code == 404:
            return _result("missing", registry, repository, reference, detail="image reference not found in registry")
        return _result(
            "error", registry, repository, reference, detail=f"registry returned HTTP {response.status_code}"
        )
    finally:
        if owns_client:
            await client.aclose()
