# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Drop the never-written sandbox_downloads table.

Revision ID: 031_drop_sandbox_downloads
Revises: 030_sandbox_validation_results
Create Date: 2026-09-15

sandbox_downloads was created alongside the sandbox runtime config but no
code ever wrote it. Component adoption is tracked uniformly through
component_download_records (with version_ref, agent_id, and source), and
the listing counters are maintained by record_component_download.
"""

# "op" is injected by Alembic at migration runtime; type checkers that lack the
# server environment cannot resolve it statically.
from alembic import op  # type: ignore

revision = "031_drop_sandbox_downloads"
down_revision = "030_sandbox_validation_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("sandbox_downloads")


def downgrade() -> None:
    # The table was never written; recreating it exactly as it was is not
    # worth the round-trip — schema state before 031 is simply unavailable.
    raise NotImplementedError("sandbox_downloads was dead schema; downgrade recreates nothing")
