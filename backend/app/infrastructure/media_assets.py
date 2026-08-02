from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.media import MediaAsset


async def attach_media_by_url(
    session: AsyncSession,
    *,
    secure_url: str | None,
    company_id: uuid.UUID,
    owner_type: str,
    owner_id: uuid.UUID,
    replace_single: bool = False,
) -> None:
    if replace_single:
        await session.execute(
            update(MediaAsset)
            .where(
                MediaAsset.owner_type == owner_type,
                MediaAsset.owner_id == owner_id,
                MediaAsset.status == "active",
                MediaAsset.secure_url != secure_url,
            )
            .values(status="detached")
        )
    if not secure_url:
        return
    asset = await session.scalar(select(MediaAsset).where(MediaAsset.secure_url == secure_url))
    if asset is not None:
        asset.company_id = company_id
        asset.owner_type = owner_type
        asset.owner_id = owner_id
        asset.status = "active"
