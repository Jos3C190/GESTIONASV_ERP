"""Pydantic DTOs for supplier purchase receipts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.common import ORMOut
from app.domain.entities.purchase import PurchaseStatus
from app.domain.entities.purchase_order import PurchaseOrderStatus


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
    unit_id: int
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
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    created_by_id: uuid.UUID
    purchase_date: datetime
    supplier_invoice_number: str | None = None
    supplier_invoice_date: date | None = None
    currency: str
    details: tuple[PurchaseDetailResponse, ...]
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    status: PurchaseStatus
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
    branch_id: uuid.UUID
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
]
