"""Pure rules of the tracking simulator.

The simulator never fakes ERP data: it drives a *virtual GPS device* that
reports to Traccar over OsmAnd, exactly like the phone app of a real driver.
Geofence events, alerts, ETA and stored trails then come from the real
pipeline. Everything here is pure so the motion is deterministic and testable.
"""

from __future__ import annotations

import math
import uuid
from bisect import bisect_left
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from app.application.tracking.transfers import EARTH_RADIUS_M, LngLat, distance_m

SimulationMode = Literal["route", "joystick"]
SimulationState = Literal["running", "paused", "arrived", "ended"]

#: How often the engine advances route sessions.
TICK_SECONDS = 2.0
#: Report period while moving (a phone app usually reports every few seconds).
MOVING_REPORT_S = 3.0
#: Heartbeat while stopped, so Traccar keeps the unit online.
PARKED_REPORT_S = 30.0
#: Acceleration and braking (≈ 0-50 km/h in 4 s, like a loaded van).
ACCEL_KMH_PER_S = 12.0
MIN_SPEED_KMH = 1
MAX_SPEED_KMH = 300
#: Sessions nobody touched for this long end on their own.
IDLE_TIMEOUT = timedelta(minutes=45)
#: No session outlives a working day.
MAX_SESSION = timedelta(hours=8)
#: Joystick reports may not imply more than this (teleport protection).
MAX_DRIVE_KMH = 450
DRIVE_TOLERANCE_M = 60
#: Lateral distance of the detour waypoint from the planned route.
DETOUR_OFFSET_M = 800
MAX_WAYPOINTS = 25
#: Maximum length of a simulated stop or signal loss.
MAX_HOLD_MINUTES = 240
#: No detour is offered this close to the destination.
MIN_DETOUR_REMAINING_M = 200
#: Below this the unit counts as standing still.
STILL_KMH = 0.5
ARRIVAL_SLACK_M = 0.5
#: A joystick session may appear at most this far from where it was created.
FIRST_DRIVE_MAX_M = 5_000
#: Like the angle setting of Traccar Client: a turn sharper than this is always reported,
#: so the trail in Traccar bends at the corner instead of cutting the block.
TURN_REPORT_DEG = 15.0
#: A turn is measured between points this far before and after the vertex, so a curve
#: drawn with many small vertices counts as one turn.
TURN_WINDOW_M = 15.0
#: Speed through a corner: gentle bends barely slow down, 90° ≈ 20 km/h, U-turn 10 km/h.
MIN_CORNER_KMH = 10.0
CORNER_FREE_DEG = 15.0
#: Extra distance looked ahead beyond the braking distance.
LOOKAHEAD_MARGIN_M = 30.0
MAX_LOOKAHEAD_M = 400.0
#: Timer slack so a 3 s period is not missed by a few milliseconds.
REPORT_SLACK_S = 0.05

UNIQUE_ID_PREFIX = "erp-sim-"
SIMULATED_ATTRIBUTE = "erpSimulated"
KMH_PER_KNOT = 1.852


def unique_id_for(vehicle_id: uuid.UUID) -> str:
    """Stable identifier of a vehicle's virtual GPS (reused across sessions)."""
    return f"{UNIQUE_ID_PREFIX}{vehicle_id.hex[:20]}"


def is_simulator_unique_id(value: str) -> bool:
    return value.strip().lower().startswith(UNIQUE_ID_PREFIX)


# ---------------------------------------------------------------- geometry


def bearing(a: LngLat, b: LngLat) -> float:
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    d_lng = math.radians(b[0] - a[0])
    y = math.sin(d_lng) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lng)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def offset_point(point: LngLat, course: float, meters: float) -> LngLat:
    """The point ``meters`` away from ``point`` heading ``course`` (degrees)."""
    angular = meters / EARTH_RADIUS_M
    heading = math.radians(course)
    lat1, lng1 = math.radians(point[1]), math.radians(point[0])
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular) + math.cos(lat1) * math.sin(angular) * math.cos(heading)
    )
    lng2 = lng1 + math.atan2(
        math.sin(heading) * math.sin(angular) * math.cos(lat1),
        math.cos(angular) - math.sin(lat1) * math.sin(lat2),
    )
    return ((math.degrees(lng2) + 540) % 360 - 180, math.degrees(lat2))


