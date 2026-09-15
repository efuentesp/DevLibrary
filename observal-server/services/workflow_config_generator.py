# SPDX-FileCopyrightText: 2026 Edgar F. Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Install config generation for workflow components.

Returns a {"workflows": [{"path", "content"}]} snippet. The CLI resolves
the path relative to the target directory (or the real home for user
scope) and writes the script file.
"""

from __future__ import annotations

from observal_shared.harness_registry import HARNESS_REGISTRY

_FIRST = 0


def generate_workflow_config(
    listing,
    harness: str,
    *,
    scope: str = "project",
    version_override=None,
    local_name: str | None = None,
) -> dict:
    entry = HARNESS_REGISTRY.get(harness)
    if entry is None or "workflows" not in entry.get("capabilities", set()):
        raise ValueError(f"harness {harness!r} does not support workflows")

    version = version_override or getattr(listing, "latest_version", None)
    if version is None:
        raise ValueError("listing has no version to install")

    templates = entry["workflows"]
    template = templates.get(scope) or templates.get("user") or list(templates.values())[_FIRST]
    file_name = local_name or listing.slug
    path = template.format(name=file_name)

    return {
        "workflows": [
            {
                "path": path,
                "content": version.script_content,
            }
        ]
    }
