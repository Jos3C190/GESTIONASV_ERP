"""DTOs de cuentas por cobrar y recibos de cobro (V5a)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Method = Literal["cash", "card", "transfer", "check", "other"]
Bucket = Literal["current", "1_30", "31_60", "61_90", "over_90"]


class CustomerRefOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    credit_days: int
    credit_limit: Decimal | None


class CustomerSummaryOut(BaseModel):
    customer: CustomerRefOut
    balance: Decimal
    overdue: Decimal
    credit: Decimal
    aging: dict[Bucket, Decimal]
    oldest_due: date | None


class CertificateIn(BaseModel):
    certificate_number: str = Field(min_length=1, max_length=100)
    issued_on: date
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class CertificateOut(CertificateIn):
    pass


class AccountDocumentOut(BaseModel):
    id: uuid.UUID
    document_type: str
    control_number: str
    issued_on: date
    due_on: date
    payable: Decimal
    credited: Decimal
    applied: Decimal
    balance: Decimal
    bucket: Bucket
    overdue: bool
    invalidated: bool
    sale_id: uuid.UUID
    sale_code: str
    customer_id: uuid.UUID
    withholding: Decimal
    certificate: CertificateOut | None


class PaymentIn(BaseModel):
    method: Method
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    reference: str | None = Field(default=None, max_length=100)


class ApplicationIn(BaseModel):
    document_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class ApplicationOut(BaseModel):
    document_id: uuid.UUID
    control_number: str
    amount: Decimal
    applied_on: date
    document_invalidated: bool


class ReceiptIn(BaseModel):
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    received_on: date
    payments: list[PaymentIn] = Field(min_length=1, max_length=10)
    applications: list[ApplicationIn] = Field(default_factory=list, max_length=50)
    notes: str | None = Field(default=None, max_length=300)
    idempotency_key: str = Field(min_length=8, max_length=120)


class ApplyIn(BaseModel):
    applications: list[ApplicationIn] = Field(min_length=1, max_length=50)


class AnnulReceiptIn(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


class ReceiptOut(BaseModel):
    id: uuid.UUID
    code: str
    number: int
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    received_on: date
    total: Decimal
    unapplied: Decimal
    notes: str | None
    status: Literal["issued", "annulled"]
    payments: list[PaymentIn]
    applications: list[ApplicationOut]
    annul_reason: str | None
    annulled_at: datetime | None
    created_at: datetime | None


class AccountOut(BaseModel):
    customer: CustomerRefOut
    balance: Decimal
    overdue: Decimal
    credit: Decimal
    aging: dict[Bucket, Decimal]
    documents: list[AccountDocumentOut]
    receipts: list[ReceiptOut]
