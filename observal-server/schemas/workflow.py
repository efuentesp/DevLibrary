# SPDX-FileCopyrightText: 2026 Edgar F. Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Pydantic schemas for the workflow component type.

A workflow is a single self-contained JavaScript file that deterministic
harness workflow runtimes (e.g. pi) execute. The registry versions the
script body; install writes it to the harness's workflow directory.
"""


import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from models.mcp import ListingStatus
from schemas.constants import Visibility, make_harness_list_validator


class WorkflowSubmitRequest(BaseModel):
    name: str
    version: str
    description: str
    owner: str
    team_id: uuid.UUID | None = None
    visibility: Visibility = "public"
    script_content: str
    supported_harnesses: list[str] = ["pi"]
    target_agents: list[str] = []

    _validate_harnesses = field_validator("supported_harnesses")(make_harness_list_validator())


class WorkflowDraftRequest(BaseModel):
    name: str | None = None
    version: str | None = None
    description: str | None = None
    owner: str | None = None
    team_id: uuid.UUID | None = None
    visibility: Visibility | None = None
    script_content: str | None = None
    supported_harnesses: list[str] | None = None
    target_agents: list[str] | None = None

    _validate_harnesses = field_validator("supported_harnesses")(make_harness_list_validator())


class WorkflowUpdateRequest(BaseModel):
    name: str | None = None
    version: str | None = None
    description: str | None = None
    owner: str | None = None
    team_id: uuid.UUID | None = None
    visibility: Visibility | None = None
    script_content: str | None = None
    target_agents: list[str] | None = None
    supported_harnesses: list[str] | None = None

    _validate_harnesses = field_validator("supported_harnesses")(make_harness_list_validator())


class WorkflowListingResponse(BaseModel):
    id: uuid.UUID
    name: str
    namespace: str
    slug: str
    qualified_name: str
    version: str
    description: str
    owner: str
    team_id: uuid.UUID | None = None
    visibility: Visibility = "public"
    is_private: bool = False
    target_agents: list[str]
    supported_harnesses: list[str]
    script_content: str | None = None
    validated: bool = False
    status: ListingStatus
    rejection_reason: str | None = None
    submitted_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    download_count: int = 0
    user_permission: str | None = None

    @field_validator("user_permission", mode="before")
    @classmethod
    def _coerce_user_permission(cls, v):
        return v if isinstance(v, str) else None

    model_config = {"from_attributes": True}


class WorkflowListingSummary(BaseModel):
    id: uuid.UUID
    name: str
    namespace: str
    slug: str
    qualified_name: str
    version: str
    description: str
    owner: str
    team_id: uuid.UUID | None = None
    visibility: Visibility = "public"
    is_private: bool = False
    target_agents: list[str]
    status: ListingStatus
    rejection_reason: str | None = None
    updated_at: datetime | None = None
    model_config = {"from_attributes": True}


class WorkflowInstallRequest(BaseModel):
    harness: str
    scope: Literal["project", "user"] = "project"
    local_name: str | None = None
    version: str | None = None


class WorkflowInstallResponse(BaseModel):
    listing_id: uuid.UUID
    harness: str
    config_snippet: dict
    warnings: list[str] = []
