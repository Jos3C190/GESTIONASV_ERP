"""Pydantic DTOs for purchase quotations and supplier offer comparison."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.common import ORMOut
from app.domain.entities.purchase_quotation import PurchaseQuotationStatus


class PurchaseQuotationRequestLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    purchase_request_detail_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)


class PurchaseQuotationRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    purchase_request_id: uuid.UUID
    lines: tuple[PurchaseQuotationRequestLineInput, ...] = Field(min_length=1, max_length=100)


class PurchaseQuotationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    supplier_id: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    requests: tuple[PurchaseQuotationRequestInput, ...] = Field(min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=4000)


class PurchaseQuotationResponseLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: int = Field(gt=0)
    unit_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    discount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=6)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=9, decimal_places=6)
    delivery_days: int | None = Field(default=None, ge=0)
    available_quantity: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=18,
        decimal_places=6,
    )
    notes: str | None = Field(default=None, max_length=2000)


class PurchaseQuotationExpenseInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expense_type_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    description: str | None = Field(default=None, max_length=1000)


class PurchaseQuotationRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    quotation_date: datetime
    valid_until: datetime | None = None
    payment_terms: str | None = Field(default=None, max_length=4000)
    delivery_days: int | None = Field(default=None, ge=0)
    lines: tuple[PurchaseQuotationResponseLineInput, ...] = Field(min_length=1, max_length=200)
    expenses: tuple[PurchaseQuotationExpenseInput, ...] = Field(default=(), max_length=50)
    notes: str | None = Field(default=None, max_length=4000)


class PurchaseQuotationRequestDetailResponse(ORMOut):
    id: uuid.UUID
    purchase_quotation_request_id: uuid.UUID
    purchase_quotation_detail_id: uuid.UUID
    purchase_request_detail_id: uuid.UUID
    quantity: Decimal
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseQuotationRequestResponse(ORMOut):
    id: uuid.UUID
    purchase_quotation_id: uuid.UUID
    purchase_request_id: uuid.UUID
    details: tuple[PurchaseQuotationRequestDetailResponse, ...]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseQuotationDetailResponse(ORMOut):
    id: uuid.UUID
    purchase_quotation_id: uuid.UUID
    product_id: int
    unit_id: int
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total: Decimal
    delivery_days: int | None = None
    available_quantity: Decimal | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseQuotationExpenseResponse(ORMOut):
    id: uuid.UUID
    purchase_quotation_id: uuid.UUID
    expense_type_id: uuid.UUID
    amount: Decimal
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseQuotationResponse(ORMOut):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    supplier_id: int
    quotation_date: datetime
    currency: str
    created_by_id: uuid.UUID
    request_links: tuple[PurchaseQuotationRequestResponse, ...]
    details: tuple[PurchaseQuotationDetailResponse, ...]
    expenses: tuple[PurchaseQuotationExpenseResponse, ...]
    valid_until: datetime | None = None
    payment_terms: str | None = None
    delivery_days: int | None = None
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    status: PurchaseQuotationStatus
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseQuotationComparisonResponse(ORMOut):
    quotation_id: uuid.UUID
    code: str
    supplier_id: int
    currency: str
    total: Decimal
    delivery_days: int | None = None
    valid_until: datetime | None = None
    status: PurchaseQuotationStatus


__all__ = [
    "PurchaseQuotationComparisonResponse",
    "PurchaseQuotationCreate",
    "PurchaseQuotationDetailResponse",
    "PurchaseQuotationExpenseInput",
    "PurchaseQuotationExpenseResponse",
    "PurchaseQuotationRecordResponse",
    "PurchaseQuotationRequestDetailResponse",
    "PurchaseQuotationRequestInput",
    "PurchaseQuotationRequestLineInput",
    "PurchaseQuotationRequestResponse",
    "PurchaseQuotationResponse",
    "PurchaseQuotationResponseLineInput",
]
