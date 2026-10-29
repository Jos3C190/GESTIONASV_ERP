"""Pure helpers for Kardex balances, local calendar boundaries and scope masking."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.entities.operational_context import OperationalContext

LOCAL_TZ = ZoneInfo("America/El_Salvador")
ZERO = Decimal("0")


def snapshot_quantity(
    snapshot: list[dict[str, Any]], *, warehouse_id: uuid.UUID,
    inventory_item_id: uuid.UUID, lot_code: str | None,
) -> Decimal:
    return sum(
        (Decimal(row["quantity_base"]) for row in snapshot
         if row.get("warehouse_id") == str(warehouse_id)
         and row.get("inventory_item_id") == str(inventory_item_id)
         and (lot_code is None or row.get("lot_code") == lot_code)),
        ZERO,
    )


def warehouse_scope_allowed(context: OperationalContext, branch_id: uuid.UUID | None) -> bool:
    if branch_id is None:
        return context.access_all_branches
    return context.access_all_branches or context.can_access(branch_id)


def valuation_opening_known(opened_at: datetime, period_from: date) -> bool:
    """A daily opening balance is known only after the cut's accounting day."""
    return opened_at.astimezone(LOCAL_TZ).date() < period_from


def mask_unauthorized_warehouse_endpoints(
    row: dict[str, Any], authorized_warehouse_ids: set[uuid.UUID]
) -> dict[str, Any]:
    for prefix in ("from", "to"):
        if row[f"{prefix}_warehouse_id"] not in authorized_warehouse_ids:
            for field in (
                "warehouse_id", "warehouse_code", "warehouse_name",
                "location_id", "location_code", "stock_status",
            ):
                row[f"{prefix}_{field}"] = None
    return row
