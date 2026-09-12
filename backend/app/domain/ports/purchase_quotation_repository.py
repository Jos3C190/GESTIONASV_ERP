"""Persistence port and validation projections for purchase quotations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.domain.entities.purchase_quotation import PurchaseQuotation, PurchaseQuotationStatus
from app.domain.entities.purchase_request import PurchaseRequestStatus


@dataclass(frozen=True, slots=True)
class PurchaseQuotationSupplierReference:
    supplier_id: int
    is_active: bool
    supplier_status: str


@dataclass(frozen=True, slots=True)
class PurchaseQuotationRequestDetailReference:
    id: uuid.UUID
    product_id: int
    unit_id: int
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class PurchaseQuotationRequestReference:
    id: uuid.UUID
    status: PurchaseRequestStatus
    details: tuple[PurchaseQuotationRequestDetailReference, ...]


@dataclass(frozen=True, slots=True)
class PurchaseQuotationCoverageReference:
    purchase_request_id: uuid.UUID
    purchase_request_detail_id: uuid.UUID
    product_id: int
    unit_id: int
    quantity: Decimal


class PurchaseQuotationRepository(Protocol):
    async def list_quotations(
        self,
        company_id: uuid.UUID,
        *,
        status: PurchaseQuotationStatus | None = None,
        supplier_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseQuotation], int]: ...

    async def get_quotation(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> PurchaseQuotation | None: ...

    async def get_quotation_for_update(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> PurchaseQuotation | None: ...

    async def allocate_next_code(self, company_id: uuid.UUID) -> str: ...

    async def get_supplier_reference(
        self,
        company_id: uuid.UUID,
        supplier_id: int,
    ) -> PurchaseQuotationSupplierReference | None: ...

    async def is_currency_active(self, currency: str) -> bool: ...

    async def get_request_reference(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> PurchaseQuotationRequestReference | None: ...

    async def is_expense_type_active(
        self,
        company_id: uuid.UUID,
        expense_type_id: uuid.UUID,
    ) -> bool: ...

    async def get_coverage_references(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
    ) -> tuple[PurchaseQuotationCoverageReference, ...]: ...

    async def add_quotation(self, quotation: PurchaseQuotation) -> PurchaseQuotation: ...

    async def replace_response(self, quotation: PurchaseQuotation) -> PurchaseQuotation | None: ...

    async def update_status(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        status: PurchaseQuotationStatus,
    ) -> PurchaseQuotation | None: ...

    async def list_comparable(
        self,
        company_id: uuid.UUID,
        purchase_request_id: uuid.UUID,
    ) -> list[PurchaseQuotation]: ...

    async def advance_purchase_request_quotation_statuses(
        self,
        company_id: uuid.UUID,
        request_ids: tuple[uuid.UUID, ...],
    ) -> None: ...
