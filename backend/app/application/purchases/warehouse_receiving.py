"""Read operations available to the warehouse receiving workspace."""

from __future__ import annotations

import uuid

from app.domain.ports.warehouse_receiving import WarehouseReceipt, WarehouseReceivingRepository


class WarehouseReceiving:
    def __init__(self, repository: WarehouseReceivingRepository) -> None:
        self.repository = repository

    async def list_pending(
        self, company_id: uuid.UUID, warehouse_id: uuid.UUID, *, skip: int, limit: int
    ) -> tuple[list[WarehouseReceipt], int]:
        return await self.repository.list_pending(company_id, warehouse_id, skip=skip, limit=limit)

    async def get_receipt(
        self, company_id: uuid.UUID, purchase_id: uuid.UUID
    ) -> WarehouseReceipt | None:
        return await self.repository.get_receipt(company_id, purchase_id)
