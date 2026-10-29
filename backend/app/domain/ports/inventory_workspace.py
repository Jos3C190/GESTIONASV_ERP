"""Ports for warehouse stock consultation and documented product opening."""

from typing import Any, Protocol


class InventoryWorkspaceRepository(Protocol):
    async def stock(self, **scope: Any) -> dict[str, Any]: ...

    async def open_product(self, **command: Any) -> dict[str, Any]: ...
