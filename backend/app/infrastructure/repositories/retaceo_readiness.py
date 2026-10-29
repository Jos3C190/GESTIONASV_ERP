"""Shared persisted retaceo readiness checks for inventory release and labels."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.inventory_valuation import (
    InventoryRetaceoApplicationModel,
    InventoryValuationSettingModel,
)
from app.infrastructure.models.retaceo import RetaceoModel


async def purchase_retaceo_readiness_error(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    purchase_id: uuid.UUID,
    received_at: datetime,
    require_closed: bool = False,
    require_applied: bool = True,
) -> str | None:
    """Return the existing label policy's blocker, if an active retaceo applies."""
    retaceos = list(
        (
            await session.scalars(
                select(RetaceoModel).where(
                    RetaceoModel.company_id == company_id,
                    RetaceoModel.purchase_id == purchase_id,
                )
            )
        ).all()
    )
    active = [row for row in retaceos if row.status != "cancelled"]
    if require_closed and (not active or any(row.status != "closed" for row in active)):
        return "not_final"
    if any(row.status not in {"verified", "closed"} for row in active):
        return "not_final"
    if not active or not require_applied:
        return None

    setting = await session.get(InventoryValuationSettingModel, company_id)
    if setting is None or received_at <= setting.opened_at:
        return None

    applied_ids = set(
        (
            await session.scalars(
                select(InventoryRetaceoApplicationModel.retaceo_id).where(
                    InventoryRetaceoApplicationModel.company_id == company_id,
                    InventoryRetaceoApplicationModel.retaceo_id.in_([row.id for row in active]),
                )
            )
        ).all()
    )
    if any(row.applied_at is None or row.id not in applied_ids for row in active):
        return "cost_unapplied"
    return None
