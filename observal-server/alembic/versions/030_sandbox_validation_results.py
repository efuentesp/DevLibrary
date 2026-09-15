# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Add validation_results JSON column to sandbox_versions.

Revision ID: 030_sandbox_validation_results
Revises: 029_sandbox_env_mounts
Create Date: 2026-09-15

Written by the validate_sandbox_version arq job after a version is approved:
{"status": "valid|missing|error", "registry", "repository", "reference",
 "digest", "size_bytes", "architectures", "checked_at", "detail"}.
"""

import sqlalchemy as sa

# "op" is injected by Alembic at migration runtime; type checkers that lack the
# server environment cannot resolve it statically.
from alembic import op  # type: ignore

revision = "030_sandbox_validation_results"
down_revision = "029_sandbox_env_mounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sandbox_versions", sa.Column("validation_results", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("sandbox_versions", "validation_results")
