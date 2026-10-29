"""Schemas for branch product-demand history and classification."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BranchDemandLevel = Literal["low", "medium", "high"]


class BranchDemandUnitTotal(BaseModel):
    unit_id: int
    unit_name: str
    unit_symbol: str
    quantity: Decimal


class BranchProductDemandItem(BaseModel):
    product_id: int
    sku: str
    product_name: str
    request_count: int
    last_requested_at: datetime
    unit_totals: list[BranchDemandUnitTotal]
    demand_level: BranchDemandLevel | None = None


class BranchProductDemandResponse(BaseModel):
    branch_id: uuid.UUID
    period_start: date
    period_end: date
    items: list[BranchProductDemandItem]


class BranchProductDemandLevelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: BranchDemandLevel | None = Field(
        description="Clasificación manual de demanda; null quita la clasificación."
    )


class BranchProductDemandLevelResponse(BaseModel):
    branch_id: uuid.UUID
    product_id: int
    level: BranchDemandLevel | None
    updated_at: datetime | None = None
