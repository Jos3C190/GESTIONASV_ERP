"""Port used by inventory application services."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol

from app.domain.entities.inventory import (
    CapacityDecision,
    CapacityReservation,
    InventoryItem,
    PackagingDefinition,
    PackagingType,
    PhysicalMeasures,
    StockStatus,
)


class InventoryRepository(Protocol):
    async def create_item(
        self,
        *,
        company_id: uuid.UUID,
        product_id: int | None,
        variant_id: uuid.UUID | None,
        base_unit_id: int,
    ) -> InventoryItem: ...

    async def get_item(self, company_id: uuid.UUID, item_id: uuid.UUID) -> InventoryItem | None: ...

    async def get_item_by_target(
        self,
        *,
        company_id: uuid.UUID,
        product_id: int | None,
        variant_id: uuid.UUID | None,
    ) -> InventoryItem | None: ...

    async def list_packaging(
        self, company_id: uuid.UUID, item_id: uuid.UUID
    ) -> Sequence[PackagingDefinition]: ...

    async def create_packaging(
        self,
        *,
        company_id: uuid.UUID,
        item_id: uuid.UUID,
        code: str,
        name: str,
        packaging_type: PackagingType,
        base_quantity: Decimal,
        measures: PhysicalMeasures,
        stackable: bool,
        max_stack: int | None,
        supersedes_id: uuid.UUID | None = None,
    ) -> PackagingDefinition: ...

    async def deactivate_packaging(
        self, company_id: uuid.UUID, item_id: uuid.UUID, packaging_id: uuid.UUID
    ) -> None: ...

    async def preview_capacity(
        self,
        *,
        company_id: uuid.UUID,
        location_id: uuid.UUID,
        item_id: uuid.UUID,
        packaging_id: uuid.UUID | None,
        quantity_base: Decimal,
        stock_status: StockStatus,
        actual_measures: PhysicalMeasures | None,
        override_id: uuid.UUID | None = None,
        exclude_reservation_id: uuid.UUID | None = None,
    ) -> CapacityDecision: ...

    async def reserve_capacity(
        self,
        *,
        company_id: uuid.UUID,
        location_id: uuid.UUID,
        item_id: uuid.UUID,
        packaging_id: uuid.UUID | None,
        quantity_base: Decimal,
        stock_status: StockStatus,
        actual_measures: PhysicalMeasures | None,
        expires_at: datetime,
        actor_id: uuid.UUID,
        override_id: uuid.UUID | None = None,
    ) -> tuple[CapacityReservation, CapacityDecision]: ...

    async def change_reservation_status(
        self,
        *,
        company_id: uuid.UUID,
        reservation_id: uuid.UUID,
        action: str,
        actor_id: uuid.UUID,
    ) -> CapacityReservation: ...

    async def verify_handling_unit_measurements(
        self,
        *,
        company_id: uuid.UUID,
        handling_unit_id: uuid.UUID,
        measures: PhysicalMeasures,
        source: str,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]: ...

    async def list_handling_units(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID | None = None,
        item_id: uuid.UUID | None = None,
        stock_status: StockStatus | None = None,
        include_closed: bool = False,
    ) -> Sequence[dict[str, Any]]: ...

    async def list_balances(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID | None = None,
        item_id: uuid.UUID | None = None,
        stock_status: StockStatus | None = None,
        lot_code: str | None = None,
        expiry_before: date | None = None,
    ) -> Sequence[dict[str, Any]]: ...

    async def post_movement(
        self,
        *,
        company_id: uuid.UUID,
        idempotency_key: str,
        movement_type: str,
        source_reference: str | None,
        lines: list[dict[str, Any]],
        actor_id: uuid.UUID,
        reservation_id: uuid.UUID | None = None,
    ) -> dict[str, Any]: ...

    async def capacity_summary(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID | None = None,
    ) -> dict[str, Any]: ...

    async def create_operational_override(
        self,
        *,
        company_id: uuid.UUID,
        location_id: uuid.UUID,
        reason: str,
        valid_until: datetime,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]: ...

    async def revoke_operational_override(
        self,
        *,
        company_id: uuid.UUID,
        override_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]: ...
