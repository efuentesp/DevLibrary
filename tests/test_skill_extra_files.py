# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Multi-file skill contract: extra_files helpers, schemas, version extras, and routes.

Covers the shared observal_shared.skill_files validators (single source of
truth for server and CLI), the pydantic schemas, component version publishing,
and the submit/draft/update persistence in api/routes/skill.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.routes import skill
from models.mcp import ListingStatus
from models.skill import SkillListing, SkillVersion
from observal_shared.skill_files import (
    MAX_EXTRA_FILE_BYTES,
    MAX_EXTRA_FILES,
    check_extra_file_set,
    decoded_size,
    normalize_extra_file_path,
    validate_extra_file_entry,
    validate_extra_files,
)
from schemas.skill import (
    SkillDraftRequest,
    SkillExtraFile,
    SkillListingResponse,
    SkillSubmitRequest,
    SkillUpdateRequest,
)
from services.component_version_extras import SKILL_FIELDS, validate_and_extract
from services.teamspace import PublishTarget

USER_ID = uuid.UUID(int=103)
NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
SKILL_MD = "---\nname: Multi\ndescription: Multi-file skill\n---\nBody\n"

VALID_FILES = [
    {"path": "scripts/validate.py", "content": "print('ok')"},
    {"path": "templates/estimate.md", "content": "# Estimate"},
]


class TestNormalizeExtraFilePath:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("scripts/run.py", "scripts/run.py"),
            ("templates/x.md", "templates/x.md"),
            ("a/./b.md", "a/b.md"),
            ("dir//file.txt", "dir/file.txt"),
            (" templates/x.md ", "templates/x.md"),
            ("a/b/c/d/e/f/g/h/i/j.txt", "a/b/c/d/e/f/g/h/i/j.txt"),
        ],
    )
    def test_accepts_and_normalizes_safe_paths(self, raw, expected):
        assert normalize_extra_file_path(raw) == expected

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "   ",
            "../escape.py",
            "a/../b.md",
            "/absolute.py",
            "a\\b.md",
            "c:/x.md",
            "name:with:colons.md",
            "bad\x01name.md",
            ".git/config",
            ".git/hooks/pre-commit",
            "SKILL.md",
            "skill.md",
            "docs/SKILL.md",
            "a" * 201 + ".md",
            "/".join(["d"] * 11 + ["f.md"]),
            None,
            5,
        ],
    )
    def test_rejects_unsafe_or_malformed_paths(self, bad):
        with pytest.raises(Exception, match="extra file path"):
            normalize_extra_file_path(bad)


class TestDecodedSize:
    def test_utf8_counts_bytes_not_characters(self):
        assert decoded_size("ñ" * 10, "utf-8") == 20

    def test_base64_counts_decoded_bytes(self):
        assert decoded_size("aGVsbG8=", "base64") == 5

    def test_invalid_base64_raises(self):
        with pytest.raises(Exception, match="not valid base64"):
            decoded_size("!!not-base64!!", "base64")


class TestValidateExtraFileEntry:
    def test_normalizes_and_defaults_encoding(self):
        assert validate_extra_file_entry({"path": "./a/./b.md", "content": "x"}) == {
            "path": "a/b.md",
            "content": "x",
            "encoding": "utf-8",
        }

    def test_drops_unknown_keys(self):
        entry = validate_extra_file_entry({"path": "a.md", "content": "x", "bogus": 1})
        assert set(entry) == {"path", "content", "encoding"}

    def test_rejects_unknown_encoding(self):
        with pytest.raises(Exception, match="encoding"):
            validate_extra_file_entry({"path": "a.md", "content": "x", "encoding": "hex"})

    def test_rejects_non_dict_entry(self):
        with pytest.raises(Exception, match="must be an object"):
            validate_extra_file_entry("scripts/a.py")

    def test_rejects_oversized_utf8_entry(self):
        with pytest.raises(Exception, match="exceeds"):
            validate_extra_file_entry({"path": "big.md", "content": "x" * (MAX_EXTRA_FILE_BYTES + 1)})


