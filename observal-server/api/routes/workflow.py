# SPDX-FileCopyrightText: 2026 Edgar F. Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Workflow component routes.

A workflow is a single self-contained JavaScript file that deterministic
harness workflow runtimes execute. The registry versions the script body;
install returns a {"workflows": [{"path", "content"}]} snippet the CLI
writes into the harness's workflow directory.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from loguru import logger as optic
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    apply_registry_scope,
    apply_visibility_filter,
    commit_or_name_conflict,
    get_db,
    get_effective_component_permission,
    get_registry_user,
    may_view_unapproved,
    require_role,
    resolve_listing,
    resolve_visible_listing,
)
from api.routes._component_archive import archive_listing, archived_install_warning, unarchive_listing
from api.routes.component_versions import create_version_router
from api.sanitize import escape_like
from api.search import keyword_search
from models.mcp import ListingStatus
from models.user import User, UserRole
from models.workflow import WorkflowDownload, WorkflowListing, WorkflowVersion
from schemas.workflow import (
    WorkflowDraftRequest,
    WorkflowInstallRequest,
    WorkflowInstallResponse,
    WorkflowListingResponse,
    WorkflowListingSummary,
    WorkflowSubmitRequest,
    WorkflowUpdateRequest,
)
from services.editing_lock import _is_lock_expired, acquire_edit_lock, release_edit_lock
from services.inbox import sources as inbox
from services.registry_namespace import identity_exists
from services.teamspace import publish_auto_approves_for_entity, resolve_publish_target
from services.workflow_config_generator import generate_workflow_config

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])

# The registry stores the script body; anything beyond a comment-only file
# is accepted. Determinism is the submitter's contract, not a server check.
_MIN_SCRIPT_CHARS = 10


def _validate_script(script_content: str | None) -> str:
    if not script_content or not script_content.strip():
        raise HTTPException(status_code=422, detail="script_content is required")
    stripped = script_content.strip()
    if len(stripped) < _MIN_SCRIPT_CHARS or (stripped.startswith("//") and len(stripped.splitlines()) < 3):
        raise HTTPException(status_code=422, detail="script_content is too short to be a workflow")
    return script_content


def _reject_visibility_edits(listing, req) -> None:
    """Refuse teamspace or visibility changes on the draft update route.

    Mirrors the skill policy: visibility has exactly one authoritative path
    (the registry visibility PATCH), so a real change is rejected here.
    """
    if req.team_id is not None and req.team_id != listing.team_id:
        raise HTTPException(
            status_code=400,
            detail="team_id cannot be changed here. A listing stays in the teamspace it was created under.",
        )
    if req.visibility is not None and req.visibility != listing.visibility:
        raise HTTPException(
            status_code=400,
            detail=f"visibility cannot be changed here. Use PATCH /api/v1/registry/workflow/{listing.id}/visibility.",
        )


