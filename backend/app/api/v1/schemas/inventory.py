"""HTTP contracts for inventory, handling units and physical capacity."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.entities.inventory import (
    MeasurementSource,
    MeasurementStatus,
    PackagingType,
    PhysicalMeasures,
    ReservationStatus,
    StockStatus,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PhysicalMeasuresIn(StrictModel):
    gross_weight_kg: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)
    length_m: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)
    width_m: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)
    height_m: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)
    volume_m3: Decimal | None = Field(None, gt=0, max_digits=18, decimal_places=6)

    @model_validator(mode="after")
    def validate_dimensions(self) -> PhysicalMeasuresIn:
        self.to_domain().validate()
        return self

    def to_domain(self) -> PhysicalMeasures:
        return PhysicalMeasures(
            gross_weight_kg=self.gross_weight_kg,
            length_m=self.length_m,
            width_m=self.width_m,
            height_m=self.height_m,
            volume_m3=self.volume_m3,
        )


class InventoryItemCreate(StrictModel):
    product_id: int | None = Field(None, gt=0)
    variant_id: uuid.UUID | None = None
    base_unit_id: int = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_exact_target(self) -> InventoryItemCreate:
        if (self.product_id is None) == (self.variant_id is None):
            raise ValueError("Seleccione exactamente un producto independiente o una variante.")
        return self


class InventoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    product_id: int | None
    variant_id: uuid.UUID | None
    base_unit_id: int
    is_active: bool


class InventoryItemStatusSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stock_status: StockStatus
    quantity_base: Decimal
    occupied_weight_kg: Decimal | None
    occupied_volume_m3: Decimal | None
    measurement_status: Literal["complete", "incomplete"]


class InventoryItemSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inventory_item_id: uuid.UUID
    company_id: uuid.UUID
    product_id: int | None
    variant_id: uuid.UUID | None
    base_unit_id: int
    is_active: bool
    total_quantity_base: Decimal
    status_totals: list[InventoryItemStatusSummaryOut]
    occupied_weight_kg: Decimal | None
    occupied_volume_m3: Decimal | None
    measurement_status: Literal["complete", "incomplete"]
    handling_unit_count: int
    unmeasured_handling_units: int
    warehouse_count: int
    location_count: int
    lot_count: int


class PackagingCreate(StrictModel):
    code: str = Field(..., min_length=1, max_length=60, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(..., min_length=2, max_length=120)
    packaging_type: PackagingType
    packaging_unit_id: int = Field(..., gt=0)
    base_quantity: Decimal = Field(..., gt=0, max_digits=18, decimal_places=6)
    measures: PhysicalMeasuresIn = Field(
        default_factory=PhysicalMeasuresIn,
        description="Medidas de una presentación individual, no del lote recibido.",
    )
    stackable: bool = True
    max_stack: int | None = Field(None, ge=1)
    supersedes_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_stack(self) -> PackagingCreate:
        if not self.stackable and self.max_stack is not None:
            raise ValueError("Una presentación no apilable no admite máximo de apilado.")
        return self


class PackagingOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    inventory_item_id: uuid.UUID
    code: str
    name: str
    packaging_type: PackagingType
    packaging_unit_id: int | None
    version: int
    base_quantity: Decimal
    gross_weight_kg: Decimal | None
    length_m: Decimal | None
    width_m: Decimal | None
    height_m: Decimal | None
    volume_m3: Decimal | None
    stackable: bool
    max_stack: int | None
    is_current: bool
    is_active: bool
    created_at: datetime | None = None


class CapacityPreviewIn(StrictModel):
    location_id: uuid.UUID
    inventory_item_id: uuid.UUID
    packaging_definition_id: uuid.UUID | None = None
    quantity_base: Decimal = Field(..., gt=0, max_digits=18, decimal_places=6)
    stock_status: StockStatus = StockStatus.AVAILABLE
    actual_measures: PhysicalMeasuresIn | None = Field(
        None,
        description="Medidas totales de la unidad logística real; no se multiplican por cantidad.",
    )
    operational_override_id: uuid.UUID | None = None
    exclude_reservation_id: uuid.UUID | None = None


class CapacityDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    allowed: bool
    code: str | None
    projected_weight_kg: Decimal | None
    projected_volume_m3: Decimal | None
    weight_utilization_pct: Decimal | None
    volume_utilization_pct: Decimal | None
    limiting_metric: Literal["weight", "volume"] | None
    measurement_status: MeasurementStatus


class CapacityReservationCreate(CapacityPreviewIn):
    duration_minutes: int = Field(30, ge=1, le=120)
    exclude_reservation_id: None = None


class CapacityReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    warehouse_id: uuid.UUID
    location_id: uuid.UUID
    inventory_item_id: uuid.UUID
    quantity_base: Decimal
    weight_kg: Decimal | None
    volume_m3: Decimal | None
    measurement_status: MeasurementStatus
    status: ReservationStatus
    expires_at: datetime
    operational_override_id: uuid.UUID | None
    created_at: datetime | None = None


class CapacityReservationCreated(BaseModel):
    reservation: CapacityReservationOut
    decision: CapacityDecisionOut


class ReservationActionIn(StrictModel):
    action: Literal["confirm", "cancel"]


MovementCommandType = Literal[
    "receipt",
    "putaway",
    "transfer",
    "pick",
    "shipment",
    "adjustment_in",
    "adjustment_out",
]


class MovementLineIn(StrictModel):
    inventory_item_id: uuid.UUID
    handling_unit_id: uuid.UUID | None = None
    packaging_definition_id: uuid.UUID | None = None
    handling_unit_code: str | None = Field(None, min_length=3, max_length=120)
    lot_code: str | None = Field(None, max_length=120)
    expiry_date: date | None = None
    from_location_id: uuid.UUID | None = None
    to_location_id: uuid.UUID | None = None
    from_stock_status: StockStatus | None = None
    to_stock_status: StockStatus | None = None
    quantity_base: Decimal = Field(..., gt=0, max_digits=18, decimal_places=6)
    actual_measures: PhysicalMeasuresIn | None = Field(
        None,
        description="Medidas totales de la unidad logística recibida.",
    )
    capacity_override_id: uuid.UUID | None = None
    valuation_kind: (
        Literal[
            "receipt",
            "issue",
            "adjustment_in",
            "adjustment_out",
            "customer_return",
            "supplier_return",
        ]
        | None
    ) = None
    valuation_value: Decimal | None = Field(None, ge=0, max_digits=24, decimal_places=6)
    valuation_currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    valuation_original_entry_id: uuid.UUID | None = None


class MovementConfirmIn(StrictModel):
    idempotency_key: str = Field(..., min_length=8, max_length=120)
    movement_type: MovementCommandType
    source_reference: str | None = Field(None, max_length=160)
    reservation_id: uuid.UUID | None = None
    lines: list[MovementLineIn] = Field(..., min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_line_contracts(self) -> MovementConfirmIn:  # noqa: C901
        inbound = self.movement_type in {"receipt", "adjustment_in"}
        outbound = self.movement_type in {"pick", "shipment", "adjustment_out"}
        transfer = self.movement_type in {"putaway", "transfer"}
        seen_handling_units: set[uuid.UUID] = set()
        seen_new_codes: set[str] = set()
        for line in self.lines:
            financial_fields = (
                line.valuation_kind,
                line.valuation_value,
                line.valuation_currency,
                line.valuation_original_entry_id,
            )
            if transfer and any(value is not None for value in financial_fields):
                raise ValueError("Un traslado dentro de la empresa no modifica el costo.")
            if line.valuation_kind == "customer_return":
                if (
                    not inbound
                    or line.valuation_original_entry_id is None
                    or line.valuation_value is not None
                ):
                    raise ValueError(
                        "La devolución de cliente requiere entrada y salida original, sin costo manual."
                    )
            elif line.valuation_original_entry_id is not None:
                raise ValueError("La salida original solo corresponde a una devolución de cliente.")
            if outbound and line.valuation_value is not None:
                raise ValueError("El sistema determina el costo de salida según el promedio.")
            if inbound and (
                line.from_location_id is not None
                or line.to_location_id is None
                or line.to_stock_status is None
            ):
                raise ValueError("Una entrada requiere ubicación y estado de destino.")
            if outbound and (
                line.from_location_id is None
                or line.to_location_id is not None
                or line.from_stock_status is None
            ):
                raise ValueError("Una salida requiere ubicación y estado de origen.")
            if transfer and (
                line.from_location_id is None
                or line.to_location_id is None
                or line.from_stock_status is None
                or line.to_stock_status is None
            ):
                raise ValueError("Un traslado requiere origen y destino completos.")
            if inbound and line.handling_unit_id is not None:
                raise ValueError("Una recepción crea una unidad logística nueva.")
            if (outbound or transfer) and line.handling_unit_id is None:
                raise ValueError("La confirmación física requiere una unidad logística.")
            if line.handling_unit_id is not None:
                if line.handling_unit_id in seen_handling_units:
                    raise ValueError(
                        "Una unidad logística solo puede aparecer una vez por movimiento."
                    )
                seen_handling_units.add(line.handling_unit_id)
            if line.handling_unit_code is not None:
                normalized_code = line.handling_unit_code.casefold()
                if normalized_code in seen_new_codes:
                    raise ValueError(
                        "El código de una unidad logística no puede repetirse en el movimiento."
                    )
                seen_new_codes.add(normalized_code)
        return self


class MovementLineOut(BaseModel):
    id: uuid.UUID
    line_number: int
    inventory_item_id: uuid.UUID
    handling_unit_id: uuid.UUID
    operational_override_id: uuid.UUID | None = None
    from_location_id: uuid.UUID | None
    to_location_id: uuid.UUID | None
    quantity_base: Decimal
    occupied_weight_kg: Decimal | None
    occupied_volume_m3: Decimal | None
    measurement_status: MeasurementStatus
    lot_code: str | None
    receipt_lot_code: str | None = None
    receipt_lot_header_code: str | None = None
    expiry_date: date | None


class MovementOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    movement_type: str
    idempotency_key: str
    source_reference: str | None
    reservation_id: uuid.UUID | None
    posted_at: datetime
    lines: list[MovementLineOut]


class HandlingUnitSplitPrepareIn(StrictModel):
    idempotency_key: str = Field(..., min_length=8, max_length=120)
    split_quantity_base: Decimal = Field(..., gt=0, max_digits=18, decimal_places=6)
    destination_location_id: uuid.UUID


class HandlingUnitSplitPrepareOut(BaseModel):
    idempotency_key: str
    source_reference: str
    quarantine_movement: MovementOut
    split_movement: MovementOut
    remainder_handling_unit_id: uuid.UUID
    remainder_handling_unit_code: str
    remainder_quantity_base: Decimal
    split_handling_unit_id: uuid.UUID
    split_handling_unit_code: str
    split_quantity_base: Decimal
    stock_status: StockStatus
    measurement_status: MeasurementStatus


class InventoryMovementHistoryOut(BaseModel):
    id: uuid.UUID
    movement_id: uuid.UUID
    line_number: int
    company_id: uuid.UUID
    movement_type: str
    source_reference: str | None
    purchase_code: str | None
    purchase_order_code: str | None
    posted_at: datetime
    posted_by: uuid.UUID | None
    operator: str | None
    inventory_item_id: uuid.UUID
    product_id: int | None
    variant_id: uuid.UUID | None
    base_unit_id: int
    base_unit_name: str | None
    base_unit_symbol: str | None
    product_sku: str | None
    product_name: str | None
    handling_unit_id: uuid.UUID | None
    handling_unit_code: str | None
    from_warehouse_id: uuid.UUID | None
    from_warehouse_code: str | None
    from_warehouse_name: str | None
    from_location_id: uuid.UUID | None
    from_location_code: str | None
    from_stock_status: StockStatus | None
    to_warehouse_id: uuid.UUID | None
    to_warehouse_code: str | None
    to_warehouse_name: str | None
    to_location_id: uuid.UUID | None
    to_location_code: str | None
    to_stock_status: StockStatus | None
    quantity_base: Decimal
    occupied_weight_kg: Decimal | None
    occupied_volume_m3: Decimal | None
    measurement_status: MeasurementStatus
    lot_code: str | None
    receipt_lot_code: str | None = None
    receipt_lot_header_code: str | None = None
    expiry_date: date | None
    packaging_snapshot: dict[str, object] | None


class HandlingUnitMeasurementVerify(StrictModel):
    measures: PhysicalMeasuresIn
    source: Literal[MeasurementSource.MANUAL, MeasurementSource.DEVICE] = MeasurementSource.MANUAL

    @model_validator(mode="after")
    def validate_complete(self) -> HandlingUnitMeasurementVerify:
        if not self.measures.to_domain().is_complete:
            raise ValueError("La verificación requiere peso y volumen completos.")
        return self


class HandlingUnitOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    warehouse_id: uuid.UUID
    location_id: uuid.UUID
    inventory_item_id: uuid.UUID
    packaging_definition_id: uuid.UUID | None
    origin_handling_unit_id: uuid.UUID | None = None
    code: str
    lot_code: str | None
    expiry_date: date | None
    quantity_base: Decimal
    actual_gross_weight_kg: Decimal | None
    actual_length_m: Decimal | None
    actual_width_m: Decimal | None
    actual_height_m: Decimal | None
    actual_volume_m3: Decimal | None
    occupied_weight_kg: Decimal | None
    occupied_volume_m3: Decimal | None
    stock_status: StockStatus
    measurement_status: MeasurementStatus
    measurement_source: MeasurementSource
    closed_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    receipt_lot_id: uuid.UUID | None = None
    receipt_lot_code: str | None = None
    receipt_lot_header_code: str | None = None
    received_at: datetime | None = None
    purchase_code: str | None = None
    product_sku: str | None = None
    product_name: str | None = None
    product_id: int | None = None
    base_unit_id: int | None = None
    base_unit_symbol: str | None = None
    base_unit_name: str | None = None
    packaging_name: str | None = None
    packaging_base_quantity: Decimal | None = None
    release_requirements: list[str] = Field(default_factory=list)


class TransferHandlingUnitOut(HandlingUnitOut):
    """Handling unit with the identity and routing data needed by transfers."""

    product_id: int | None
    product_sku: str | None
    product_name: str | None
    base_unit_id: int
    base_unit_name: str | None
    base_unit_symbol: str | None
    warehouse_code: str | None
    warehouse_name: str
    branch_id: uuid.UUID | None
    branch_name: str | None
    location_code: str
    source_reference: str | None
    origin_handling_unit_code: str | None = None


class HandlingUnitTraceEventOut(BaseModel):
    movement_id: uuid.UUID
    movement_type: str
    source_reference: str | None
    posted_at: datetime
    posted_by: uuid.UUID | None
    operator: str | None
    from_warehouse_code: str | None
    from_warehouse_name: str | None
    from_location_code: str | None
    from_stock_status: StockStatus | None
    to_warehouse_code: str | None
    to_warehouse_name: str | None
    to_location_code: str | None
    to_stock_status: StockStatus | None
    quantity_base: Decimal


class HandlingUnitTraceRequestOut(BaseModel):
    request_code: str
    branch_name: str
    requested_at: datetime
    required_date: datetime | None


class HandlingUnitTraceOriginOut(BaseModel):
    supplier_code: str | None
    supplier_name: str | None
    purchase_code: str | None
    purchase_order_code: str | None
    received_at: datetime | None
    purchase_date: datetime | None
    consolidation_code: str | None
    requests: list[HandlingUnitTraceRequestOut]


class HandlingUnitTraceOut(BaseModel):
    handling_unit: HandlingUnitOut
    product_sku: str | None
    product_name: str | None
    base_unit_name: str | None
    base_unit_symbol: str | None
    warehouse_code: str
    warehouse_name: str
    location_code: str
    origin: HandlingUnitTraceOriginOut
    movements: list[HandlingUnitTraceEventOut]


class InventoryBalanceOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    warehouse_id: uuid.UUID
    location_id: uuid.UUID
    inventory_item_id: uuid.UUID
    stock_status: StockStatus
    lot_code: str | None
    expiry_date: date | None
    quantity_base: Decimal
    occupied_weight_kg: Decimal | None
    occupied_volume_m3: Decimal | None
    measurement_status: Literal["complete", "incomplete"]
    created_at: datetime | None
    updated_at: datetime | None


class CapacityMetricOut(BaseModel):
    certified: Decimal | None
    operational: Decimal | None
    occupied: Decimal | None
    reserved: Decimal | None
    projected: Decimal | None
    available: Decimal | None
    utilization_pct: Decimal | None


class CapacityScopeReferenceOut(BaseModel):
    scope_type: Literal["warehouse", "capacity_group", "location"]
    scope_id: uuid.UUID
    code: str
    name: str


class CapacityScopeSummaryOut(CapacityScopeReferenceOut):
    measurement_status: Literal["complete", "incomplete"]
    status: Literal[
        "not_configured",
        "incomplete",
        "available",
        "warning",
        "critical",
        "full",
        "over_operational",
        "over_certified",
    ]
    limiting_metric: Literal["weight", "volume"] | None
    weight: CapacityMetricOut
    volume: CapacityMetricOut
    effective_utilization_pct: Decimal | None
    unmeasured_handling_units: int
    unmeasured_reservations: int


class CapacitySummaryOut(BaseModel):
    scope_type: Literal["warehouse", "location"]
    warehouse_id: uuid.UUID
    location_id: uuid.UUID | None
    measurement_status: Literal["complete", "incomplete"]
    status: Literal[
        "not_configured",
        "incomplete",
        "available",
        "warning",
        "critical",
        "full",
        "over_operational",
        "over_certified",
    ]
    limiting_metric: Literal["weight", "volume"] | None
    weight: CapacityMetricOut
    volume: CapacityMetricOut
    effective_utilization_pct: Decimal | None
    unmeasured_handling_units: int
    unmeasured_reservations: int
    scope_path: list[CapacityScopeSummaryOut] = Field(default_factory=list)
    limiting_scope: CapacityScopeReferenceOut | None = None


class OperationalOverrideCreate(StrictModel):
    location_id: uuid.UUID
    reason: str = Field(..., min_length=10, max_length=1000)
    valid_until: datetime

    @model_validator(mode="after")
    def validate_timezone(self) -> OperationalOverrideCreate:
        if self.valid_until.tzinfo is None or self.valid_until.utcoffset() is None:
            raise ValueError("valid_until debe incluir zona horaria.")
        return self


class OperationalOverrideOut(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    reason: str
    valid_until: datetime
    status: Literal["active", "revoked", "expired"]
    granted_by: uuid.UUID | None = None
    revoked_at: datetime | None = None
    revoked_by: uuid.UUID | None = None
