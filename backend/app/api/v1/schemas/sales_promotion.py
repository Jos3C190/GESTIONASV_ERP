"""DTOs de las promociones por sucursal (pedido del ingeniero, 24/11/2026)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PromotionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: uuid.UUID
    product_id: int = Field(ge=1)
    discount_percent: Decimal = Field(gt=0, lt=100, max_digits=5, decimal_places=2)
    valid_from: date | None = None
    """Si falta, rige desde hoy."""
    valid_to: date | None = None
    notes: str | None = Field(default=None, max_length=200)


class PromotionOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str | None
    product_id: int
    product_name: str | None
    product_sku: str | None
    discount_percent: Decimal
    valid_from: date
    valid_to: date | None
    notes: str | None
    status: Literal["current", "scheduled", "expired", "ended"]