@router.post("/submit", response_model=WorkflowListingResponse)
async def submit_workflow(
    req: WorkflowSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    optic.debug("submitting workflow: {}", req.name)
    _validate_script(req.script_content)

    target = await resolve_publish_target(
        db,
        current_user,
        req.name,
        team_id=req.team_id,
        visibility=req.visibility,
    )
    if await identity_exists(db, WorkflowListing, target.namespace, target.slug):
        raise HTTPException(status_code=409, detail=f"Workflow '{target.namespace}/{target.slug}' already exists")

    listing = WorkflowListing(
        name=req.name,
        namespace=target.namespace,
        slug=target.slug,
        owner=target.owner if target.team_id else req.owner,
        submitted_by=current_user.id,
        team_id=target.team_id,
        is_private=target.visibility == "team",
    )
    db.add(listing)
    await db.flush()

    version = WorkflowVersion(
        listing_id=listing.id,
        version=req.version,
        description=req.description,
        script_content=req.script_content,
        validated=True,
        target_agents=req.target_agents,
        supported_harnesses=req.supported_harnesses,
        status=ListingStatus.approved if target.auto_approve else ListingStatus.pending,
        released_by=current_user.id,
        released_at=datetime.now(UTC),
        reviewed_by=current_user.id if target.auto_approve else None,
        reviewed_at=datetime.now(UTC) if target.auto_approve else None,
    )
    db.add(version)
    await db.flush()

    listing.latest_version_id = version.id
    await inbox.on_publish(
        db,
        listing,
        subject_type="workflow",
        actor_id=current_user.id,
        auto_approved=target.auto_approve,
        version=version.version,
    )
    await commit_or_name_conflict(db, "workflow")
    await db.refresh(listing)
    return WorkflowListingResponse.model_validate(listing)


@router.get("", response_model=list[WorkflowListingSummary])
async def list_workflows(
    response: Response,
    target_agent: str | None = Query(None),
    harness: str | None = Query(None),
    namespace: str | None = Query(None),
    search: str | None = Query(None),
    team_id: uuid.UUID | None = Query(None, description="Only listings owned by this teamspace"),
    composable_for_team_id: uuid.UUID | None = Query(
        None, description="Public listings plus this teamspace's private ones, for agent composition"
    ),
    public_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_registry_user),
):
    optic.debug("listing workflows (search={})", search)
    stmt = (
        select(WorkflowListing)
        .join(WorkflowVersion, WorkflowListing.latest_version_id == WorkflowVersion.id)
        .where(WorkflowVersion.status == ListingStatus.approved)
    )
    if harness:
        stmt = stmt.where(cast(WorkflowVersion.supported_harnesses, String).ilike(f'%"{escape_like(harness)}"%'))
    if namespace:
        stmt = stmt.where(WorkflowListing.namespace == namespace.strip().lower())
    target_agents_text = cast(WorkflowVersion.target_agents, String)
    if target_agent:
        target_filter, _ = keyword_search(target_agent, [target_agents_text])
        if target_filter is not None:
            stmt = stmt.where(target_filter)
    search_rank = None
    if search:
        search_filter, search_rank = keyword_search(
            search,
            [
                WorkflowListing.name,
                WorkflowListing.slug,
                WorkflowListing.namespace,
                WorkflowListing.owner,
                WorkflowVersion.description,
                WorkflowVersion.script_content,
                target_agents_text,
                cast(WorkflowVersion.supported_harnesses, String),
            ],
            name_field=WorkflowListing.name,
        )
        if search_filter is not None:
            stmt = stmt.where(search_filter)
    stmt = apply_registry_scope(
        stmt,
        WorkflowListing,
        current_user,
        team_id=team_id,
        composable_for_team_id=composable_for_team_id,
        public_only=public_only,
    )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    order_by = [WorkflowListing.created_at.desc()]
    if search_rank is not None:
        order_by.insert(0, search_rank.desc())
    result = await db.execute(stmt.order_by(*order_by).limit(limit).offset(offset))
    listings = [WorkflowListingSummary.model_validate(r) for r in result.scalars().all()]
    response.headers["X-Total-Count"] = str(total or 0)
    return listings


@router.get("/my", response_model=list[WorkflowListingSummary])
async def my_workflows(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    optic.debug("my_workflows called")
    stmt = (
        select(WorkflowListing)
        .where(WorkflowListing.submitted_by == current_user.id)
        .order_by(WorkflowListing.created_at.desc())
    )
    # Authorship is not a standing grant: a member removed from a teamspace
    # keeps the author column but must not keep reading team-private listings.
    stmt = apply_visibility_filter(stmt, WorkflowListing, current_user)

    result = await db.execute(stmt)
    listings = [WorkflowListingSummary.model_validate(r) for r in result.scalars().all()]
    return listings


@router.get("/{listing_id}", response_model=WorkflowListingResponse)
async def get_workflow(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_registry_user),
):
    optic.debug("fetching workflow {}", listing_id)
    listing = await resolve_visible_listing(
        WorkflowListing, listing_id, db, current_user, require_status=ListingStatus.approved
    )
    if listing is None:
        listing = await resolve_visible_listing(WorkflowListing, listing_id, db, current_user)
        may_view = listing is not None and may_view_unapproved(
            get_effective_component_permission(listing, current_user), current_user
        )
        if not may_view:
            raise HTTPException(status_code=404, detail="Listing not found")
    resp = WorkflowListingResponse.model_validate(listing)
    resp.user_permission = get_effective_component_permission(listing, current_user)
    return resp


