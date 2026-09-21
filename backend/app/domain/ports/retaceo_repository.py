"""Persistence port for retaceo landed-cost allocations."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.domain.entities.retaceo import Retaceo, RetaceoStatus


class RetaceoRepository(Protocol):
    async def list_retaceos(
        self,
        company_id: uuid.UUID,
        *,
        status: RetaceoStatus | None = None,
        purchase_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Retaceo], int]: ...

    async def get_retaceo(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo | None: ...

    async def get_retaceo_for_update(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
    ) -> Retaceo | None: ...

    async def allocate_next_code(self, company_id: uuid.UUID) -> str: ...

    async def add_retaceo(self, retaceo: Retaceo) -> Retaceo: ...

    async def replace_draft(self, retaceo: Retaceo) -> Retaceo | None: ...

    async def update_status(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        status: RetaceoStatus,
    ) -> Retaceo | None: ...
