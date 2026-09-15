# SPDX-FileCopyrightText: 2026 Edgar F. Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Add the workflow component type (listings, versions, downloads).

Revision ID: 028_workflow_component
Revises: 027_skill_extra_files
Create Date: 2026-09-14

A workflow is a single self-contained JavaScript file (deterministic
orchestration for harness workflow runtimes, e.g. pi). The script body is
stored on workflow_versions.script_content; install writes it to the
harness's workflow directory.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "028_workflow_component"
down_revision = "027_skill_extra_files"
branch_labels = None
depends_on = None

_LISTING_STATUS = ("draft", "pending", "approved", "rejected", "archived")


def _status_enum():
    """Reuse the existing listingstatus enum, creating it only when missing."""
    inspector = sa.inspect(op.get_bind())
    existing = {row["name"] for row in inspector.get_enums()}
    if "listingstatus" in existing:
        return postgresql.ENUM(name="listingstatus", create_type=False)
    return sa.Enum(*_LISTING_STATUS, name="listingstatus")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "workflow_listings" in inspector.get_table_names():
        return

    status_enum = _status_enum()

    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("download_count", sa.Integer(), nullable=False),
        sa.Column("released_by", sa.UUID(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supported_harnesses", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("script_content", sa.Text(), nullable=False),
        sa.Column("validated", sa.Boolean(), nullable=False),
        sa.Column("target_agents", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("is_editing", sa.Boolean(), nullable=False),
        sa.Column("editing_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("editing_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["listing_id"], ["workflow_listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["released_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["editing_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "version"),
    )
    op.create_index("ix_workflow_versions_listing_id", "workflow_versions", ["listing_id"])
    op.create_index("ix_workflow_versions_status", "workflow_versions", ["status"])

    op.create_table(
        "workflow_listings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("namespace", sa.String(length=32), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("is_private", sa.Boolean(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=True),
        sa.Column("bundle_id", sa.UUID(), nullable=True),
        sa.Column("submitted_by", sa.UUID(), nullable=False),
        sa.Column("co_authors", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("unique_agents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_version_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bundle_id"], ["component_bundles.id"]),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["latest_version_id"], ["workflow_versions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("namespace", "slug", name="uq_workflow_listings_namespace_slug"),
    )
    op.create_index("ix_workflow_listings_namespace", "workflow_listings", ["namespace"])
    op.create_index("ix_workflow_listings_submitted_by", "workflow_listings", ["submitted_by"])
    op.create_index("ix_workflow_listings_team_id", "workflow_listings", ["team_id"])

    op.create_table(
        "workflow_downloads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("harness", sa.String(length=50), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["workflow_listings.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("workflow_downloads")
    op.drop_table("workflow_listings")
    op.drop_table("workflow_versions")
