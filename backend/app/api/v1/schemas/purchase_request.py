"""Pydantic DTOs for the purchase-request API."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.common import ORMOut
from app.domain.entities.purchase_request import PurchaseRequestStatus


class PurchaseRequestDetailInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    description: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)


class PurchaseRequestWriteBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    required_date: datetime | None = None
    justification: str = Field(min_length=1, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)
    details: tuple[PurchaseRequestDetailInput, ...] = Field(min_length=1, max_length=100)


class PurchaseRequestCreate(PurchaseRequestWriteBase):
    pass


class PurchaseRequestUpdate(PurchaseRequestWriteBase):
    pass


class PurchaseRequestDetailResponse(ORMOut):
    id: uuid.UUID
    purchase_request_id: uuid.UUID
    product_id: int
    unit_id: int
    quantity: Decimal
    description: str | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseRequestResponse(ORMOut):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    requested_by_id: uuid.UUID
    request_date: datetime
    required_date: datetime | None = None
    justification: str
    status: PurchaseRequestStatus
    notes: str | None = None
    details: tuple[PurchaseRequestDetailResponse, ...]
    created_at: datetime | None = None
    updated_at: datetime | None = None


__all__ = [
    "PurchaseRequestCreate",
    "PurchaseRequestDetailInput",
    "PurchaseRequestDetailResponse",
    "PurchaseRequestResponse",
    "PurchaseRequestUpdate",
]
