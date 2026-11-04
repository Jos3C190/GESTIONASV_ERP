"""A company's fleet rules. A company that never saved them follows these defaults."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

#: Grams per unit in the catalogue's weight units, as kilograms.
_KG_PER_UNIT = {
    "mg": Decimal("0.000001"),
    "g": Decimal("0.001"),
    "kg": Decimal("1"),
    "t": Decimal("1000"),
    "oz": Decimal("0.0283495"),
    "lb": Decimal("0.453592"),
}


@dataclass(frozen=True, slots=True)
class FleetSettings:
    block_overdue_maintenance: bool = False
    require_inspection: bool = False
    block_overweight: bool = False
    inspection_valid_hours: int = 24
    document_warning_days: int = 30
    maintenance_warning_km: int = 500
    maintenance_warning_days: int = 7


def settings_from(row: Any | None) -> FleetSettings:
    if row is None:
        return FleetSettings()
    return FleetSettings(
        block_overdue_maintenance=row.block_overdue_maintenance,
        require_inspection=row.require_inspection,
        block_overweight=row.block_overweight,
        inspection_valid_hours=row.inspection_valid_hours,
        document_warning_days=row.document_warning_days,
        maintenance_warning_km=row.maintenance_warning_km,
        maintenance_warning_days=row.maintenance_warning_days,
    )


def to_kilograms(value: Decimal, unit: str) -> Decimal | None:
    factor = _KG_PER_UNIT.get(unit)
    return None if factor is None else Decimal(value) * factor
