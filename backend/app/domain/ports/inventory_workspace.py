"""Explicit persistence contract shared by adapters and application services."""

from __future__ import annotations

import uuid
from typing import Any, Protocol


class InventoryWorkspaceRepository(Protocol):
    async def stock(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        q: str,
        location_id: uuid.UUID | None,
        stock_status: str | None,
        page: int,
        size: int,
    ) -> dict[str, Any]: ...

    async def open_product(
        self, *, company_id: uuid.UUID, actor_id: uuid.UUID, command: dict[str, Any]
    ) -> dict[str, Any]: ...
