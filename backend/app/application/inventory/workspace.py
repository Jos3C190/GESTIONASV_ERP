"""Inventory workspace application boundary."""

from typing import Any

from app.domain.ports.inventory_workspace import InventoryWorkspaceRepository


class InventoryWorkspace:
    def __init__(self, repository: InventoryWorkspaceRepository) -> None:
        self.repository = repository

    async def stock(self, **scope: Any) -> dict[str, Any]:
        return await self.repository.stock(**scope)

    async def open_product(self, **command: Any) -> dict[str, Any]:
        return await self.repository.open_product(**command)