@router.post("/{listing_id}/install", response_model=WorkflowInstallResponse)
async def install_workflow(
    listing_id: str,
    req: WorkflowInstallRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_registry_user),
):
    optic.debug("installing workflow {}", listing_id)
    listing = await resolve_visible_listing(
        WorkflowListing, listing_id, db, current_user, require_status=ListingStatus.approved
    )
    if not listing:
        listing = await resolve_visible_listing(WorkflowListing, listing_id, db, current_user)
        if not listing or current_user is None:
            raise HTTPException(status_code=404, detail="Listing not found or not approved")
        if (
            listing.status != ListingStatus.archived
            and get_effective_component_permission(listing, current_user) != "owner"
        ):
            raise HTTPException(status_code=404, detail="Listing not found or not approved")

    warnings = []
    if listing.status == ListingStatus.archived:
        warnings.append(archived_install_warning("workflow", listing.name))

    version_override = None
    if req.version:
        ver_stmt = select(WorkflowVersion).where(
            WorkflowVersion.listing_id == listing.id,
            WorkflowVersion.version == req.version,
            WorkflowVersion.status.in_([ListingStatus.approved, listing.status]),
        )
        ver_result = await db.execute(ver_stmt)
        version_override = ver_result.scalar_one_or_none()
        if not version_override:
            raise HTTPException(
                status_code=404,
                detail=f"Version {req.version!r} not found for this workflow",
            )

    if current_user is not None:
        db.add(WorkflowDownload(listing_id=listing.id, user_id=current_user.id, harness=req.harness))
        latest_version = getattr(listing, "latest_version", None)
        if latest_version:
            latest_version.download_count += 1
        await commit_or_name_conflict(db, "workflow")

    try:
        config = generate_workflow_config(
            listing,
            req.harness,
            scope=req.scope,
            version_override=version_override,
            local_name=req.local_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkflowInstallResponse(listing_id=listing.id, harness=req.harness, config_snippet=config, warnings=warnings)


@router.post("/draft", response_model=WorkflowListingResponse)
async def save_workflow_draft(
    req: WorkflowDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    optic.trace("req={}", req)
    if req.script_content is not None:
        _validate_script(req.script_content)

    target = await resolve_publish_target(
        db,
        current_user,
        req.name,
        team_id=req.team_id,
        visibility=req.visibility,
    )
    if await identity_exists(db, WorkflowListing, target.namespace, target.slug):
        raise HTTPException(status_code=409, detail=f"Workflow '{target.namespace}/{target.slug}' already exists")
    listing = WorkflowListing(
        name=req.name,
        namespace=target.namespace,
        slug=target.slug,
        owner=target.owner if target.team_id else (req.owner or current_user.username or current_user.email),
        submitted_by=current_user.id,
        team_id=target.team_id,
        is_private=target.visibility == "team",
    )
    db.add(listing)
    await db.flush()

    version = WorkflowVersion(
        listing_id=listing.id,
        version=req.version,
        description=req.description or "",
        script_content=req.script_content or "// draft workflow\n",
        target_agents=req.target_agents or [],
        supported_harnesses=req.supported_harnesses or ["pi"],
        status=ListingStatus.draft,
        released_by=current_user.id,
        released_at=datetime.now(UTC),
    )
    db.add(version)
    await db.flush()

    listing.latest_version_id = version.id
    await commit_or_name_conflict(db, "workflow")
    await db.refresh(listing)
    return WorkflowListingResponse.model_validate(listing)


@router.put("/{listing_id}/draft", response_model=WorkflowListingResponse)
async def update_workflow_draft(
    listing_id: str,
    req: WorkflowUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    optic.trace("listing_id={}", listing_id)
    listing = await resolve_listing(WorkflowListing, listing_id, db, current_user=current_user)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if get_effective_component_permission(listing, current_user) != "owner":
        raise HTTPException(status_code=403, detail="Not the listing owner")
    if listing.status not in (ListingStatus.draft, ListingStatus.rejected, ListingStatus.pending):
        raise HTTPException(status_code=400, detail="Only draft, rejected, or pending listings can be edited")
    _reject_visibility_edits(listing, req)

    ver = listing.latest_version
    if not ver:
        raise HTTPException(status_code=400, detail="Listing has no version to update")

    if req.script_content is not None:
        _validate_script(req.script_content)

    for field in ("version", "description", "script_content", "target_agents", "supported_harnesses"):
        val = getattr(req, field)
        if val is not None:
            setattr(ver, field, val)

    # Don't allow saving over another user's active lock
    if ver.is_editing and ver.editing_by != current_user.id and not _is_lock_expired(ver.editing_since):
        raise HTTPException(
            status_code=409,
            detail="This item is currently being edited by another user. Please try again later.",
        )
    release_edit_lock(ver, current_user.id, force=True)
    await db.flush()

    for field in ("name", "owner"):
        val = getattr(req, field)
        if val is not None:
            setattr(listing, field, val)

    await commit_or_name_conflict(db, "workflow")
    await db.refresh(listing)
    return WorkflowListingResponse.model_validate(listing)


@router.post("/{listing_id}/start-edit")
async def start_edit_workflow(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    optic.trace("listing_id={}", listing_id)
    listing = await resolve_listing(WorkflowListing, listing_id, db, current_user=current_user)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if get_effective_component_permission(listing, current_user) != "owner":
        raise HTTPException(status_code=403, detail="Not the listing owner")
    ver = listing.latest_version
    if not ver:
        raise HTTPException(status_code=400, detail="Listing has no version")
    if ver.status not in (ListingStatus.pending, ListingStatus.draft, ListingStatus.rejected):
        raise HTTPException(status_code=400, detail=f"Cannot edit: listing is '{ver.status.value}'")
    # Re-fetch with row-level lock to prevent TOCTOU race
    ver = (await db.execute(select(WorkflowVersion).where(WorkflowVersion.id == ver.id).with_for_update())).scalar_one()
    acquire_edit_lock(ver, current_user.id)
    await commit_or_name_conflict(db, "workflow")
    return {"status": "locked"}


@router.post("/{listing_id}/cancel-edit")
async def cancel_edit_workflow(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    optic.trace("listing_id={}", listing_id)
    listing = await resolve_listing(WorkflowListing, listing_id, db, current_user=current_user)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if get_effective_component_permission(listing, current_user) != "owner":
        raise HTTPException(status_code=403, detail="Not the listing owner")
    ver = listing.latest_version
    if not ver:
        raise HTTPException(status_code=400, detail="Listing has no version")
    release_edit_lock(ver, current_user.id)
    await commit_or_name_conflict(db, "workflow")
    return {"status": "unlocked"}


@router.post("/{listing_id}/submit", response_model=WorkflowListingResponse)
async def submit_workflow_draft(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    optic.trace("listing_id={}", listing_id)
    listing = await resolve_listing(WorkflowListing, listing_id, db, current_user=current_user)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if get_effective_component_permission(listing, current_user) != "owner":
        raise HTTPException(status_code=403, detail="Not the listing owner")
    if listing.status not in (ListingStatus.draft, ListingStatus.rejected):
        raise HTTPException(status_code=400, detail="Listing is not a draft")

    ver = listing.latest_version
    if not ver:
        raise HTTPException(status_code=400, detail="Listing has no version")
    _validate_script(ver.script_content)

    if not listing.description:
        raise HTTPException(status_code=400, detail="Description is required before submitting")

    auto_approved = await publish_auto_approves_for_entity(listing, current_user, db)
    if auto_approved:
        listing.status = ListingStatus.approved
        listing.latest_version.reviewed_by = current_user.id
        listing.latest_version.reviewed_at = datetime.now(UTC)
    else:
        listing.status = ListingStatus.pending
    await inbox.on_publish(
        db,
        listing,
        subject_type="workflow",
        actor_id=current_user.id,
        auto_approved=auto_approved,
        version=getattr(listing.latest_version, "version", None),
    )
    await commit_or_name_conflict(db, "workflow")
    await db.refresh(listing)
    return WorkflowListingResponse.model_validate(listing)


@router.patch("/{listing_id}/archive")
async def archive_workflow(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    return await archive_listing(WorkflowListing, listing_id, db, current_user, "workflow")


@router.patch("/{listing_id}/unarchive")
async def unarchive_workflow(
    listing_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.user)),
):
    return await unarchive_listing(WorkflowListing, listing_id, db, current_user, "workflow")


# --- Version sub-routes ---
router.include_router(create_version_router("workflow", WorkflowListing, WorkflowVersion))
