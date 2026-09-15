# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Add env_vars and allowed_mounts JSON columns to sandbox_versions.

Revision ID: 029_sandbox_env_mounts
Revises: 028_workflow_component
Create Date: 2026-09-06

env_vars: list of "KEY" or "KEY=value" static environment entries applied to
every execution. allowed_mounts: list of "host_path:container_path[:ro]"
volume mounts, mirroring Docker bind-mount syntax.
"""

import sqlalchemy as sa

# "op" is injected by Alembic at migration runtime; type checkers that lack the
# server environment cannot resolve it statically.
from alembic import op  # type: ignore

revision = "029_sandbox_env_mounts"
down_revision = "028_workflow_component"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sandbox_versions", sa.Column("env_vars", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("sandbox_versions", sa.Column("allowed_mounts", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("sandbox_versions", "allowed_mounts")
    op.drop_column("sandbox_versions", "env_vars")
