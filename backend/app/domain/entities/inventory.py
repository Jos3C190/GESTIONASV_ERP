"""Pure inventory and warehouse-capacity domain primitives.

All physical quantities use canonical SI units (kg, m and m³) and ``Decimal``.
The module deliberately has no SQLAlchemy or FastAPI dependency so the critical
capacity rules can be tested independently from persistence.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from enum import StrEnum

ZERO = Decimal("0")
PHYSICAL_QUANTUM = Decimal("0.000001")
MAX_NUMERIC_18_6 = Decimal("999999999999.999999")


def _canonical_physical_quantity(value: Decimal) -> Decimal:
    """Round a positive physical quantity to the persisted SI precision.

    PostgreSQL stores these values as ``NUMERIC(18, 6)``.  Rounding upward is
    deliberate: a capacity guard must never understate weight or volume merely
    because a packaging ratio or three-dimensional product has more precision
    than the ledger column.
    """

    if not value.is_finite() or value <= ZERO:
        raise ValueError("Las cantidades físicas deben ser mayores que cero.")
    if value > MAX_NUMERIC_18_6:
        raise ValueError("La cantidad física excede la precisión admitida.")
    try:
        return value.quantize(PHYSICAL_QUANTUM, rounding=ROUND_CEILING)
    except InvalidOperation as exc:
        raise ValueError("La cantidad física no es representable.") from exc


class InventoryOperationError(Exception):
    """Stable business failure raised across the inventory boundary."""

    def __init__(self, message: str, *, code: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class PackagingType(StrEnum):
    PIECE = "piece"
    BOX = "box"
    BAG = "bag"
    PACKAGE = "package"
    ROLL = "roll"
    DRUM = "drum"
    CONTAINER = "container"
    LOOSE_OTHER = "loose_other"


class StockStatus(StrEnum):
    AVAILABLE = "available"
    QUARANTINE = "quarantine"
    BLOCKED = "blocked"
    DAMAGED = "damaged"
    IN_TRANSIT = "in_transit"


class MeasurementStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    VERIFIED = "verified"


class MeasurementSource(StrEnum):
    MASTER = "master"
    RECEIPT = "receipt"
    MANUAL = "manual"
    DEVICE = "device"


class MovementType(StrEnum):
    RECEIPT = "receipt"
    PUTAWAY = "putaway"
    TRANSFER = "transfer"
    PICK = "pick"
    SHIPMENT = "shipment"
    ADJUSTMENT_IN = "adjustment_in"
    ADJUSTMENT_OUT = "adjustment_out"
    REVERSAL = "reversal"


class ReservationStatus(StrEnum):
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    CONSUMED = "consumed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class PhysicalMeasures:
    gross_weight_kg: Decimal | None
    length_m: Decimal | None
    width_m: Decimal | None
    height_m: Decimal | None
    volume_m3: Decimal | None = None

    @property
    def derived_volume_m3(self) -> Decimal | None:
        if self.volume_m3 is not None:
            return _canonical_physical_quantity(self.volume_m3)
        dimensions = (self.length_m, self.width_m, self.height_m)
        if any(value is None for value in dimensions):
            return None
        assert self.length_m is not None
        assert self.width_m is not None
        assert self.height_m is not None
        return _canonical_physical_quantity(
            self.length_m * self.width_m * self.height_m
        )

    @property
    def is_complete(self) -> bool:
        volume = self.derived_volume_m3
        return (
            self.gross_weight_kg is not None
            and self.gross_weight_kg > ZERO
            and volume is not None
            and volume > ZERO
        )

    def validate(self) -> None:
        values = (
            self.gross_weight_kg,
            self.length_m,
            self.width_m,
            self.height_m,
            self.volume_m3,
        )
        if any(
            value is not None and (not value.is_finite() or value <= ZERO)
            for value in values
        ):
            raise ValueError("Las medidas físicas deben ser mayores que cero.")
        supplied_dimensions = [
            self.length_m is not None,
            self.width_m is not None,
            self.height_m is not None,
        ]
        if any(supplied_dimensions) and not all(supplied_dimensions):
            raise ValueError("Largo, ancho y alto deben informarse juntos.")


@dataclass(frozen=True, slots=True)
class Consumption:
    weight_kg: Decimal
    volume_m3: Decimal


def calculate_consumption(
    *,
    quantity_base: Decimal,
    base_quantity: Decimal,
    measures: PhysicalMeasures,
) -> Consumption | None:
    """Calculate physical consumption for a homogeneous packaging quantity."""
    if quantity_base <= ZERO or base_quantity <= ZERO:
        raise ValueError("Las cantidades deben ser mayores que cero.")
    measures.validate()
    if not measures.is_complete:
        return None
    assert measures.gross_weight_kg is not None
    volume = measures.derived_volume_m3
    assert volume is not None
    packaging_count = quantity_base / base_quantity
    return Consumption(
        weight_kg=_canonical_physical_quantity(
            measures.gross_weight_kg * packaging_count
        ),
        volume_m3=_canonical_physical_quantity(volume * packaging_count),
    )


def calculate_measured_consumption(
    measures: PhysicalMeasures,
) -> Consumption | None:
    """Use one real HU measurement as a total, never as a per-pack factor."""

    measures.validate()
    if not measures.is_complete:
        return None
    assert measures.gross_weight_kg is not None
    volume = measures.derived_volume_m3
    assert volume is not None
    return Consumption(
        weight_kg=_canonical_physical_quantity(measures.gross_weight_kg),
        volume_m3=_canonical_physical_quantity(volume),
    )


def require_quarantine_for_incomplete_measures(
    measures: PhysicalMeasures,
    stock_status: StockStatus,
) -> None:
    measures.validate()
    if not measures.is_complete and stock_status is not StockStatus.QUARANTINE:
        raise ValueError(
            "La mercancía sin peso y volumen completos solo puede recibirse en cuarentena."
        )


@dataclass(frozen=True, slots=True)
class CapacityLimit:
    certified_weight_kg: Decimal | None
    operational_weight_kg: Decimal | None
    certified_volume_m3: Decimal | None
    operational_volume_m3: Decimal | None
    enforcement_mode: str = "enforce"


@dataclass(frozen=True, slots=True)
class CapacityUsage:
    occupied_weight_kg: Decimal = ZERO
    occupied_volume_m3: Decimal = ZERO
    reserved_weight_kg: Decimal = ZERO
    reserved_volume_m3: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class CapacityDecision:
    allowed: bool
    code: str | None
    projected_weight_kg: Decimal | None
    projected_volume_m3: Decimal | None
    weight_utilization_pct: Decimal | None
    volume_utilization_pct: Decimal | None
    limiting_metric: str | None
    measurement_status: MeasurementStatus = MeasurementStatus.COMPLETE


def _percent(value: Decimal, limit: Decimal | None) -> Decimal | None:
    if limit is None or limit <= ZERO:
        return None
    return value / limit * Decimal("100")


def evaluate_capacity(
    *,
    limit: CapacityLimit,
    usage: CapacityUsage,
    incoming: Consumption,
    has_operational_override: bool = False,
) -> CapacityDecision:
    """Evaluate the projected state; certified limits can never be overridden."""
    projected_weight = (
        usage.occupied_weight_kg + usage.reserved_weight_kg + incoming.weight_kg
    )
    projected_volume = (
        usage.occupied_volume_m3 + usage.reserved_volume_m3 + incoming.volume_m3
    )
    weight_pct = _percent(projected_weight, limit.operational_weight_kg)
    volume_pct = _percent(projected_volume, limit.operational_volume_m3)
    comparable = [("weight", weight_pct), ("volume", volume_pct)]
    available = [(name, value) for name, value in comparable if value is not None]
    limiting = max(available, key=lambda entry: entry[1])[0] if available else None

    code: str | None = None
    if (
        limit.certified_weight_kg is not None
        and projected_weight > limit.certified_weight_kg
    ) or (
        limit.certified_volume_m3 is not None
        and projected_volume > limit.certified_volume_m3
    ):
        code = "certified_capacity_exceeded"
    elif limit.enforcement_mode == "enforce" and not has_operational_override:
        if (
            limit.operational_weight_kg is not None
            and projected_weight > limit.operational_weight_kg
        ):
            code = "capacity_weight_exceeded"
        elif (
            limit.operational_volume_m3 is not None
            and projected_volume > limit.operational_volume_m3
        ):
            code = "capacity_volume_exceeded"

    return CapacityDecision(
        allowed=code is None,
        code=code,
        projected_weight_kg=projected_weight,
        projected_volume_m3=projected_volume,
        weight_utilization_pct=weight_pct,
        volume_utilization_pct=volume_pct,
        limiting_metric=limiting,
    )


@dataclass(frozen=True, slots=True)
class InventoryItem:
    id: uuid.UUID
    company_id: uuid.UUID
    product_id: int | None
    variant_id: uuid.UUID | None
    base_unit_id: int
    is_active: bool


@dataclass(frozen=True, slots=True)
class PackagingDefinition:
    id: uuid.UUID
    company_id: uuid.UUID
    inventory_item_id: uuid.UUID
    code: str
    name: str
    packaging_type: PackagingType
    version: int
    base_quantity: Decimal
    measures: PhysicalMeasures
    stackable: bool
    max_stack: int | None
    is_current: bool
    is_active: bool
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CapacityReservation:
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
    operational_override_id: uuid.UUID | None = None
    created_at: datetime | None = None
