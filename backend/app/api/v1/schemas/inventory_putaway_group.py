"""Contracts for one atomic group of quarantine putaway assignments."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PutawayGroupAllocationIn(StrictModel):
    handling_unit_id: uuid.UUID
    quantity_base: Decimal = Field(..., gt=0, max_digits=18, decimal_places=6)
    destination_location_id: uuid.UUID


class PutawayGroupConfirmIn(StrictModel):
    idempotency_key: str = Field(..., min_length=8, max_length=120)
    receipt_lot_id: uuid.UUID
    inventory_lot_detail_id: uuid.UUID
    inventory_item_id: uuid.UUID
    allocations: list[PutawayGroupAllocationIn] = Field(..., min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_allocations(self) -> PutawayGroupConfirmIn:
        seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for allocation in self.allocations:
            key = (allocation.handling_unit_id, allocation.destination_location_id)
            if key in seen:
                raise ValueError(
                    "Una unidad logística solo puede aparecer una vez por destino en el grupo."
                )
            seen.add(key)
        return self


class ConfirmedPutawayAllocationOut(BaseModel):
    inventory_lot_detail_id: uuid.UUID
    receipt_lot_detail_code: str
    source_handling_unit_id: uuid.UUID
    handling_unit_id: uuid.UUID
    handling_unit_code: str
    movement_id: uuid.UUID
    destination_location_id: uuid.UUID
    destination_location_code: str
    quantity_base: Decimal
    stock_status: Literal["available", "quarantine"]
    measurement_status: Literal["complete", "incomplete", "verified"]
    measurement_source: Literal["master", "receipt", "manual", "device", "split_estimate"]


class PutawayGroupConfirmOut(BaseModel):
    idempotency_key: str
    receipt_lot_id: uuid.UUID
    inventory_lot_detail_id: uuid.UUID
    receipt_lot_detail_code: str
    inventory_item_id: uuid.UUID
    total_quantity_base: Decimal
    allocations: list[ConfirmedPutawayAllocationOut]
    replayed: bool
