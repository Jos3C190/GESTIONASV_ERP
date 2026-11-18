"""DTOs del documento fiscal del pedido (bloque V3b)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FiscalStatus = Literal[
    "pending", "contingency", "issued", "simulated", "rejected", "failed", "invalidated"
]


class InvoiceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point_of_sale_id: uuid.UUID | None = None


class FiscalDocumentOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID
    sale_id: uuid.UUID
    sale_code: str | None
    customer_name: str | None
    customer_email: str | None
    establishment_code: str | None
    point_of_sale_code: str | None
    document_type: Literal["01", "03"]
    mode: str
    status: FiscalStatus
    generation_code: uuid.UUID | None
    control_number: str | None
    total: Decimal
    seal: str | None
    attempts: int
    error_code: str | None
    error_message: str | None
    has_json: bool
    has_pdf: bool
    issued_at: datetime | None
    contingency_type: int | None = None
    contingency_reason: str | None = None
    contingency_at: datetime | None = None
    replaces_document_id: uuid.UUID | None = None
    superseded_by_id: uuid.UUID | None = None
    created_at: datetime | None
    updated_at: datetime | None


class FiscalDocumentPage(BaseModel):
    items: list[FiscalDocumentOut]
    page: int
    size: int
    total: int
    pages: int


class PointOfSaleOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class InvoiceOptionsOut(BaseModel):
    document_type: str
    mode: str
    establishment_code: str | None
    points_of_sale: list[PointOfSaleOut]
    blockers: list[str]
    document: FiscalDocumentOut | None


class DownloadUrlOut(BaseModel):
    url: str


class FiscalEmailIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipients: list[str] | None = Field(default=None, max_length=10)
    """Vacío: el correo de la ficha del cliente."""


class FiscalEmailOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    recipients: list[str]
    origin: Literal["auto", "manual"]
    status: Literal["pending", "sent", "failed"]
    attempts: int
    error_code: str | None
    error_message: str | None
    requested_by_name: str | None
    sent_at: datetime | None
    created_at: datetime | None


class FiscalEmailHistoryOut(BaseModel):
    enabled: bool
    """Si el servidor tiene configurado el correo saliente."""
    customer_email: str | None
    items: list[FiscalEmailOut]
