"""Pure rules for odometer readings and fuel efficiency."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

#: Readings may not be dated in the future beyond this tolerance (clock drift).
FUTURE_TOLERANCE_SECONDS = 300

TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class OdometerBounds:
    minimum: Decimal | None
    maximum: Decimal | None


def odometer_error(reading: Decimal, bounds: OdometerBounds) -> str | None:
    """Explain why a reading breaks the vehicle's odometer history, if it does.

    Odometers never go back: a reading must be at least the latest earlier one
    and at most the earliest later one (readings can be back-dated).
    """
    if bounds.minimum is not None and reading < bounds.minimum:
        return f"La lectura ({reading} km) es menor que una lectura anterior ({bounds.minimum} km)."
    if bounds.maximum is not None and reading > bounds.maximum:
        return (
            f"La lectura ({reading} km) supera una lectura posterior ya registrada "
            f"({bounds.maximum} km)."
        )
    return None


def total_distance(readings: Sequence[tuple[Decimal, str]]) -> Decimal:
    """Distance over a vehicle's life: each meter's span, summed across replacements.

    ``readings`` are the valid (reading, source) pairs ordered by date.
    """
    total = Decimal("0")
    start: Decimal | None = None
    last: Decimal | None = None
    for reading, source in readings:
        if source == "meter_replacement" or start is None:
            if start is not None and last is not None:
                total += last - start
            start = reading
        last = reading
    if start is not None and last is not None:
        total += last - start
    return total


def in_future(moment: datetime, now: datetime) -> bool:
    return (moment - now).total_seconds() > FUTURE_TOLERANCE_SECONDS


def _money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def fuel_efficiency(logs: Sequence[Any]) -> dict[Any, Decimal | None]:
    """km/L per fill, measured only between consecutive full-tank fills.

    ``logs`` must be ordered by ``filled_at`` ascending. A full fill closes a
    segment: the distance since the previous full fill divided by every liter
    loaded after it (including partial fills) up to and including this one.
    """
    result: dict[Any, Decimal | None] = {}
    previous_full: Any | None = None
    liters_since = Decimal("0")
    for log in logs:
        liters_since += Decimal(log.liters)
        result[log.id] = None
        if not log.full_tank:
            continue
        if previous_full is not None and liters_since > 0:
            distance = Decimal(log.odometer_km) - Decimal(previous_full.odometer_km)
            if distance > 0:
                result[log.id] = _money(distance / liters_since)
        previous_full = log
        liters_since = Decimal("0")
    return result


def fuel_stats(logs: Sequence[Any], efficiency: dict[Any, Decimal | None]) -> dict[str, Any]:
    liters = sum((Decimal(log.liters) for log in logs), Decimal("0"))
    amount = sum((Decimal(log.total_amount) for log in logs), Decimal("0"))
    measured = [value for value in efficiency.values() if value is not None]
    average = _money(sum(measured, Decimal("0")) / len(measured)) if measured else None
    cost_per_km = None
    if len(logs) >= 2:  # noqa: PLR2004
        distance = Decimal(logs[-1].odometer_km) - Decimal(logs[0].odometer_km)
        # El primer llenado solo marca el punto de partida; su costo no recorre esa distancia.
        spent = amount - Decimal(logs[0].total_amount)
        if distance > 0:
            cost_per_km = (spent / distance).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return {
        "liters": liters.quantize(Decimal("0.001")),
        "amount": _money(amount),
        "average_km_per_liter": average,
        "cost_per_km": cost_per_km,
    }


def unit_price(total_amount: Decimal, liters: Decimal) -> Decimal:
    return (Decimal(total_amount) / Decimal(liters)).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )
