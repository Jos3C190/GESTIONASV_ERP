"""Pydantic DTOs for purchase quotations and supplier offer comparison."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

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


class PurchaseQuotationFromConsolidationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    supplier_id: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    consolidation_line_ids: tuple[uuid.UUID, ...] = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)


class PurchaseQuotationResponseLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    product_id: int = Field(gt=0)
    unit_id: int = Field(gt=0)
    offered_quantity: Decimal = Field(
        ge=0,
        max_digits=18,
        decimal_places=6,
        validation_alias=AliasChoices("offered_quantity", "quantity"),
    )
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
    lines: tuple[PurchaseQuotationResponseLineInput, ...] = Field(default=(), max_length=200)
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
    offered_quantity: Decimal | None = None
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


class PurchaseQuotationSourceSnapshotResponse(ORMOut):
    purchase_request_id: uuid.UUID
    purchase_request_detail_id: uuid.UUID
    request_code: str
    branch_name: str | None
    warehouse_name: str | None
    requester_name: str | None
    required_date: datetime | None
    included_quantity: Decimal


class PurchaseQuotationLineSnapshotResponse(ORMOut):
    purchase_quotation_detail_id: uuid.UUID
    consolidation_line_id: uuid.UUID
    product_sku: str
    product_name: str
    unit_name: str
    branch_quantity: Decimal
    central_quantity: Decimal
    sources: tuple[PurchaseQuotationSourceSnapshotResponse, ...]


class PurchaseQuotationDocumentInitiate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=160)
    size_bytes: int = Field(gt=0)
    checksum_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9A-Fa-f]{64}$")


class PurchaseQuotationDocumentResponse(ORMOut):
    id: uuid.UUID
    purchase_quotation_id: uuid.UUID
    document_id: uuid.UUID
    file_name: str
    file_type: str
    size_bytes: int
    status: str
    failure_code: str | None = None
    uploaded_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseQuotationDocumentUploadResponse(BaseModel):
    document: PurchaseQuotationDocumentResponse
    upload_url: str
    method: Literal["PUT"] = "PUT"
    required_headers: dict[str, str]
    expires_at: datetime


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
    response_notes: str | None = None
    consolidation_id: uuid.UUID | None = None
    consolidation_code: str | None = None
    version_number: int = 1
    sent_at: datetime | None = None
    snapshots: tuple[PurchaseQuotationLineSnapshotResponse, ...] = ()
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
    "PurchaseQuotationDocumentInitiate",
    "PurchaseQuotationDocumentResponse",
    "PurchaseQuotationDocumentUploadResponse",
    "PurchaseQuotationExpenseInput",
    "PurchaseQuotationExpenseResponse",
    "PurchaseQuotationFromConsolidationCreate",
    "PurchaseQuotationLineSnapshotResponse",
    "PurchaseQuotationRecordResponse",
    "PurchaseQuotationRequestDetailResponse",
    "PurchaseQuotationRequestInput",
    "PurchaseQuotationRequestLineInput",
    "PurchaseQuotationRequestResponse",
    "PurchaseQuotationResponse",
    "PurchaseQuotationResponseLineInput",
    "PurchaseQuotationSourceSnapshotResponse",
]
