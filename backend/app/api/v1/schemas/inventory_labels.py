"""HTTP contracts for inventory label previews and print history."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from app.api.v1.schemas.common import ORMOut
from app.api.v1.schemas.inventory import StrictModel
from app.domain.entities.inventory_label import LabelPrintLayout


class InventoryLabelLayoutIn(StrictModel):
    content: Literal["full", "qr", "barcode"]
    width_mm: int = Field(ge=25, le=200, strict=True)
    height_mm: int = Field(ge=20, le=200, strict=True)

    @model_validator(mode="after")
    def validate_layout(self) -> InventoryLabelLayoutIn:
        self.to_domain()
        return self

    def to_domain(self) -> LabelPrintLayout:
        return LabelPrintLayout(**self.model_dump())


class InventoryLabelTargetIn(StrictModel):
    """One receipted lot detail or one physical handling unit."""

    inventory_lot_detail_id: uuid.UUID | None = None
    handling_unit_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def require_one_target(self) -> InventoryLabelTargetIn:
        if (self.inventory_lot_detail_id is None) == (self.handling_unit_id is None):
            raise ValueError("Seleccione un detalle de lote o una unidad logística.")
        return self


class InventoryLabelPreviewIn(InventoryLabelTargetIn):
    pass


class InventoryLabelPreviewOut(StrictModel):
    inventory_lot_id: uuid.UUID
    inventory_lot_detail_id: uuid.UUID | None
    handling_unit_id: uuid.UUID | None
    handling_unit_code: str | None
    inventory_item_id: uuid.UUID
    product_internal_code: str
    product_name: str
    receipt_lot_code: str
    receipt_lot_header_code: str | None
    manufacturer_lot_code: str | None
    received_on: date
    quantity_base: Decimal
    base_unit_symbol: str
    expiry_date: date | None
    stock_status: str
    print_count: int
    has_initial_print: bool
    label_revision: int | None
    label_print_id: uuid.UUID | None
    label_confirmation_required: bool
    label_confirmed: bool
    presentation_equivalence: str | None


class InventoryLabelPrintIn(InventoryLabelTargetIn):
    idempotency_key: str = Field(min_length=8, max_length=120)
    quantity_printed: int = Field(ge=1, le=10000)
    print_date: date
    reason: Literal["initial", "reprint"]
    layout: InventoryLabelLayoutIn | None = None
    notes: str | None = Field(default=None, max_length=160)


class InventoryLabelPrintOut(ORMOut):
    id: uuid.UUID
    inventory_lot_id: uuid.UUID
    inventory_lot_detail_id: uuid.UUID | None
    handling_unit_id: uuid.UUID | None
    inventory_item_id: uuid.UUID
    quantity_printed: int
    print_date: date
    reason: Literal["initial", "reprint"]
    printed_by: uuid.UUID
    printed_at: datetime
    label_snapshot: dict[str, object]


class InventoryLabelConfirmationIn(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    handling_unit_id: uuid.UUID
    handling_unit_code: str = Field(min_length=1, max_length=120)
    label_print_id: uuid.UUID


class InventoryLabelConfirmationOut(ORMOut):
    id: uuid.UUID
    handling_unit_id: uuid.UUID
    label_print_id: uuid.UUID
    handling_unit_code: str
    label_revision: int
    quantity_base: Decimal
    label_fingerprint: str
    confirmed_by: uuid.UUID
    confirmed_at: datetime
