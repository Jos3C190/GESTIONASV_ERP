"""Pydantic DTOs for retaceo landed-cost allocations."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.common import ORMOut
from app.domain.entities.retaceo import RetaceoStatus


class RetaceoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    purchase_id: uuid.UUID
    total_freight: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    total_expenses: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    total_dai: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    import_vat: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    notes: str | None = Field(default=None, max_length=4000)


class RetaceoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    total_freight: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    total_expenses: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    total_dai: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    import_vat: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    notes: str | None = Field(default=None, max_length=4000)


class RetaceoDetailResponse(ORMOut):
    id: uuid.UUID
    retaceo_id: uuid.UUID
    purchase_detail_id: uuid.UUID
    product_id: int
    unit_id: int
    quantity: Decimal
    cost_fob: Decimal
    freight: Decimal
    expenses: Decimal
    dai: Decimal
    total_cost: Decimal
    unit_cost: Decimal
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RetaceoResponse(ORMOut):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    purchase_id: uuid.UUID
    branch_id: uuid.UUID
    created_by_id: uuid.UUID
    currency: str
    details: tuple[RetaceoDetailResponse, ...]
    total_fob: Decimal
    total_freight: Decimal
    total_expenses: Decimal
    total_dai: Decimal
    import_vat: Decimal
    total_cost: Decimal
    freight_percentage: Decimal
    expense_percentage: Decimal
    dai_percentage: Decimal
    status: RetaceoStatus
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


__all__ = [
    "RetaceoCreate",
    "RetaceoDetailResponse",
    "RetaceoResponse",
    "RetaceoUpdate",
]
