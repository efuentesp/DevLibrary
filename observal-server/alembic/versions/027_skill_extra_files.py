# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Add extra_files JSON column to skill_versions for multi-file skills.

Revision ID: 027_skill_extra_files
Revises: 026_usage_ping_state
Create Date: 2026-09-06

Each entry is {"path": str, "content": str, "encoding": "utf-8" | "base64"}.
See observal_shared.skill_files for the shared validation contract.
"""

import sqlalchemy as sa

# "op" is injected by Alembic at migration runtime; type checkers that lack the
# server environment cannot resolve it statically.
from alembic import op  # type: ignore

revision = "027_skill_extra_files"
down_revision = "026_usage_ping_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skill_versions", sa.Column("extra_files", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("skill_versions", "extra_files")