def path_length(route: list[LngLat]) -> float:
    return sum(distance_m(a, b) for a, b in pairwise(route))


def point_at(route: list[LngLat], distance: float) -> tuple[LngLat, float]:
    """Position and heading ``distance`` meters along ``route``."""
    if not route:
        raise ValueError("empty route")
    if len(route) == 1:
        return route[0], 0.0
    walked = 0.0
    for a, b in pairwise(route):
        segment = distance_m(a, b)
        if segment <= 0:
            continue
        if walked + segment >= distance:
            t = max(0.0, min(1.0, (distance - walked) / segment))
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), bearing(a, b)
        walked += segment
    last = next(
        ((a, b) for a, b in reversed(list(pairwise(route))) if a != b),
        (route[-2], route[-1]),
    )
    return route[-1], bearing(*last)


def _turn(a: float, b: float) -> float:
    return abs((b - a + 180) % 360 - 180)


def turns_between(
    route: list[LngLat], start: float, end: float
) -> list[tuple[float, LngLat, float]]:
    """Corners of ``route`` passed between ``start`` and ``end`` meters.

    Returns ``(distance, vertex, course after the vertex)`` for every vertex where the
    road turns at least ``TURN_REPORT_DEG``.
    """
    corners: list[tuple[float, LngLat, float]] = []
    walked = 0.0
    previous: float | None = None
    for a, b in pairwise(route):
        segment = distance_m(a, b)
        if segment <= 0:
            continue
        course = bearing(a, b)
        if (
            previous is not None
            and start < walked < end
            and _turn(previous, course) >= TURN_REPORT_DEG
        ):
            corners.append((walked, a, course))
        if walked > end:
            break
        walked += segment
        previous = course
    return corners


def corner_speed_kmh(turn_deg: float) -> float:
    """Comfortable speed through a turn of ``turn_deg`` degrees."""
    if turn_deg < CORNER_FREE_DEG:
        return math.inf
    return max(MIN_CORNER_KMH, 70.0 - 0.55 * turn_deg)


def _cumulative(route: list[LngLat]) -> list[float]:
    distances = [0.0]
    for a, b in pairwise(route):
        distances.append(distances[-1] + distance_m(a, b))
    return distances


def _at(route: list[LngLat], cumulative: list[float], distance: float) -> LngLat:
    distance = max(0.0, min(distance, cumulative[-1]))
    index = max(1, min(bisect_left(cumulative, distance), len(route) - 1))
    a, b = route[index - 1], route[index]
    span = cumulative[index] - cumulative[index - 1]
    t = 0.0 if span <= 0 else (distance - cumulative[index - 1]) / span
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def upcoming_turns(route: list[LngLat], start: float, end: float) -> list[tuple[float, float]]:
    """``(distance, turn degrees)`` of the vertices between ``start`` and ``end`` meters."""
    if len(route) < 3:  # noqa: PLR2004 - no vertex between two points
        return []
    cumulative = _cumulative(route)
    turns: list[tuple[float, float]] = []
    for index in range(1, len(route) - 1):
        at = cumulative[index]
        if at <= start:
            continue
        if at > end:
            break
        vertex = route[index]
        before = _at(route, cumulative, at - TURN_WINDOW_M)
        after = _at(route, cumulative, at + TURN_WINDOW_M)
        if vertex in (before, after):
            continue
        turns.append((at, _turn(bearing(before, vertex), bearing(vertex, after))))
    return turns


def corner_limit_kmh(
    route: list[LngLat], progress: float, current_kmh: float, accel_ms2: float
) -> float:
    """Fastest speed now that still lets the unit slow down for every turn ahead."""
    speed_ms = current_kmh / 3.6
    lookahead = min(MAX_LOOKAHEAD_M, speed_ms**2 / (2 * accel_ms2) + LOOKAHEAD_MARGIN_M)
    limit = math.inf
    for at, turn in upcoming_turns(route, progress - TURN_WINDOW_M, progress + lookahead):
        corner = corner_speed_kmh(turn)
        if math.isinf(corner):
            continue
        gap = max(0.0, at - progress)
        limit = min(limit, math.sqrt((corner / 3.6) ** 2 + 2 * accel_ms2 * gap) * 3.6)
    return limit


