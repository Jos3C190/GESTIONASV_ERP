"""Pydantic DTOs for purchase orders."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.api.v1.schemas.common import ORMOut
from app.domain.entities.purchase_order import PurchaseOrderStatus


class PurchaseOrderLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    purchase_quotation_detail_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)


class PurchaseOrderExpenseInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expense_type_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    description: str | None = Field(default=None, max_length=1000)


class PurchaseOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    purchase_quotation_id: uuid.UUID
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    expected_date: AwareDatetime | None = None
    lines: tuple[PurchaseOrderLineInput, ...] = Field(min_length=1, max_length=200)
    expenses: tuple[PurchaseOrderExpenseInput, ...] = Field(default=(), max_length=50)
    notes: str | None = Field(default=None, max_length=4000)


class PurchaseOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    expected_date: AwareDatetime | None = None
    lines: tuple[PurchaseOrderLineInput, ...] = Field(min_length=1, max_length=200)
    expenses: tuple[PurchaseOrderExpenseInput, ...] = Field(default=(), max_length=50)
    notes: str | None = Field(default=None, max_length=4000)


class PurchaseOrderDetailResponse(ORMOut):
    id: uuid.UUID
    purchase_order_id: uuid.UUID
    purchase_quotation_detail_id: uuid.UUID
    product_id: int
    quantity: Decimal
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


class PurchaseOrderExpenseResponse(ORMOut):
    id: uuid.UUID
    purchase_order_id: uuid.UUID
    expense_type_id: uuid.UUID
    amount: Decimal
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseOrderResponse(ORMOut):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    supplier_id: int
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    purchase_quotation_id: uuid.UUID
    created_by_id: uuid.UUID
    order_date: datetime
    expected_date: datetime | None = None
    currency: str
    payment_terms: str | None = None
    details: tuple[PurchaseOrderDetailResponse, ...]
    expenses: tuple[PurchaseOrderExpenseResponse, ...]
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    additional_expenses: Decimal
    total: Decimal
    status: PurchaseOrderStatus
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseOrderExpenseDocumentInitiate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=160)
    size_bytes: int = Field(gt=0)
    checksum_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9A-Fa-f]{64}$",
    )


class PurchaseOrderExpenseDocumentResponse(ORMOut):
    id: uuid.UUID
    purchase_order_expense_id: uuid.UUID
    document_id: uuid.UUID
    file_name: str
    file_type: str
    size_bytes: int
    status: str
    failure_code: str | None = None
    uploaded_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseOrderExpenseDocumentUploadResponse(BaseModel):
    document: PurchaseOrderExpenseDocumentResponse
    upload_url: str
    method: Literal["PUT"] = "PUT"
    required_headers: dict[str, str]
    expires_at: datetime


__all__ = [
    "PurchaseOrderCreate",
    "PurchaseOrderDetailResponse",
    "PurchaseOrderExpenseDocumentInitiate",
    "PurchaseOrderExpenseDocumentResponse",
    "PurchaseOrderExpenseDocumentUploadResponse",
    "PurchaseOrderExpenseInput",
    "PurchaseOrderExpenseResponse",
    "PurchaseOrderLineInput",
    "PurchaseOrderResponse",
    "PurchaseOrderUpdate",
]
