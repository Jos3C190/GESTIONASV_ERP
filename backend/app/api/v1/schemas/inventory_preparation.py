"""Warehouse projections deliberately contain no procurement or inventory costs."""

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.inventory import HandlingUnitOut


class PreparationUnitOut(HandlingUnitOut):
    inventory_lot_detail_id: uuid.UUID
    label_confirmed: bool
    phase: Literal["measure", "label", "place"]


class PreparationCommandIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=120)
    quantity_base: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    unit_scan: str = Field(min_length=1, max_length=700)


class PlacementCommandIn(PreparationCommandIn):
    location_scan: str = Field(min_length=1, max_length=120)


class PreparationActionOut(BaseModel):
    action: Literal["split", "place"]
    handling_unit_id: uuid.UUID
    prepared_unit_id: uuid.UUID
    quantity_base: Decimal
    movement_id: uuid.UUID | None = None
