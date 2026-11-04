"""Pure rules for the fleet cost report; operating figures, not accounting."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.application.fleet.operations import total_distance

BUSINESS_TZ = ZoneInfo("America/El_Salvador")
ZERO = Decimal("0")


def business_today() -> date:
    return datetime.now(BUSINESS_TZ).date()


def period_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    """Whole business days, with the end excluded: a 7 p.m. refill stays on its own date."""
    return (
        datetime.combine(date_from, time.min, BUSINESS_TZ),
        datetime.combine(date_to + timedelta(days=1), time.min, BUSINESS_TZ),
    )


def period_distance(readings: Sequence[tuple[Decimal, str]]) -> Decimal:
    """Distance over a period; ``readings`` start at the last one before it, when there is one."""
    return total_distance(readings)


def cost_per_unit(total: Decimal, distance: Decimal) -> Decimal | None:
    if distance <= 0:
        return None
    return (total / distance).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def report_rows(
    vehicles: Iterable[Mapping[str, Any]],
    *,
    fuel: Mapping[Any, Decimal],
    maintenance: Mapping[Any, Decimal],
    other: Mapping[Any, Decimal],
    distance: Mapping[Any, Decimal],
    incidents: Mapping[Any, Decimal] | None = None,
) -> list[dict[str, Any]]:
    """One row per vehicle. A retired unit only appears if it cost something in the period."""
    rows: list[dict[str, Any]] = []
    for vehicle in vehicles:
        vehicle_id = vehicle["vehicle_id"]
        row_fuel = fuel.get(vehicle_id, ZERO)
        row_maintenance = maintenance.get(vehicle_id, ZERO)
        row_other = other.get(vehicle_id, ZERO)
        row_incidents = (incidents or {}).get(vehicle_id, ZERO)
        total = row_fuel + row_maintenance + row_other + row_incidents
        if vehicle["retired"] and total == 0:
            continue
        travelled = distance.get(vehicle_id, ZERO)
        rows.append(
            {
                **{key: value for key, value in vehicle.items() if key != "retired"},
                "fuel": row_fuel,
                "maintenance": row_maintenance,
                "other": row_other,
                "incidents": row_incidents,
                "total": total,
                "distance": travelled,
                "cost_per_unit": cost_per_unit(total, travelled),
            }
        )
    rows.sort(key=lambda row: (-row["total"], row["code"]))
    return rows


def report_totals(rows: Iterable[Mapping[str, Any]]) -> dict[str, Decimal]:
    """Money adds up across the fleet. Distance does not: kilometers and hours do not mix."""
    totals = {"fuel": ZERO, "maintenance": ZERO, "other": ZERO, "incidents": ZERO, "total": ZERO}
    for row in rows:
        for key in totals:
            totals[key] += row[key]
    return totals