def detour_waypoint(route: list[LngLat], progress: float) -> LngLat | None:
    """A point off to the side of the road ahead, to force a deviation."""
    length = path_length(route)
    remaining = length - progress
    if remaining < MIN_DETOUR_REMAINING_M:
        return None
    ahead, course = point_at(route, progress + min(1_200.0, remaining / 2))
    return offset_point(ahead, (course + 90) % 360, DETOUR_OFFSET_M)


# ---------------------------------------------------------------- motion


@dataclass(frozen=True, slots=True)
class SimSnapshot:
    mode: SimulationMode
    state: SimulationState
    route: list[LngLat]
    route_length_m: float
    progress_m: float
    speed_kmh: float
    current_speed_kmh: float
    position: LngLat
    course: float
    stop_until: datetime | None
    signal_lost_until: datetime | None
    last_report_at: datetime | None


@dataclass(frozen=True, slots=True)
class SimStep:
    state: SimulationState
    progress_m: float
    position: LngLat
    course: float
    current_speed_kmh: float
    #: Send a position to Traccar on this tick.
    report: bool
    #: Holds that ran out on this tick.
    stop_until: datetime | None
    signal_lost_until: datetime | None
    #: Corners crossed on this tick, ``(vertex, course, fraction of the tick)``, to report
    #: before the position so the trail follows the street.
    corners: tuple[tuple[LngLat, float, float], ...] = ()


def holding(snapshot: SimSnapshot, now: datetime) -> bool:
    """The unit is standing still on purpose (paused, a timed stop, or arrived)."""
    if snapshot.state in {"paused", "arrived"}:
        return True
    return snapshot.stop_until is not None and now < snapshot.stop_until


def signal_lost(snapshot: SimSnapshot, now: datetime) -> bool:
    return snapshot.signal_lost_until is not None and now < snapshot.signal_lost_until


def _report_due(snapshot: SimSnapshot, now: datetime, speed: float) -> bool:
    if signal_lost(snapshot, now):
        return False
    if snapshot.last_report_at is None:
        return True
    elapsed = (now - snapshot.last_report_at).total_seconds()
    if snapshot.signal_lost_until is not None and now >= snapshot.signal_lost_until:
        return True  # La señal acaba de volver: se informa de inmediato.
    period = MOVING_REPORT_S if speed > STILL_KMH else PARKED_REPORT_S
    return elapsed >= period - REPORT_SLACK_S


def step(snapshot: SimSnapshot, now: datetime, dt: float) -> SimStep:
    """Advance a session by ``dt`` seconds."""
    stop_until = snapshot.stop_until if snapshot.stop_until and now < snapshot.stop_until else None
    lost_until = (
        snapshot.signal_lost_until
        if snapshot.signal_lost_until and now < snapshot.signal_lost_until
        else None
    )
    if snapshot.mode == "joystick" or not snapshot.route:
        # El joystick mueve la unidad desde el navegador; aquí solo se mantiene viva.
        speed = snapshot.current_speed_kmh
        if snapshot.last_report_at is not None and (now - snapshot.last_report_at) > timedelta(
            seconds=MOVING_REPORT_S * 2
        ):
            speed = 0.0
        return SimStep(
            state=snapshot.state,
            progress_m=snapshot.progress_m,
            position=snapshot.position,
            course=snapshot.course,
            current_speed_kmh=speed,
            report=_report_due(snapshot, now, speed),
            stop_until=stop_until,
            signal_lost_until=lost_until,
        )

    remaining = max(0.0, snapshot.route_length_m - snapshot.progress_m)
    target = 0.0 if holding(snapshot, now) else snapshot.speed_kmh
    # Frena a tiempo para detenerse justo en el destino.
    accel_ms2 = ACCEL_KMH_PER_S / 3.6
    target = min(target, math.sqrt(2 * accel_ms2 * remaining) * 3.6)
    # Y antes de cada curva, a la velocidad que permite tomarla. Se mide desde donde estará
    # al terminar este paso: con el punto de partida, el freno llegaba un paso tarde.
    ahead = snapshot.progress_m + snapshot.current_speed_kmh / 3.6 * dt
    target = min(
        target,
        corner_limit_kmh(snapshot.route, ahead, snapshot.current_speed_kmh, accel_ms2),
    )
    change = ACCEL_KMH_PER_S * dt
    current = snapshot.current_speed_kmh
    speed = min(target, current + change) if target >= current else max(target, current - change)
    travelled = (current + speed) / 2 / 3.6 * dt
    progress = min(snapshot.route_length_m, snapshot.progress_m + travelled)
    position, course = point_at(snapshot.route, progress)
    state: SimulationState = snapshot.state
    if snapshot.route_length_m - progress <= ARRIVAL_SLACK_M and state == "running":
        state, speed, progress = "arrived", 0.0, snapshot.route_length_m
        position, course = point_at(snapshot.route, progress)
    if speed < STILL_KMH and travelled < ARRIVAL_SLACK_M:
        course = snapshot.course
    moved = replace(snapshot, current_speed_kmh=speed)
    corners: tuple[tuple[LngLat, float, float], ...] = ()
    if not signal_lost(snapshot, now) and progress > snapshot.progress_m:
        span = progress - snapshot.progress_m
        corners = tuple(
            (vertex, heading, (at - snapshot.progress_m) / span)
            for at, vertex, heading in turns_between(snapshot.route, snapshot.progress_m, progress)
        )
    return SimStep(
        state=state,
        progress_m=progress,
        position=position,
        course=course,
        current_speed_kmh=round(speed, 1),
        # Si cruzó una esquina, informa también la posición actual: el tramo queda completo.
        report=_report_due(moved, now, speed) or bool(corners),
        stop_until=stop_until,
        signal_lost_until=lost_until,
        corners=corners,
    )


