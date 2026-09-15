# SPDX-FileCopyrightText: 2026 Edgar F. Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Workflow component routes: submit, list, get, install, and validation."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.deps import get_current_user, get_db, get_registry_user
from api.routes import workflow as workflow_routes
from models.mcp import ListingStatus
from models.user import UserRole
from models.workflow import WorkflowListing, WorkflowVersion
from services.workflow_config_generator import generate_workflow_config

USER_ID = uuid.uuid4()
LISTING_ID = uuid.uuid4()
TEAM_ID = uuid.uuid4()

SCRIPT = (
    "// sizing workflow\n"
    "const rounds = args.maxRounds ?? 3;\n"
    "const result = agent('counter', 'count the requirements', {skills: ['requirements-refiner']});\n"
    "return {status: 'done', rounds};\n"
)


def _user(*, user_id=USER_ID, role=UserRole.user, username="alice", email="alice@example.test"):
    return SimpleNamespace(id=user_id, role=role, username=username, email=email)


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


def _result(value=None, *, rows=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    result.scalar.return_value = value
    result.first.return_value = value
    result.all.return_value = list(rows or [])
    result.scalars.return_value.all.return_value = list(rows if rows is not None else ([value] if value else []))
    result.scalars.return_value.first.return_value = value
    return result


def _version(
    *,
    status=ListingStatus.approved,
    script=SCRIPT,
    version="1.0.0",
    description="Deterministic COSMIC sizing",
    download_count=0,
):
    ver = WorkflowVersion(
        id=uuid.uuid4(),
        listing_id=LISTING_ID,
        version=version,
        description=description,
        status=status,
        download_count=download_count,
        released_by=USER_ID,
        released_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        supported_harnesses=["pi"],
        script_content=script,
        validated=True,
        target_agents=[],
    )
    return ver


def _listing(*, status=ListingStatus.approved, version=None, name="Cosmic Sizing", slug="cosmic-sizing"):
    listing = WorkflowListing(
        id=LISTING_ID,
        name=name,
        namespace="alice",
        slug=slug,
        owner="alice",
        submitted_by=USER_ID,
        co_authors=[],
        is_private=False,
        team_id=None,
    )
    ver = version or _version(status=status)
    listing.latest_version = ver
    listing.latest_version_id = ver.id
    listing.versions = [ver]
    return listing


def _req(**overrides):
    base = {
        "name": "Cosmic Sizing",
        "version": "1.0.0",
        "description": "Deterministic COSMIC sizing workflow",
        "owner": "alice",
        "script_content": SCRIPT,
        "supported_harnesses": ["pi"],
        "target_agents": [],
    }
    base.update(overrides)
    return base


class TestValidation:
    def test_empty_script_rejected(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            workflow_routes._validate_script("   ")
        assert exc.value.status_code == 422

    def test_comment_only_script_rejected(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            workflow_routes._validate_script("// too short\n// to be real")

    def test_real_script_accepted(self):
        assert workflow_routes._validate_script(SCRIPT) == SCRIPT


class TestSubmitWorkflow:
    async def test_submit_creates_pending_listing(self, monkeypatch):
        app = FastAPI()
        app.include_router(workflow_routes.router)
        db = _db()
        added = []
        db.add = Mock(side_effect=lambda obj: added.append(obj))

        async def _flush():
            from datetime import UTC as _UTC
            from datetime import datetime as _dt

            now = _dt.now(_UTC)
            for obj in added:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid.uuid4()
                for attr, default in (("created_at", now), ("updated_at", now), ("released_at", now), ("download_count", 0)):
                    if getattr(obj, attr, None) is None:
                        setattr(obj, attr, default)
            for obj in added:
                if isinstance(obj, WorkflowListing):
                    obj.latest_version = next(
                        (v for v in added if isinstance(v, WorkflowVersion) and v.listing_id == obj.id), None
                    )

        db.flush = AsyncMock(side_effect=_flush)
        monkeypatch.setattr(workflow_routes, "identity_exists", AsyncMock(return_value=False))
        monkeypatch.setattr(workflow_routes.inbox, "on_publish", AsyncMock())
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: _user()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/workflows/submit", json=_req())

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["name"] == "Cosmic Sizing"
        assert body["status"] == "pending"
        assert body["script_content"] == SCRIPT

    async def test_submit_rejects_empty_script(self, monkeypatch):
        app = FastAPI()
        app.include_router(workflow_routes.router)
        app.dependency_overrides[get_db] = lambda: _db()
        app.dependency_overrides[get_current_user] = lambda: _user()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/workflows/submit", json=_req(script_content=""))

        assert response.status_code == 422


class TestInstallWorkflow:
    async def test_install_returns_pi_workflow_file(self, monkeypatch):
        app = FastAPI()
        app.include_router(workflow_routes.router)
        db = _db()
        listing = _listing()
        db.execute = AsyncMock(return_value=_result(listing))
        monkeypatch.setattr(
            workflow_routes, "resolve_visible_listing", AsyncMock(return_value=listing)
        )
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_registry_user] = lambda: _user()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/workflows/{LISTING_ID}/install",
                json={"harness": "pi", "scope": "project"},
            )

        assert response.status_code == 200, response.text
        snippet = response.json()["config_snippet"]
        assert snippet["workflows"][0]["path"] == ".pi/workflows/cosmic-sizing.js"
        assert snippet["workflows"][0]["content"] == SCRIPT

    async def test_install_rejects_unsupported_harness(self, monkeypatch):
        app = FastAPI()
        app.include_router(workflow_routes.router)
        listing = _listing()
        monkeypatch.setattr(
            workflow_routes, "resolve_visible_listing", AsyncMock(return_value=listing)
        )
        app.dependency_overrides[get_db] = lambda: _db()
        app.dependency_overrides[get_registry_user] = lambda: _user()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/workflows/{LISTING_ID}/install",
                json={"harness": "claude-code", "scope": "project"},
            )

        assert response.status_code == 400
        assert "does not support workflows" in response.json()["detail"]


class TestConfigGenerator:
    def test_pi_project_path(self):
        listing = _listing()
        snippet = generate_workflow_config(listing, "pi", scope="project")
        assert snippet["workflows"][0]["path"] == ".pi/workflows/cosmic-sizing.js"

    def test_pi_user_path(self):
        listing = _listing()
        snippet = generate_workflow_config(listing, "pi", scope="user")
        assert snippet["workflows"][0]["path"] == "~/.pi/agent/workflows/cosmic-sizing.js"

    def test_local_name_overrides_slug(self):
        listing = _listing()
        snippet = generate_workflow_config(listing, "pi", scope="project", local_name="custom-name")
        assert snippet["workflows"][0]["path"] == ".pi/workflows/custom-name.js"

    def test_non_workflow_harness_raises(self):
        listing = _listing()
        with pytest.raises(ValueError, match="does not support workflows"):
            generate_workflow_config(listing, "claude-code", scope="project")


class TestHarnessRegistry:
    def test_pi_declares_workflows_capability(self):
        from observal_shared.harness_registry import HARNESS_REGISTRY

        assert "workflows" in HARNESS_REGISTRY["pi"]["capabilities"]
        assert HARNESS_REGISTRY["pi"]["workflows"]["project"] == ".pi/workflows/{name}.js"