class TestValidateExtraFiles:
    def test_none_passes_through(self):
        assert validate_extra_files(None) is None

    def test_normalizes_full_list_preserving_order(self):
        result = validate_extra_files(VALID_FILES)
        assert result == [
            {"path": "scripts/validate.py", "content": "print('ok')", "encoding": "utf-8"},
            {"path": "templates/estimate.md", "content": "# Estimate", "encoding": "utf-8"},
        ]

    def test_rejects_non_list(self):
        with pytest.raises(Exception, match="must be a list"):
            validate_extra_files({"path": "a.md"})

    def test_rejects_exact_duplicates(self):
        with pytest.raises(Exception, match="duplicate"):
            validate_extra_files([{"path": "a.md", "content": "1"}, {"path": "a.md", "content": "2"}])

    def test_rejects_case_insensitive_duplicates(self):
        with pytest.raises(Exception, match="duplicate"):
            validate_extra_files([{"path": "A.md", "content": "1"}, {"path": "a.md", "content": "2"}])

    def test_rejects_collision_with_script_slot(self):
        with pytest.raises(Exception, match="collides with the script slot"):
            validate_extra_files(
                [{"path": "scripts/run.sh", "content": "x"}],
                script_filename="run.sh",
            )

    def test_allows_other_scripts_entries(self):
        result = validate_extra_files(
            [{"path": "scripts/other.sh", "content": "x"}],
            script_filename="run.sh",
        )
        assert result[0]["path"] == "scripts/other.sh"

    def test_rejects_too_many_entries(self):
        entries = [{"path": f"f{i}.md", "content": "x"} for i in range(MAX_EXTRA_FILES + 1)]
        with pytest.raises(Exception, match="maximum"):
            validate_extra_files(entries)

    def test_rejects_total_size_over_cap(self):
        entries = [{"path": f"f{i}.md", "content": "x" * 1_800_000} for i in range(5)]
        with pytest.raises(Exception, match="total"):
            validate_extra_files(entries)

    def test_check_extra_file_set_validates_already_normalized_entries(self):
        normalized = validate_extra_files(VALID_FILES)
        check_extra_file_set(normalized, script_filename=None)  # must not raise


class TestSkillSchemas:
    def test_submit_request_accepts_extra_files(self):
        req = SkillSubmitRequest(
            name="multi",
            version="1.0.0",
            description="Multi-file skill",
            owner="alice",
            task_type="general",
            delivery_mode="registry_direct",
            skill_md_content=SKILL_MD,
            extra_files=VALID_FILES,
        )
        assert [f.path for f in req.extra_files] == ["scripts/validate.py", "templates/estimate.md"]
        assert req.extra_files[0].encoding == "utf-8"

    def test_submit_request_normalizes_paths(self):
        req = SkillSubmitRequest(
            name="multi",
            version="1.0.0",
            description="d",
            owner="alice",
            task_type="general",
            extra_files=[{"path": "./a/./b.md", "content": "x"}],
        )
        assert req.extra_files[0].path == "a/b.md"

    @pytest.mark.parametrize(
        "files",
        [
            [{"path": "../escape.py", "content": "x"}],
            [{"path": "SKILL.md", "content": "x"}],
            [{"path": "a.md", "content": "x"}, {"path": "A.md", "content": "y"}],
            [{"path": "big.md", "content": "x" * (MAX_EXTRA_FILE_BYTES + 1)}],
        ],
    )
    def test_submit_request_rejects_contract_violations(self, files):
        with pytest.raises(ValidationError):
            SkillSubmitRequest(
                name="multi",
                version="1.0.0",
                description="d",
                owner="alice",
                task_type="general",
                extra_files=files,
            )

    def test_submit_request_rejects_script_slot_collision(self):
        with pytest.raises(ValidationError, match="script slot"):
            SkillSubmitRequest(
                name="multi",
                version="1.0.0",
                description="d",
                owner="alice",
                task_type="general",
                script_filename="run.sh",
                extra_files=[{"path": "scripts/run.sh", "content": "x"}],
            )

    def test_draft_request_enforces_same_contract(self):
        with pytest.raises(ValidationError):
            SkillDraftRequest(
                name="multi",
                task_type="general",
                extra_files=[{"path": "/abs.py", "content": "x"}],
            )

    def test_update_request_enforces_same_contract(self):
        with pytest.raises(ValidationError):
            SkillUpdateRequest(extra_files=[{"path": "a\\b.py", "content": "x"}])

    def test_listing_response_echoes_extra_files(self):
        listing = SimpleNamespace(
            id=uuid.uuid4(),
            name="multi",
            namespace="alice",
            slug="multi",
            qualified_name="alice/multi",
            version="1.0.0",
            description="d",
            owner="alice",
            team_id=None,
            visibility="public",
            is_private=False,
            task_type="general",
            target_agents=[],
            supported_harnesses=[],
            skill_path="/",
            git_url=None,
            git_ref=None,
            skill_md_content=SKILL_MD,
            delivery_mode="registry_direct",
            script_content=None,
            script_filename=None,
            extra_files=VALID_FILES,
            validated=True,
            slash_command=None,
            status=ListingStatus.pending,
            rejection_reason=None,
            submitted_by=USER_ID,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            download_count=0,
        )
        response = SkillListingResponse.model_validate(listing)
        assert [f["path"] for f in response.model_dump()["extra_files"]] == [
            "scripts/validate.py",
            "templates/estimate.md",
        ]


