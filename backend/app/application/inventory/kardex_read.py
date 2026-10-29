"""Application entry points for company-authorized Kardex read models."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from app.domain.ports.inventory_kardex_read_repository import InventoryKardexReadRepository


class InventoryKardexReadUseCases:
    def __init__(self, repository: InventoryKardexReadRepository) -> None:
        self._repository = repository

    async def get_warehouse_scope(
        self, *, warehouse_id: uuid.UUID
    ) -> tuple[uuid.UUID, uuid.UUID | None] | None:
        return await self._repository.get_warehouse_scope(warehouse_id=warehouse_id)

    async def search_items(
        self, *, company_id: uuid.UUID, warehouse_id: uuid.UUID, query: str
    ) -> Sequence[Mapping[str, Any]]:
        return await self._repository.search_items(
            company_id=company_id, warehouse_id=warehouse_id, query=query
        )

    async def physical_kardex(self, **kwargs: Any) -> Mapping[str, Any] | None:
        return await self._repository.physical_kardex(**kwargs)

    async def reconciliation(self, **kwargs: Any) -> Mapping[str, Any]:
        return await self._repository.reconciliation(**kwargs)

    async def valued_kardex(self, **kwargs: Any) -> Mapping[str, Any] | None:
        return await self._repository.valued_kardex(**kwargs)
