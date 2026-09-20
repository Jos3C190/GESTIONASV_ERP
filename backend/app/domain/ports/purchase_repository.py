"""Persistence port for supplier purchase receipts."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Protocol

from app.domain.entities.purchase import Purchase, PurchaseStatus
from app.domain.entities.purchase_order import PurchaseOrder, PurchaseOrderStatus


class PurchaseOrderReceivingRepository(Protocol):
    async def get_order(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> PurchaseOrder | None: ...

    async def get_order_for_update(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
    ) -> PurchaseOrder | None: ...

    async def update_status(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        status: PurchaseOrderStatus,
    ) -> PurchaseOrder | None: ...


class PurchaseRepository(Protocol):
    async def list_purchases(
        self,
        company_id: uuid.UUID,
        *,
        status: PurchaseStatus | None = None,
        supplier_id: int | None = None,
        purchase_order_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Purchase], int]: ...

    async def get_purchase(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
    ) -> Purchase | None: ...

    async def get_purchase_for_update(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
    ) -> Purchase | None: ...

    async def allocate_next_code(self, company_id: uuid.UUID) -> str: ...

    async def get_received_quantities(
        self,
        company_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        *,
        exclude_purchase_id: uuid.UUID | None = None,
    ) -> dict[uuid.UUID, Decimal]: ...

    async def add_purchase(self, purchase: Purchase) -> Purchase: ...

    async def replace_draft(self, purchase: Purchase) -> Purchase | None: ...

    async def update_status(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
        status: PurchaseStatus,
    ) -> Purchase | None: ...
