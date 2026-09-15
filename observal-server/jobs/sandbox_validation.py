# SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""Background validation of sandbox image references."""

import uuid
from datetime import UTC, datetime

from loguru import logger as optic
from sqlalchemy import select


async def validate_sandbox_version(ctx: dict, version_id: str) -> None:
    """Check the version's image ref against its registry and stamp results."""
    from database import async_session
    from models.sandbox import SandboxVersion
    from services.sandbox_image_validation import check_image_ref

    async with async_session() as db:
        version = (
            await db.execute(select(SandboxVersion).where(SandboxVersion.id == uuid.UUID(version_id)))
        ).scalar_one_or_none()
        if version is None:
            optic.warning("sandbox validation: version {} not found", version_id)
            return
        result = await check_image_ref(version.image)
        version.validated_at = datetime.now(UTC)
        version.validation_results = result
        await db.commit()

    optic.info(
        "sandbox image validation: version={}, image={}, status={}",
        version_id,
        result.get("repository"),
        result.get("status"),
    )
