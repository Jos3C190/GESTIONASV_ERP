"""Persistence port and validation projections for purchase orders."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.domain.entities.actual_expense import ActualExpenseClosure, ActualPurchaseExpense
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
    consolidation_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class PurchaseOrderAwardReference:
    id: uuid.UUID
    purchase_quotation_detail_id: uuid.UUID
    supplier_id: int
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class PurchaseOrderDestinationReference:
    branch_id: uuid.UUID | None
    warehouse_id: uuid.UUID
    branch_is_active: bool | None
    branch_operational_status: str | None
    warehouse_is_active: bool
    warehouse_operational_status: str
    warehouse_storage_eligible: bool
    warehouse_is_central: bool = False


@dataclass(frozen=True, slots=True)
class PurchaseOrderExpenseTypeReference:
    id: uuid.UUID
    name: str
    description: str | None = None
    is_active: bool = True
    usage_count: int = 0


class PurchaseOrderRepository(Protocol):
    async def get_actual_expense_closure(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> ActualExpenseClosure | None: ...

    async def list_actual_expenses(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> tuple[ActualPurchaseExpense, ...]: ...

    async def add_actual_expense(self, expense: ActualPurchaseExpense) -> ActualPurchaseExpense: ...

    async def actual_expense_usage(
        self,
        company_id: uuid.UUID,
        expense_ids: tuple[uuid.UUID, ...],
        *,
        exclude_retaceo_id: uuid.UUID | None = None,
    ) -> dict[uuid.UUID, Decimal]: ...

    async def list_orders(
        self,
        company_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
        status: PurchaseOrderStatus | None = None,
        supplier_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseOrder], int]: ...

    async def get_order(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
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
        *,
        branch_id: uuid.UUID | None = None,
    ) -> PurchaseOrderQuotationReference | None: ...

    async def get_consolidation_status_for_update(
        self, company_id: uuid.UUID, consolidation_id: uuid.UUID
    ) -> str | None: ...

    async def list_active_awards_for_quotation_for_update(
        self,
        company_id: uuid.UUID,
        consolidation_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> tuple[PurchaseOrderAwardReference, ...]: ...

    async def get_ordered_award_quantities(
        self,
        company_id: uuid.UUID,
        award_ids: tuple[uuid.UUID, ...],
        *,
        exclude_order_id: uuid.UUID | None = None,
    ) -> dict[uuid.UUID, Decimal]: ...

    async def get_destination_reference(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        warehouse_id: uuid.UUID,
    ) -> PurchaseOrderDestinationReference | None: ...

    async def list_active_expense_types(
        self,
        company_id: uuid.UUID,
    ) -> tuple[PurchaseOrderExpenseTypeReference, ...]: ...

    async def list_expense_type_catalog(
        self,
        company_id: uuid.UUID,
    ) -> tuple[PurchaseOrderExpenseTypeReference, ...]: ...

    async def create_expense_type(
        self,
        company_id: uuid.UUID,
        name: str,
        description: str | None,
    ) -> PurchaseOrderExpenseTypeReference: ...

    async def get_expense_type(
        self,
        company_id: uuid.UUID,
        expense_type_id: uuid.UUID,
    ) -> PurchaseOrderExpenseTypeReference | None: ...

    async def update_expense_type(
        self,
        company_id: uuid.UUID,
        expense_type_id: uuid.UUID,
        *,
        name: str,
        description: str | None,
        is_active: bool,
    ) -> PurchaseOrderExpenseTypeReference | None: ...

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
