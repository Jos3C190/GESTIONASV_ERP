"""DTOs del evento de retorno sobre una factura (bloque V4d2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.sales_invalidation import PersonIn, PersonOut
from app.api.v1.schemas.sales_note import CcfLineOut

ReturnStatus = Literal["pending", "issued", "simulated", "rejected", "failed", "invalidated"]
AnnulStatus = Literal["pending", "accepted", "rejected", "failed"]


class ReturnLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_line_number: int = Field(ge=1)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)


class ReturnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=5, max_length=300)
    lines: list[ReturnLineIn] = Field(min_length=1, max_length=2000)


class AnnulReturnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requester: PersonIn


class ReturnLineOut(BaseModel):
    line_number: int
    invoice_line_number: int
    nature: Literal["taxed", "exempt", "not_subject"]
    description: str
    quantity: Decimal
    amount: Decimal
    vat: Decimal


class FiscalReturnOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    reason: str
    status: ReturnStatus
    total: Decimal
    generation_code: uuid.UUID | None
    seal: str | None
    error_code: str | None
    error_message: str | None
    issued_at: datetime | None
    has_json: bool
    lines: list[ReturnLineOut]
    annul_status: AnnulStatus | None
    annul_requester: PersonOut | None
    annul_seal: str | None
    annul_error_code: str | None
    annul_error_message: str | None
    annulled_at: datetime | None
    created_at: datetime | None


class ReturnsOverviewOut(BaseModel):
    invoice_id: uuid.UUID
    deadline: date | None
    withholding: bool
    blocker: str | None
    lines: list[CcfLineOut]
    returns: list[FiscalReturnOut]