def expiry_reason(started_at: datetime, last_activity_at: datetime, now: datetime) -> str | None:
    if now - started_at >= MAX_SESSION:
        return "La sesión alcanzó su duración máxima (8 h)."
    if now - last_activity_at >= IDLE_TIMEOUT:
        return "Sesión sin actividad durante 45 min."
    return None


def plausible_drive(
    previous: LngLat, previous_at: datetime | None, target: LngLat, now: datetime
) -> bool:
    """Reject joystick reports that would teleport the unit."""
    if previous_at is None:
        return distance_m(previous, target) <= FIRST_DRIVE_MAX_M
    seconds = max((now - previous_at).total_seconds(), 0.2)
    allowed = MAX_DRIVE_KMH / 3.6 * seconds + DRIVE_TOLERANCE_M
    return distance_m(previous, target) <= allowed


# ---------------------------------------------------------------- Traccar


def osmand_params(
    unique_id: str, position: LngLat, at: datetime, speed_kmh: float, course: float
) -> dict[str, str]:
    """Query of an OsmAnd report (the protocol of the Traccar Client app)."""
    return {
        "id": unique_id,
        "lat": f"{position[1]:.6f}",
        "lon": f"{position[0]:.6f}",
        # En milisegundos: las esquinas y la posición de un mismo segundo quedan en orden.
        "timestamp": str(int(at.timestamp() * 1000)),
        "speed": f"{max(speed_kmh, 0.0) / KMH_PER_KNOT:.2f}",
        "bearing": f"{course % 360:.1f}",
        "accuracy": "5",
        "valid": "true",
    }


def osmand_url(explicit: str | None, traccar_url: str | None) -> str | None:
    """Where OsmAnd reports go: explicit setting or the Traccar host on port 5055."""
    if explicit:
        return explicit.rstrip("/")
    if not traccar_url:
        return None
    parts = urlsplit(traccar_url)
    if not parts.hostname:
        return None
    return urlunsplit((parts.scheme or "http", f"{parts.hostname}:5055", "", "", ""))


__all__ = [
    "DETOUR_OFFSET_M",
    "IDLE_TIMEOUT",
    "MAX_HOLD_MINUTES",
    "MAX_SESSION",
    "MAX_SPEED_KMH",
    "MAX_WAYPOINTS",
    "MIN_SPEED_KMH",
    "SIMULATED_ATTRIBUTE",
    "TICK_SECONDS",
    "TURN_REPORT_DEG",
    "SimSnapshot",
    "SimStep",
    "SimulationMode",
    "SimulationState",
    "bearing",
    "corner_limit_kmh",
    "corner_speed_kmh",
    "detour_waypoint",
    "expiry_reason",
    "holding",
    "is_simulator_unique_id",
    "offset_point",
    "osmand_params",
    "osmand_url",
    "path_length",
    "plausible_drive",
    "point_at",
    "signal_lost",
    "step",
    "turns_between",
    "unique_id_for",
    "upcoming_turns",
]
