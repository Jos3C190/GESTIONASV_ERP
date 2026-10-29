"""Persistence for random, revocable public inventory trace links."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.inventory import InventoryHandlingUnitModel
from app.infrastructure.models.inventory_trace_capability import (
    InventoryTraceCapabilityModel,
)


def digest_trace_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class SqlAlchemyInventoryTraceCapabilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        company_id: uuid.UUID,
        handling_unit_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> tuple[InventoryTraceCapabilityModel, str] | None:
        unit = await self.session.scalar(
            select(InventoryHandlingUnitModel.id).where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.id == handling_unit_id,
            )
        )
        if unit is None:
            return None

        token = secrets.token_urlsafe(32)
        capability = InventoryTraceCapabilityModel(
            company_id=company_id,
            handling_unit_id=handling_unit_id,
            token_digest=digest_trace_token(token),
            created_by=actor_id,
        )
        self.session.add(capability)
        await self.session.flush()
        return capability, token

    async def revoke_all(
        self,
        *,
        company_id: uuid.UUID,
        handling_unit_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> int:
        result = await self.session.execute(
            update(InventoryTraceCapabilityModel)
            .where(
                InventoryTraceCapabilityModel.company_id == company_id,
                InventoryTraceCapabilityModel.handling_unit_id == handling_unit_id,
                InventoryTraceCapabilityModel.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC), revoked_by=actor_id)
        )
        return int(result.rowcount or 0)

    async def get_active(self, token: str) -> InventoryTraceCapabilityModel | None:
        return await self.session.scalar(
            select(InventoryTraceCapabilityModel).where(
                InventoryTraceCapabilityModel.token_digest == digest_trace_token(token),
                InventoryTraceCapabilityModel.revoked_at.is_(None),
            )
        )


__all__ = ["SqlAlchemyInventoryTraceCapabilityRepository", "digest_trace_token"]
