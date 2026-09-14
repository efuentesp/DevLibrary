# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Shared contract for multi-file skill resources (``extra_files``).

Both sides of the registry use this module so path-safety rules and size caps
have a single source of truth:

- the server validates submit/draft/version payloads (schemas + routes);
- the CLI packages skill directories and writes installed trees.

Each entry is ``{"path": str, "content": str, "encoding": "utf-8" | "base64"}``.
Paths are relative POSIX paths under the skill directory, traversal-free, and
must not collide with ``SKILL.md`` or the legacy ``scripts/<script_filename>``
slot.
"""

from __future__ import annotations

import base64
import binascii
import posixpath
from pathlib import PurePosixPath

MAX_EXTRA_FILES = 100
MAX_EXTRA_FILE_BYTES = 2 * 1024 * 1024  # 2 MB decoded size per file
MAX_EXTRA_TOTAL_BYTES = 8 * 1024 * 1024  # 8 MB decoded size across all files
MAX_EXTRA_PATH_LENGTH = 200
MAX_EXTRA_PATH_DEPTH = 10

VALID_ENCODINGS = ("utf-8", "base64")

#: Top-level directories that never make sense inside a packaged skill and can
#: carry executable side effects (git hooks) when installed.
RESERVED_FIRST_SEGMENTS = frozenset({".git"})

SKILL_MD_FILENAME = "SKILL.md"


class ExtraFileError(ValueError):
    """Raised when an extra_files entry violates the multi-file skill contract."""


def normalize_extra_file_path(path: object) -> str:
    """Validate one extra-file path and return its normalized POSIX form.

    Raises :class:`ExtraFileError` on unsafe or malformed paths.
    """
    if not isinstance(path, str):
        raise ExtraFileError("extra file path must be a string")
    candidate = path.strip()
    if not candidate:
        raise ExtraFileError("extra file path cannot be empty")
    if len(candidate) > MAX_EXTRA_PATH_LENGTH:
        raise ExtraFileError(f"extra file path exceeds {MAX_EXTRA_PATH_LENGTH} characters: {path!r}")
    if "\\" in candidate:
        raise ExtraFileError(f"extra file path must use forward slashes only: {path!r}")
    if ":" in candidate:
        raise ExtraFileError(f"extra file path must not contain ':' (drive letters and URLs are not paths): {path!r}")
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in candidate):
        raise ExtraFileError(f"extra file path must not contain control characters: {path!r}")
    if candidate.startswith("/"):
        raise ExtraFileError(f"extra file path must be relative to the skill directory: {path!r}")

    parts = PurePosixPath(candidate).parts
    if not parts:
        raise ExtraFileError("extra file path cannot be empty")
    if len(parts) > MAX_EXTRA_PATH_DEPTH:
        raise ExtraFileError(f"extra file path exceeds {MAX_EXTRA_PATH_DEPTH} path segments: {path!r}")
    for part in parts:
        if part in (".", ".."):
            raise ExtraFileError(f"extra file path must not traverse directories: {path!r}")
    if parts[0] in RESERVED_FIRST_SEGMENTS:
        raise ExtraFileError(f"extra file path must not start with reserved directory: {path!r}")
    if parts[-1].lower() == SKILL_MD_FILENAME.lower():
        # Harness skill scanners discover skills by rglob("SKILL.md"); a nested
        # copy would be misread as a second skill root on install.
        raise ExtraFileError(
            f"extra file paths must not end in {SKILL_MD_FILENAME}: harness scanners treat it as a skill root"
        )

    normalized = posixpath.normpath(candidate)
    if normalized in (".", "..") or normalized.startswith(("../", "/")):
        # Defense in depth: PurePosixPath already rejected traversal, keep the
        # invariant explicit for future edits of the rules above.
        raise ExtraFileError(f"extra file path resolves outside the skill directory: {path!r}")
    return normalized


def decoded_size(content: str, encoding: str) -> int:
    """Return the decoded byte size of one entry's content."""
    if not isinstance(content, str):
        raise ExtraFileError("extra file content must be a string")
    if encoding == "base64":
        try:
            return len(base64.b64decode(content, validate=True))
        except (binascii.Error, ValueError) as exc:
            raise ExtraFileError("extra file content is not valid base64") from exc
    return len(content.encode("utf-8"))


def validate_extra_file_entry(entry: object) -> dict:
    """Validate one raw extra-file entry (dict) and return it normalized.

    The normalized entry only carries ``path`` (normalized), ``content`` and
    ``encoding`` keys, dropping anything else the caller sent.
    """
    if not isinstance(entry, dict):
        raise ExtraFileError(f"extra file entry must be an object, got {type(entry).__name__}")
    path = normalize_extra_file_path(entry.get("path"))
    encoding = entry.get("encoding") or "utf-8"
    if encoding not in VALID_ENCODINGS:
        raise ExtraFileError(f"extra file encoding must be one of {VALID_ENCODINGS}, got {encoding!r}")
    content = entry.get("content")
    if not isinstance(content, str):
        raise ExtraFileError(f"extra file content must be a string for {path!r}")
    size = decoded_size(content, encoding)
    if size > MAX_EXTRA_FILE_BYTES:
        raise ExtraFileError(f"extra file {path!r} exceeds {MAX_EXTRA_FILE_BYTES} decoded bytes ({size} bytes)")
    return {"path": path, "content": content, "encoding": encoding}


def validate_extra_files(entries: object, *, script_filename: str | None = None) -> list[dict] | None:
    """Validate a complete extra_files payload and return the normalized list.

    ``None`` passes through as ``None`` (field absent). Raises
    :class:`ExtraFileError` on any contract violation: unsafe paths, duplicates
    (compared case-insensitively for portable installs), collisions with the
    ``scripts/<script_filename>`` legacy slot, or count/size caps.
    """
    if entries is None:
        return None
    if not isinstance(entries, list):
        raise ExtraFileError("extra_files must be a list")

    normalized = [validate_extra_file_entry(entry) for entry in entries]
    check_extra_file_set(normalized, script_filename=script_filename)
    return normalized


def check_extra_file_set(normalized: list[dict], *, script_filename: str | None = None) -> None:
    """Set-level checks over already-normalized entries.

    Entry-level validation (path safety, encoding, per-file size) must have
    run; this enforces the cross-entry contract: count cap, total size cap,
    path uniqueness, and collision with the legacy script slot.
    """
    if len(normalized) > MAX_EXTRA_FILES:
        raise ExtraFileError(f"extra_files exceeds the maximum of {MAX_EXTRA_FILES} entries")

    seen: set[str] = set()
    for entry in normalized:
        lowered = entry["path"].lower()
        if lowered in seen:
            raise ExtraFileError(f"duplicate extra file path (paths compare case-insensitively): {entry['path']!r}")
        seen.add(lowered)

    if script_filename:
        reserved = f"scripts/{script_filename}".lower()
        for entry in normalized:
            if entry["path"].lower() == reserved:
                raise ExtraFileError(
                    f"extra file path {entry['path']!r} collides with the script slot; "
                    "use a different path or drop --script"
                )

    total = sum(decoded_size(entry["content"], entry["encoding"]) for entry in normalized)
    if total > MAX_EXTRA_TOTAL_BYTES:
        raise ExtraFileError(
            f"extra_files total {total} decoded bytes exceeds the maximum of {MAX_EXTRA_TOTAL_BYTES} bytes"
        )
