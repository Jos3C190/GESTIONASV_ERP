"""Persistence port and validation projections for purchase orders."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.domain.entities.purchase_order import PurchaseOrder, PurchaseOrderStatus
from app.domain.entities.purchase_quotation import PurchaseQuotationStatus


@dataclass(frozen=True, slots=True)
class PurchaseOrderQuotationDetailReference:
    id: uuid.UUID
    product_id: int
    unit_id: int
    quantity: Decimal
    available_quantity: Decimal | None
    unit_price: Decimal
    discount: Decimal
    subtotal: Decimal
    tax_rate: Decimal
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class PurchaseOrderQuotationReference:
    id: uuid.UUID
    supplier_id: int
    currency: str
    payment_terms: str | None
    status: PurchaseQuotationStatus
    details: tuple[PurchaseOrderQuotationDetailReference, ...]


@dataclass(frozen=True, slots=True)
class PurchaseOrderDestinationReference:
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    branch_is_active: bool
    branch_operational_status: str
    warehouse_is_active: bool
    warehouse_operational_status: str
    warehouse_storage_eligible: bool


@dataclass(frozen=True, slots=True)
class PurchaseOrderExpenseTypeReference:
    id: uuid.UUID
    name: str
    description: str | None = None


class PurchaseOrderRepository(Protocol):
    async def list_orders(
        self,
        company_id: uuid.UUID,
        *,
        status: PurchaseOrderStatus | None = None,
        supplier_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseOrder], int]: ...

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

    async def allocate_next_code(self, company_id: uuid.UUID) -> str: ...

    async def get_quotation_reference_for_update(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> PurchaseOrderQuotationReference | None: ...

    async def get_destination_reference(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> PurchaseOrderDestinationReference | None: ...

    async def list_active_expense_types(
        self,
        company_id: uuid.UUID,
    ) -> tuple[PurchaseOrderExpenseTypeReference, ...]: ...

    async def is_expense_type_active(
        self,
        company_id: uuid.UUID,
        expense_type_id: uuid.UUID,
    ) -> bool: ...

    async def get_ordered_quantities(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        *,
        exclude_order_id: uuid.UUID | None = None,
    ) -> dict[uuid.UUID, Decimal]: ...

    async def add_order(self, order: PurchaseOrder) -> PurchaseOrder: ...

    async def replace_draft(self, order: PurchaseOrder) -> PurchaseOrder | None: ...

    async def update_status(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        status: PurchaseOrderStatus,
    ) -> PurchaseOrder | None: ...

    async def advance_purchase_request_order_statuses(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> None: ...
