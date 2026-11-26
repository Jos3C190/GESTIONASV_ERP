"""DTOs de los libros de IVA, los anexos del F-07 y el documento del proveedor en una compra."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class IssuerOut(BaseModel):
    name: str
    nit: str | None
    nrc: str | None


class SummaryOut(BaseModel):
    contributor_taxed: Decimal
    contributor_vat: Decimal
    consumer_taxed_with_vat: Decimal
    consumer_vat: Decimal
    exempt_sales: Decimal
    not_subject_sales: Decimal
    debit: Decimal
    purchase_taxed: Decimal
    credit: Decimal
    perception_collected: Decimal
    balance: Decimal


class ContributorLineOut(BaseModel):
    number: int
    issued_on: date
    document_type: str
    generation_code: str
    control_number: str
    customer: str
    registry: str
    exempt: Decimal
    not_subject: Decimal
    taxed: Decimal
    vat: Decimal
    perception: Decimal
    total: Decimal


class ConsumerLineOut(BaseModel):
    day: date
    first_control: str
    last_control: str
    point_of_sale: str
    exempt: Decimal
    not_subject: Decimal
    taxed: Decimal
    exports: Decimal
    total: Decimal
    third_parties: Decimal
    note: str


class PurchaseLineOut(BaseModel):
    number: int
    issued_on: date
    document_type: str
    document_number: str
    registry: str
    excluded_subject_id: str
    supplier: str
    internal_exempt: Decimal
    import_exempt: Decimal
    internal_taxed: Decimal
    import_taxed: Decimal
    vat: Decimal
    perception: Decimal
    total: Decimal
    third_party_withholding: Decimal
    excluded_subjects: Decimal


class AnnexOut(BaseModel):
    key: str
    title: str
    file_name: str
    rows: list[list[str]]


class PendingPurchaseOut(BaseModel):
    id: uuid.UUID
    code: str
    supplier: str
    invoice_number: str | None
    invoice_date: date | None
    total: Decimal


class FiscalMonthOut(BaseModel):
    period: str
    label: str
    mode: str
    modes: list[str]
    issuer: IssuerOut
    warnings: list[str]
    summary: SummaryOut
    contributor_book: list[ContributorLineOut]
    consumer_book: list[ConsumerLineOut]
    purchase_book: list[PurchaseLineOut]
    annexes: list[AnnexOut]
    pending_purchases: list[PendingPurchaseOut]


class RentaPurchaseIn(BaseModel):
    operation: int
    classification: int
    sector: int
    cost_type: int


class RentaPurchaseOut(RentaPurchaseIn):
    pass


class PurchaseFiscalIn(BaseModel):
    issued_on: date
    document_class: Literal[1, 3, 4]
    document_type: Literal["03", "05", "06", "12", "13"]
    number: str = Field(min_length=1, max_length=100)
    control_number: str | None = Field(default=None, max_length=31)
    seal: str | None = Field(default=None, max_length=100)
    supplier_name: str = Field(min_length=1, max_length=250)
    supplier_id_type: Literal["nit", "nrc", "dui"]
    supplier_id: str = Field(min_length=1, max_length=20)
    renta: RentaPurchaseIn


class PurchaseFiscalOut(BaseModel):
    id: uuid.UUID
    code: str
    status: str
    supplier_name: str
    supplier_ids: dict[str, str]
    invoice_number: str | None
    invoice_date: date | None
    exempt: Decimal
    taxed: Decimal
    vat: Decimal
    recorded: PurchaseFiscalIn | None
    recorded_at: datetime | None
    renta_defaults: RentaPurchaseOut


class PeriodCloseOut(BaseModel):
    id: uuid.UUID
    status: Literal["closed", "reopened"]
    summary: dict[str, str]
    closed_by: str | None
    closed_at: datetime
    reopen_reason: str | None
    reopened_by: str | None
    reopened_at: datetime | None


class PeriodStatusOut(BaseModel):
    period: str
    label: str
    closed: PeriodCloseOut | None
    history: list[PeriodCloseOut]
    blockers: list[str]


class PeriodReopenIn(BaseModel):
    reason: str = Field(min_length=10, max_length=500)
