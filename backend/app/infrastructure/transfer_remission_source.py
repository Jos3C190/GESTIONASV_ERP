"""Lo que salió en un traslado despachado, para su nota de remisión (V4d)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.sales_invoices.remission import DispatchedLine, DispatchedTransfer
from app.infrastructure.repositories.inventory_transfer_repository import (
    SqlAlchemyInventoryTransferRepository,
)


def _text(value: Any) -> str | None:
    return str(value) if value else None


class SqlAlchemyDispatchedTransferSource:
    def __init__(self, session: AsyncSession) -> None:
        self._transfers = SqlAlchemyInventoryTransferRepository(session)

    async def dispatched(
        self, company_id: uuid.UUID, transfer_id: uuid.UUID
    ) -> DispatchedTransfer | None:
        """El traslado tal como salió; ``None`` si no existe o todavía no se despacha."""

        data = await self._transfers.get_transfer(company_id, transfer_id)
        if data is None or data.get("dispatched_at") is None:
            return None
        vehicle = data.get("vehicle") or {}
        driver = data.get("driver") or {}
        return DispatchedTransfer(
            id=data["id"],
            company_id=data["company_id"],
            code=data["code"],
            origin_branch_id=data.get("origin_branch_id"),
            destination_branch_id=data.get("destination_branch_id"),
            origin_name=data["origin_warehouse_name"],
            destination_name=data["destination_warehouse_name"],
            vehicle_plate=_text(vehicle.get("plate")),
            vehicle_name=_text(vehicle.get("name")),
            driver_name=_text(driver.get("name")),
            lines=tuple(
                DispatchedLine(
                    inventory_item_id=line["inventory_item_id"],
                    sku=_text(line.get("sku")),
                    name=str(line.get("product_name") or "Producto"),
                    quantity=Decimal(str(line.get("quantity_dispatched") or 0)),
                    base_unit_id=line.get("base_unit_id"),
                )
                for line in data.get("lines", [])
            ),
        )
