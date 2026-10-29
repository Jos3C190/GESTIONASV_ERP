"""Pydantic DTOs for supplier purchase receipts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.common import ORMOut
from app.domain.entities.purchase import PurchaseInventoryWorkflow, PurchaseStatus
from app.domain.entities.purchase_conversion import PurchaseValuationConversion
from app.domain.entities.purchase_order import PurchaseOrderStatus


class PurchaseValuationConversionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, from_attributes=True)

    currency: str = Field(pattern=r"^[A-Z]{3}$")
    rate: Decimal = Field(gt=0, lt=Decimal("1e12"), max_digits=24, decimal_places=12)
    effective_date: date
    reference: str = Field(min_length=3, max_length=500)

    def to_domain(self) -> PurchaseValuationConversion:
        return PurchaseValuationConversion(**self.model_dump())


class PurchaseValuationContext(BaseModel):
    receipt_currency: str
    valuation_currency: str | None


class PurchaseReceiptReadinessResponse(ORMOut):
    required: bool
    ready: bool
    retaceo_id: uuid.UUID | None = None
    retaceo_code: str | None = None
    retaceo_status: str | None = None


class PurchaseVerificationLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purchase_detail_id: uuid.UUID
    quantity_accepted: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    inventory_location_id: uuid.UUID | None = None


class PurchaseVerify(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: tuple[PurchaseVerificationLineInput, ...] = Field(min_length=1, max_length=200)
    valuation_conversion: PurchaseValuationConversionInput | None = None


class PurchaseLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purchase_order_detail_id: uuid.UUID
    quantity_received: Decimal = Field(gt=0, max_digits=18, decimal_places=6)


class PurchaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    purchase_order_id: uuid.UUID
    supplier_invoice_number: str | None = Field(default=None, max_length=80)
    supplier_invoice_date: date | None = None
    lines: tuple[PurchaseLineInput, ...] = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)


class PurchaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    supplier_invoice_number: str | None = Field(default=None, max_length=80)
    supplier_invoice_date: date | None = None
    lines: tuple[PurchaseLineInput, ...] = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)


class PurchaseDetailResponse(ORMOut):
    id: uuid.UUID
    purchase_id: uuid.UUID
    purchase_order_detail_id: uuid.UUID
    product_id: int
    quantity_ordered: Decimal
    quantity_received: Decimal
    quantity_accepted: Decimal | None = None
    quantity_rejected: Decimal | None = None
    unit_id: int
    inventory_location_id: uuid.UUID | None = None
    unit_price: Decimal
    discount: Decimal
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total: Decimal
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseResponse(ORMOut):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    purchase_order_id: uuid.UUID
    supplier_id: int
    branch_id: uuid.UUID | None = None
    warehouse_id: uuid.UUID
    created_by_id: uuid.UUID
    purchase_date: datetime
    supplier_invoice_number: str | None = None
    supplier_invoice_date: date | None = None
    currency: str
    valuation_conversion: PurchaseValuationConversionInput | None = None
    details: tuple[PurchaseDetailResponse, ...]
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    status: PurchaseStatus
    inventory_workflow: PurchaseInventoryWorkflow
    inventory_movement_id: uuid.UUID | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseReceivableLineResponse(BaseModel):
    purchase_order_detail_id: uuid.UUID
    product_id: int
    unit_id: int
    quantity_ordered: Decimal
    quantity_received: Decimal
    quantity_pending: Decimal
    unit_price: Decimal
    discount: Decimal
    tax_rate: Decimal
    notes: str | None = None


class PurchaseReceivableResponse(BaseModel):
    purchase_order_id: uuid.UUID
    code: str
    status: PurchaseOrderStatus
    supplier_id: int
    branch_id: uuid.UUID | None = None
    warehouse_id: uuid.UUID
    currency: str
    lines: tuple[PurchaseReceivableLineResponse, ...]


__all__ = [
    "PurchaseCreate",
    "PurchaseDetailResponse",
    "PurchaseLineInput",
    "PurchaseReceivableLineResponse",
    "PurchaseReceivableResponse",
    "PurchaseResponse",
    "PurchaseUpdate",
    "PurchaseValuationContext",
    "PurchaseValuationConversionInput",
    "PurchaseVerificationLineInput",
    "PurchaseVerify",
]