class TestComponentVersionExtras:
    def test_extra_files_is_an_allowed_skill_field(self):
        assert "extra_files" in SKILL_FIELDS

    def test_publish_extracts_normalized_extra_files(self):
        clean = validate_and_extract(
            "skill",
            {"task_type": "general", "extra_files": [{"path": "./a/./b.md", "content": "x"}]},
        )
        assert clean["extra_files"] == [{"path": "a/b.md", "content": "x", "encoding": "utf-8"}]

    def test_publish_rejects_invalid_extra_files_with_422(self):
        with pytest.raises(HTTPException) as exc:
            validate_and_extract(
                "skill",
                {"task_type": "general", "extra_files": [{"path": "../evil.py", "content": "x"}]},
            )
        assert exc.value.status_code == 422
        assert "extra file path" in str(exc.value.detail)

    def test_publish_still_rejects_unknown_fields(self):
        with pytest.raises(HTTPException) as exc:
            validate_and_extract("skill", {"task_type": "general", "bogus": True})
        assert exc.value.status_code == 422
        assert "Unknown fields" in str(exc.value.detail)


class TestSkillRoutesPersistence:
    @staticmethod
    def _db():
        return SimpleNamespace(
            add=Mock(),
            flush=AsyncMock(),
            refresh=AsyncMock(),
            execute=AsyncMock(),
            scalar=AsyncMock(),
            commit=AsyncMock(),
            rollback=AsyncMock(),
        )

    @staticmethod
    def _user():
        return SimpleNamespace(id=USER_ID, role="user", username="alice", email="alice@example.test")

    @staticmethod
    def _wire(monkeypatch, db):
        next_ids = iter(range(1, 100))
        rows = []

        def add(row):
            rows.append(row)

        async def flush():
            for row in rows:
                if getattr(row, "id", None) is None:
                    row.id = uuid.UUID(int=next(next_ids))
                if row.created_at is None:
                    row.created_at = NOW
                    row.updated_at = NOW
                if isinstance(row, SkillVersion):
                    if row.download_count is None:
                        row.download_count = 0
                    if row.validated is None:
                        row.validated = False
                    # Mirror what db.refresh() would load in a real session.
                    for other in rows:
                        if isinstance(other, SkillListing) and other.latest_version is None:
                            other.latest_version = row

        db.add.side_effect = add
        db.flush.side_effect = flush
        monkeypatch.setattr(
            skill,
            "resolve_publish_target",
            AsyncMock(
                return_value=PublishTarget(
                    namespace="alice",
                    slug="multi",
                    team_id=None,
                    visibility="public",
                    owner="alice",
                    auto_approve=False,
                )
            ),
        )
        monkeypatch.setattr(skill, "identity_exists", AsyncMock(return_value=False))
        monkeypatch.setattr(skill.inbox, "on_publish", AsyncMock(return_value=1))
        monkeypatch.setattr(skill, "commit_or_name_conflict", AsyncMock())
        return rows

    @pytest.mark.asyncio
    async def test_submit_persists_extra_files_on_version(self, monkeypatch):
        db = self._db()
        rows = self._wire(monkeypatch, db)
        request = SkillSubmitRequest(
            name="multi",
            version="1.0.0",
            description="Multi-file skill",
            owner="alice",
            task_type="general",
            delivery_mode="registry_direct",
            skill_md_content=SKILL_MD,
            extra_files=VALID_FILES,
        )

        response = await skill.submit_skill(request, db, self._user())

        version = next(row for row in rows if isinstance(row, SkillVersion))
        assert version.extra_files == [
            {"path": "scripts/validate.py", "content": "print('ok')", "encoding": "utf-8"},
            {"path": "templates/estimate.md", "content": "# Estimate", "encoding": "utf-8"},
        ]
        assert response.extra_files is not None
        assert [f.path for f in response.extra_files] == ["scripts/validate.py", "templates/estimate.md"]

    @pytest.mark.asyncio
    async def test_draft_persists_extra_files_on_version(self, monkeypatch):
        db = self._db()
        rows = self._wire(monkeypatch, db)
        request = SkillDraftRequest(
            name="multi",
            task_type="general",
            delivery_mode="registry_direct",
            skill_md_content=SKILL_MD,
            extra_files=VALID_FILES,
        )

        await skill.save_skill_draft(request, db, self._user())

        version = next(row for row in rows if isinstance(row, SkillVersion))
        assert version.extra_files[0]["path"] == "scripts/validate.py"

    @pytest.mark.asyncio
    async def test_update_draft_replaces_clears_and_preserves(self, monkeypatch):
        db = self._db()
        listing = SkillListing(
            id=uuid.UUID(int=1),
            name="multi",
            namespace="alice",
            slug="multi",
            owner="alice",
            submitted_by=USER_ID,
            co_authors=[],
            is_private=False,
        )
        version = SkillVersion(
            id=uuid.UUID(int=2),
            listing_id=listing.id,
            version="0.1.0",
            description="d",
            status=ListingStatus.draft,
            released_by=USER_ID,
            released_at=datetime.now(UTC),
            supported_harnesses=[],
            target_agents=[],
            validated=True,
            skill_path="/",
            delivery_mode="registry_direct",
            task_type="general",
            extra_files=[{"path": "old.md", "content": "old", "encoding": "utf-8"}],
        )
        listing.latest_version = version
        listing.latest_version_id = version.id
        listing.created_at = NOW
        listing.updated_at = NOW
        version.created_at = NOW
        version.download_count = 0
        monkeypatch.setattr(skill, "resolve_listing", AsyncMock(return_value=listing))
        monkeypatch.setattr(skill, "get_effective_component_permission", Mock(return_value="owner"))
        monkeypatch.setattr(skill, "release_edit_lock", Mock())
        monkeypatch.setattr(skill, "commit_or_name_conflict", AsyncMock())

        replace_req = SkillUpdateRequest(extra_files=[SkillExtraFile(path="new.md", content="new")])
        await skill.update_skill_draft(str(listing.id), replace_req, db, self._user())
        assert version.extra_files == [{"path": "new.md", "content": "new", "encoding": "utf-8"}]

        await skill.update_skill_draft(str(listing.id), SkillUpdateRequest(extra_files=[]), db, self._user())
        assert version.extra_files == []

        version.extra_files = [{"path": "keep.md", "content": "k", "encoding": "utf-8"}]
        await skill.update_skill_draft(str(listing.id), SkillUpdateRequest(description="only"), db, self._user())
        assert version.extra_files == [{"path": "keep.md", "content": "k", "encoding": "utf-8"}]
