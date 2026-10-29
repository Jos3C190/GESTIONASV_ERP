"""Read port for the physical, valued and reconciliation Kardex views."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Protocol


class InventoryKardexReadRepository(Protocol):
    async def get_warehouse_scope(
        self, *, warehouse_id: uuid.UUID
    ) -> tuple[uuid.UUID, uuid.UUID | None] | None: ...

    async def search_items(
        self, *, company_id: uuid.UUID, warehouse_id: uuid.UUID, query: str
    ) -> Sequence[Mapping[str, Any]]: ...

    async def physical_kardex(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        inventory_item_id: uuid.UUID,
        period_from: date,
        period_to: date,
        movement_type: str | None,
        lot_code: str | None,
        page: int,
        page_size: int,
        access_all_branches: bool,
        accessible_branch_ids: set[uuid.UUID],
    ) -> Mapping[str, Any] | None: ...

    async def reconciliation(
        self, *, company_id: uuid.UUID, page: int, page_size: int
    ) -> Mapping[str, Any]: ...

    async def valued_kardex(
        self,
        *,
        company_id: uuid.UUID,
        inventory_item_id: uuid.UUID,
        period_from: date,
        period_to: date,
        page: int,
        page_size: int,
    ) -> Mapping[str, Any] | None: ...
