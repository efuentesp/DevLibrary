# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Package local skill directories and extra files into registry extra_files payloads.

Reads raw files, detects text vs binary content (UTF-8 decode probe, base64
fallback), and validates every entry through the shared contract in
``observal_shared.skill_files`` so CLI-side errors match server-side rejections
before the request leaves the machine.
"""

from __future__ import annotations

import base64
from pathlib import Path

from observal_cli.errors import ErrorCategory, fail
from observal_shared.skill_files import ExtraFileError, validate_extra_files

SKILL_MD = "SKILL.md"

#: Directory names never packaged from --from-dir bundles.
IGNORED_DIRS = frozenset({".git", "__pycache__", ".pytest_cache", ".idea", ".vscode", "node_modules", ".venv", "venv"})

#: File names never packaged from --from-dir bundles.
IGNORED_FILES = frozenset({".DS_Store", "Thumbs.db"})


def entry_from_bytes(data: bytes, dest: str) -> dict:
    """Encode raw file bytes as one registry extra-file entry."""
    try:
        return {"path": dest, "content": data.decode("utf-8"), "encoding": "utf-8"}
    except UnicodeDecodeError:
        return {"path": dest, "content": base64.b64encode(data).decode("ascii"), "encoding": "base64"}


def parse_extra_file_spec(spec: str, skill_md_path: Path | None) -> tuple[Path, str]:
    """Parse one --extra-file value into (source path, destination path).

    Two forms are accepted:

    - ``path``: the file must live under the SKILL.md directory; its
      destination is its path relative to that directory.
    - ``dest=path``: explicit destination for files living anywhere else.
    """
    spec = spec.strip()
    if "=" in spec:
        dest, _, raw_src = spec.partition("=")
        dest = dest.strip().replace("\\", "/")
        raw_src = raw_src.strip()
        if not dest or not raw_src:
            fail(
                ErrorCategory.VALIDATION,
                "Invalid --extra-file value.",
                operation="Submit skill",
                resource=spec,
                remediation="Use 'destination=path/to/file' with both sides non-empty.",
            )
        return Path(raw_src), dest

    src = Path(spec)
    if skill_md_path is not None:
        base = skill_md_path.parent.resolve()
        try:
            rel = src.resolve().relative_to(base)
        except ValueError:
            rel = None
        if rel is not None:
            return src, rel.as_posix()
    fail(
        ErrorCategory.VALIDATION,
        "The extra file is outside the skill directory.",
        operation="Submit skill",
        resource=spec,
        remediation="Move the file under the SKILL.md directory, or use the 'destination=path' form.",
    )


def read_extra_entry(src: Path, dest: str) -> dict:
    """Read one file from disk and return its extra-file entry."""
    if not src.is_file():
        fail(
            ErrorCategory.NOT_FOUND,
            "The extra file was not found.",
            operation="Submit skill",
            resource=str(src),
            remediation="Provide an existing file and retry.",
        )
    return entry_from_bytes(src.read_bytes(), dest)


def _validated(entries: list[dict]) -> list[dict]:
    """Run the shared contract, mapping violations to the CLI error format."""
    try:
        return validate_extra_files(entries) or []
    except ExtraFileError as exc:
        fail(
            ErrorCategory.VALIDATION,
            f"Extra files rejected: {exc}",
            operation="Submit skill",
            resource="extra files",
            remediation="Fix the reported file (path or size) and retry.",
        )


def pack_extra_files(
    specs: list[str],
    skill_md_path: Path | None,
    base_entries: list[dict] | None = None,
) -> list[dict]:
    """Package --extra-file specs, merged with any pre-collected entries."""
    entries = list(base_entries or [])
    for spec in specs:
        src, dest = parse_extra_file_spec(spec, skill_md_path)
        entries.append(read_extra_entry(src, dest))
    return _validated(entries)


def pack_skill_dir(dir_path: Path) -> tuple[str, list[dict]]:
    """Collect SKILL.md content and every packable resource from a skill directory.

    Returns ``(skill_md_content, extra_files_entries)``. Ignores VCS/cache
    noise (IGNORED_DIRS, IGNORED_FILES); everything else ships.
    """
    if not dir_path.is_dir():
        fail(
            ErrorCategory.NOT_FOUND,
            "The skill directory was not found.",
            operation="Submit skill",
            resource=str(dir_path),
            remediation="Provide an existing directory containing SKILL.md and retry.",
        )
    skill_md_path = dir_path / SKILL_MD
    if not skill_md_path.is_file():
        fail(
            ErrorCategory.VALIDATION,
            "The directory has no SKILL.md at its root.",
            operation="Submit skill",
            resource=str(skill_md_path),
            remediation="Point --from-dir at a directory whose root contains SKILL.md.",
        )
    content = skill_md_path.read_text(encoding="utf-8")

    entries: list[dict] = []
    for path in sorted(dir_path.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(dir_path)
        if any(segment in IGNORED_DIRS for segment in rel.parts[:-1]):
            continue
        if path.name in IGNORED_FILES:
            continue
        if len(rel.parts) == 1 and rel.parts[0] == SKILL_MD:
            continue
        entries.append(entry_from_bytes(path.read_bytes(), rel.as_posix()))
    return content, _validated(entries)
