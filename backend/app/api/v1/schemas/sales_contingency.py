"""DTOs de la contingencia de facturación (bloque V4a)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ContingencyDocumentsOut(BaseModel):
    total: int
    in_contingency: int
    pending_transmission: int
    transmitted: int
    rejected: int


class ContingencyWindowOut(BaseModel):
    id: int
    establishment_code: str | None
    branch_name: str | None
    status: str
    contingency_type: int
    contingency_label: str
    reason: str | None
    forced: bool
    started_at: datetime
    ended_at: datetime | None
    documents: ContingencyDocumentsOut
    event_status: str | None
    event_seal: str | None
    event_sealed_at: datetime | None
    event_deadline: datetime | None
    event_overdue: bool
    transmission_deadline: datetime | None
    transmission_overdue: bool
    last_error: str | None


class ContingencyResponsibleOut(BaseModel):
    name: str
    document_type: str
    document_number: str


class ContingencyOverviewOut(BaseModel):
    windows: list[ContingencyWindowOut]
    responsible: ContingencyResponsibleOut | None
    active: bool


class ContingencyActivateIn(BaseModel):
    establishment_id: uuid.UUID
    contingency_type: int = Field(ge=1, le=5)
    reason: str | None = Field(default=None, max_length=500)


class ContingencyResponsibleIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    document_type: str = Field(min_length=2, max_length=2)
    document_number: str = Field(min_length=1, max_length=25)
