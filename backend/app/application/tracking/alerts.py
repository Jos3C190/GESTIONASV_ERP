"""Conditions worth an alert on a transfer in transit.

Pure rules over a snapshot of the trip: the monitor evaluates them every minute
and keeps one open alert per transfer and kind, resolving it when the
condition clears. Thresholds favour few, meaningful alerts over noise.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.application.tracking.transfers import LngLat, distance_m

#: Below this speed the unit counts as stopped (GPS jitter while parked stays under it).
STOPPED_KMH = 3.0
#: A stop this long outside a branch or warehouse is worth a look.
LONG_STOP = timedelta(minutes=20)
#: No fix for this long while in transit means the GPS went silent.
GPS_SILENCE = timedelta(minutes=10)
#: Delay tolerance: the larger of this and DELAY_RATIO of the planned trip.
DELAY_MINIMUM = timedelta(minutes=15)
DELAY_RATIO = 0.25
#: Extra margin around a site radius before a stop counts as "outside".
SITE_MARGIN_M = 50.0


@dataclass(frozen=True, slots=True)
class Fix:
    at: datetime
    point: LngLat
    speed_kmh: float


@dataclass(slots=True)
class TripSnapshot:
    now: datetime
    dispatched_at: datetime | None
    destination_name: str
    gps_linked: bool
    fixes: Sequence[Fix] = ()
    planned_duration_s: float | None = None
    eta: datetime | None = None
    arrived: bool = False
    off_route: bool = False
    off_route_m: float = 0.0
    #: Known places (lng, lat, radius_m) where stopping is expected.
    sites: Sequence[tuple[float, float, float]] = ()


@dataclass(frozen=True, slots=True)
class Condition:
    kind: str
    severity: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def _clock(value: datetime) -> str:
    return value.strftime("%H:%M")


def _minutes(delta: timedelta) -> int:
    return max(int(delta.total_seconds() // 60), 0)


def stopped_since(fixes: Sequence[Fix]) -> datetime | None:
    """Start of the current stop, if the latest fixes are all below walking speed."""
    since: datetime | None = None
    for fix in reversed(fixes):
        if fix.speed_kmh >= STOPPED_KMH:
            break
        since = fix.at
    return since


def _at_known_place(point: LngLat, sites: Sequence[tuple[float, float, float]]) -> bool:
    return any(
        distance_m(point, (lng, lat)) <= radius + SITE_MARGIN_M for lng, lat, radius in sites
    )


def evaluate_trip(trip: TripSnapshot) -> list[Condition]:
    """Every alert condition that currently holds for the trip."""
    if trip.arrived:
        last = trip.fixes[-1].at if trip.fixes else trip.now
        return [
            Condition(
                "arrived",
                "info",
                f"Llegó a {trip.destination_name} a las {_clock(last)}; pendiente de recepción.",
                {"arrived_at": last.isoformat()},
            )
        ]
    if not trip.gps_linked:
        return [
            Condition(
                "gps_lost",
                "critical",
                "El vehículo del traslado no tiene GPS vinculado; no se puede seguir el viaje.",
                {"reason": "no_device"},
            )
        ]
    started = trip.dispatched_at or trip.now
    last_fix = trip.fixes[-1].at if trip.fixes else None
    silent_since = last_fix or started
    if trip.now - silent_since >= GPS_SILENCE:
        # Con datos viejos el resto de reglas no es confiable: solo se avisa del silencio.
        return [
            Condition(
                "gps_lost",
                "critical",
                f"Sin señal GPS desde las {_clock(silent_since)} "
                f"({_minutes(trip.now - silent_since)} min).",
                {"last_fix_at": last_fix.isoformat() if last_fix else None},
            )
        ]
    conditions: list[Condition] = []
    if trip.eta is not None and trip.planned_duration_s and trip.dispatched_at is not None:
        planned = trip.dispatched_at + timedelta(seconds=trip.planned_duration_s)
        tolerance = max(DELAY_MINIMUM, timedelta(seconds=trip.planned_duration_s * DELAY_RATIO))
        delay = trip.eta - planned
        if delay > tolerance:
            conditions.append(
                Condition(
                    "delayed",
                    "warning",
                    f"Va {_minutes(delay)} min atrasado: llegada estimada {_clock(trip.eta)} "
                    f"(prevista {_clock(planned)}).",
                    {"delay_min": _minutes(delay), "eta": trip.eta.isoformat()},
                )
            )
    since = stopped_since(trip.fixes)
    if (
        since is not None
        and trip.now - since >= LONG_STOP
        and not _at_known_place(trip.fixes[-1].point, trip.sites)
    ):
        point = trip.fixes[-1].point
        conditions.append(
            Condition(
                "long_stop",
                "warning",
                f"Detenido {_minutes(trip.now - since)} min fuera de una sucursal o almacén.",
                {"since": since.isoformat(), "longitude": point[0], "latitude": point[1]},
            )
        )
    if trip.off_route:
        conditions.append(
            Condition(
                "off_route",
                "warning",
                f"Fuera de la ruta planeada ({round(trip.off_route_m)} m).",
                {"off_route_m": round(trip.off_route_m)},
            )
        )
    return conditions
