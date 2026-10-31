from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from app.api.v1.schemas.inventory import StrictModel


class InventoryAdjustmentLineIn(StrictModel):
    inventory_item_id: uuid.UUID
    location_id: uuid.UUID
    direction: Literal["increase", "decrease"]
    quantity_base: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    stock_status: Literal["available", "quarantine", "damaged", "in_transit"] = "quarantine"
    inventory_lot_detail_id: uuid.UUID | None = None
    handling_unit_id: uuid.UUID | None = None
    packaging_definition_id: uuid.UUID | None = None
    documented_unit_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=24, decimal_places=6
    )
    documented_total_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=24, decimal_places=6
    )
    actual_gross_weight_kg: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=6
    )
    actual_volume_m3: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    transfer_detail_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_direction_fields(self) -> InventoryAdjustmentLineIn:
        if self.direction == "increase":
            self._validate_increase_fields()
        else:
            self._validate_decrease_fields()
        return self

    def _validate_increase_fields(self) -> None:
        if self.stock_status != "quarantine" or self.handling_unit_id or self.transfer_detail_id:
            raise ValueError("Un ajuste positivo crea una nueva unidad en cuarentena.")
        if self.documented_unit_cost is not None and self.documented_total_cost is not None:
            raise ValueError("Indique costo unitario o total, no ambos.")
        if (
            self.actual_gross_weight_kg is None
            and self.actual_volume_m3 is None
            and self.packaging_definition_id is None
        ):
            raise ValueError("Indique peso y volumen o una presentación física registrada.")
        if (self.actual_gross_weight_kg is None) != (self.actual_volume_m3 is None):
            raise ValueError("El peso y el volumen deben indicarse juntos.")

    def _validate_decrease_fields(self) -> None:
        if self.handling_unit_id is None:
            raise ValueError("Una salida requiere identificar la unidad logística existente.")
        if (
            self.packaging_definition_id
            or self.documented_unit_cost is not None
            or self.documented_total_cost is not None
        ):
            raise ValueError("Una salida utiliza la unidad y el costo promedio vigente.")
        if self.actual_gross_weight_kg is not None or self.actual_volume_m3 is not None:
            raise ValueError("Las medidas de una salida se derivan de su unidad logística.")
        if self.transfer_detail_id is not None and self.stock_status not in {
            "quarantine",
            "in_transit",
        }:
            raise ValueError("La pérdida de traslado debe declararse en tránsito.")
        if self.transfer_detail_id is None and self.stock_status == "in_transit":
            raise ValueError("El tránsito solo se ajusta desde una incidencia de traslado.")


class InventoryAdjustmentCreateIn(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    warehouse_id: uuid.UUID
    operational_date: date
    accounting_date: date
    reason: str = Field(min_length=5, max_length=4000)
    document_reference: str = Field(min_length=1, max_length=240)
    notes: str | None = Field(default=None, max_length=4000)
    correction_of_id: uuid.UUID | None = None
    transfer_id: uuid.UUID | None = None
    transfer_incident_id: uuid.UUID | None = None
    lines: list[InventoryAdjustmentLineIn] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_context(self) -> InventoryAdjustmentCreateIn:
        if (self.transfer_id is None) != (self.transfer_incident_id is None):
            raise ValueError("Traslado e incidencia deben indicarse juntos.")
        if self.transfer_id is not None and (
            len(self.lines) != 1
            or self.lines[0].direction != "decrease"
            or self.lines[0].transfer_detail_id is None
        ):
            raise ValueError(
                "Una pérdida documentada requiere una sola línea de salida vinculada al traslado."
            )
        if self.transfer_id is None and any(
            line.transfer_detail_id is not None for line in self.lines
        ):
            raise ValueError("La línea de traslado requiere una incidencia vinculada.")
        return self


class InventoryAdjustmentUpdateIn(StrictModel):
    operational_date: date
    accounting_date: date
    reason: str = Field(min_length=5, max_length=4000)
    document_reference: str = Field(min_length=1, max_length=240)
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[InventoryAdjustmentLineIn] = Field(min_length=1, max_length=100)
    approval_revocation_reason: str | None = Field(default=None, min_length=5, max_length=1000)


class InventoryAdjustmentApproveIn(StrictModel):
    expected_version: int = Field(ge=1)


class InventoryAdjustmentCancelIn(StrictModel):
    reason: str = Field(min_length=5, max_length=1000)


class InventoryAdjustmentApplyIn(StrictModel):
    idempotency_key: str = Field(min_length=8, max_length=120)


class InventoryAdjustmentCorrectionIn(StrictModel):
    operational_date: date
    accounting_date: date
    reason: str = Field(min_length=5, max_length=1000)
    document_reference: str = Field(min_length=1, max_length=240)


class InventoryAdjustmentDocumentInitiateIn(StrictModel):
    file_name: str = Field(min_length=1, max_length=500)
    content_type: str = Field(min_length=3, max_length=160)
    size_bytes: int = Field(gt=0)
    checksum_sha256: str = Field(min_length=64, max_length=64)


class InventoryAdjustmentOut(StrictModel):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    branch_id: uuid.UUID | None
    operational_date: date
    accounting_date: date
    reason: str
    document_reference: str
    notes: str | None
    status: Literal["draft", "approved", "applied", "cancelled"]
    version: int
    approved_version: int | None
    correction_of_id: uuid.UUID | None
    transfer_id: uuid.UUID | None
    transfer_incident_id: uuid.UUID | None
    created_by_id: uuid.UUID
    approved_by_id: uuid.UUID | None
    applied_by_id: uuid.UUID | None
    created_at: datetime
    approved_at: datetime | None
    applied_at: datetime | None
    cancellation_reason: str | None
    lines: list[dict[str, object]]
    documents: list[dict[str, object]]
    events: list[dict[str, object]]


class InventoryAdjustmentPage(StrictModel):
    items: list[InventoryAdjustmentOut]
    total: int


class InventoryAdjustmentItemOption(StrictModel):
    id: uuid.UUID
    product_name: str
    sku: str | None
    base_unit_id: int
    base_unit_name: str | None
    base_unit_symbol: str | None


class InventoryAdjustmentLocationOption(StrictModel):
    id: uuid.UUID
    code: str
    location_type: str


class InventoryAdjustmentOptions(StrictModel):
    items: list[InventoryAdjustmentItemOption]
    locations: list[InventoryAdjustmentLocationOption]
    items_total: int | None = None
