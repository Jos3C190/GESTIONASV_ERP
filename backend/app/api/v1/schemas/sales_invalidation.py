"""DTOs de la invalidación y la corrección de documentos fiscales (bloque V4b)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.api.v1.schemas.sales_invoice import FiscalDocumentOut


class PersonIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    document_type: str = Field(min_length=2, max_length=2)
    document_number: str = Field(min_length=1, max_length=25)


class PersonOut(BaseModel):
    name: str
    document_type: str
    document_number: str


class InvalidateIn(BaseModel):
    reason: str = Field(min_length=1, max_length=200)
    requester: PersonIn
    cancel_order: bool = False


class CorrectIn(BaseModel):
    requester: PersonIn


class InvalidationOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    kind: Literal[1, 2]
    reason: str | None
    requester: PersonOut
    responsible: PersonOut | None
    replacement_document_id: uuid.UUID | None
    cancel_order: bool
    status: Literal["pending", "accepted", "rejected", "failed"]
    attempts: int
    event_generation_code: uuid.UUID | None
    event_seal: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime | None
    resolved_at: datetime | None


class InvalidationOverviewOut(BaseModel):
    deadline: date | None
    expired: bool
    estimated: bool
    history: list[InvalidationOut]


class CorrectionOut(BaseModel):
    replacement: FiscalDocumentOut
    invalidation: InvalidationOut
