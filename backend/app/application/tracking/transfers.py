"""Live tracking of an inventory transfer between two branches.

Routing runs on OSRM (OpenStreetMap data, car profile: one-way streets and
turn restrictions included):

* ``plan_route`` — fastest driving route between two points.
* ``match_trail`` — snaps the raw GPS history onto the streets actually driven
  (OSRM *match*), incrementally and cached per transfer.
* ``resolve_active_route`` — keeps the planned route while the vehicle follows
  it and recalculates from the current position when it deviates, with
  hysteresis so the route does not flap on every GPS sample.

``build_transfer_progress`` is pure and derives progress, ETA and arrival from
those pieces. Every OSRM call degrades gracefully (straight line / raw trail).
"""

from __future__ import annotations

import asyncio
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from collections.abc import Iterable
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Any

import structlog

from app.application.tracking.traccar import KNOTS_TO_KMH

logger = structlog.get_logger(__name__)

LngLat = tuple[float, float]

EARTH_RADIUS_M = 6_371_000
#: Distance to the destination branch that counts as arrived.
ARRIVAL_RADIUS_M = 300
#: Lateral distance from the active route that counts as a deviation.
OFF_ROUTE_M = 1_000
#: Distance within which a vehicle is considered back on a recalculated route.
REJOIN_M = 250
#: Speed assumed for straight-line fallbacks when no routing service answers.
FALLBACK_SPEED_KMH = 45
#: Max geometry points returned to the browser per line.
MAX_LINE_POINTS = 1_500
#: OSRM's default limit of coordinates per match request. Servers configured with a
#: lower ``max-matching-size`` (the public demo accepts ~10) answer ``TooBig``; the
#: window then shrinks and the size that works is remembered for the process.
MATCH_WINDOW = 100
MIN_MATCH_WINDOW = 3
#: Expected GPS accuracy, used by the matcher as search radius.
GPS_RADIUS_M = 35
#: Consecutive fixes closer than this are treated as the same point (parked vehicle).
DEDUPE_M = 8
OSRM_TIMEOUT_S = 8


# ---------------------------------------------------------------- geometry


def distance_m(a: LngLat, b: LngLat) -> float:
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    d_lat = lat2 - lat1
    d_lng = math.radians(b[0] - a[0])
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _project(point: LngLat, start: LngLat, end: LngLat) -> tuple[float, LngLat]:
    """Fraction along the segment and the closest point (local equirectangular)."""
    scale = math.cos(math.radians(point[1]))
    ax, ay = start[0] * scale, start[1]
    bx, by = end[0] * scale, end[1]
    px, py = point[0] * scale, point[1]
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return t, (start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t)


def split_route(point: LngLat, route: list[LngLat]) -> tuple[float, float, list[LngLat]]:
    """Closest place on the route to ``point``.

    Returns (metres travelled along the route, lateral distance, remaining
    geometry from the projected point to the end).
    """
    if len(route) < 2:  # noqa: PLR2004
        return 0.0, distance_m(point, route[0]) if route else 0.0, list(route)
    best_lateral = math.inf
    best_along = 0.0
    best_index = 0
    best_point = route[0]
    travelled = 0.0
    for index, (start, end) in enumerate(pairwise(route)):
        segment = distance_m(start, end)
        t, closest = _project(point, start, end)
        lateral = distance_m(point, closest)
        if lateral < best_lateral:
            best_lateral, best_along = lateral, travelled + segment * t
            best_index, best_point = index, closest
        travelled += segment
    return best_along, best_lateral, [best_point, *route[best_index + 1 :]]


def locate_on_route(point: LngLat, route: list[LngLat]) -> tuple[float, float]:
    """Return (distance travelled along the route, lateral distance) in metres."""
    along, lateral, _ = split_route(point, route)
    return along, lateral


def route_length_m(route: list[LngLat]) -> float:
    return sum(distance_m(a, b) for a, b in pairwise(route))


#: Starting tolerance of the line simplification; it doubles until the line fits.
SIMPLIFY_TOLERANCE_M = 1.0


def simplify(points: list[LngLat], tolerance_m: float) -> list[LngLat]:
    """Douglas-Peucker: drop only points closer than ``tolerance_m`` to the simplified line.

    Unlike keeping every n-th point, every corner and curve of the street survives.
    """
    if len(points) <= 2:  # noqa: PLR2004 - a segment cannot be simplified
        return list(points)
    lat0 = math.radians(sum(point[1] for point in points) / len(points))
    xy = [
        (
            lng * math.cos(lat0) * EARTH_RADIUS_M * math.pi / 180,
            lat * EARTH_RADIUS_M * math.pi / 180,
        )
        for lng, lat in points
    ]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        (x1, y1), (x2, y2) = xy[first], xy[last]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        worst, index = 0.0, -1
        for i in range(first + 1, last):
            px, py = xy[i]
            if length == 0:
                gap = math.hypot(px - x1, py - y1)
            else:
                t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length**2))
                gap = math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
            if gap > worst:
                worst, index = gap, i
        if index >= 0 and worst > tolerance_m:
            keep[index] = True
            stack += [(first, index), (index, last)]
    return [point for point, kept in zip(points, keep, strict=True) if kept]


def downsample(points: list[LngLat], limit: int = MAX_LINE_POINTS) -> list[LngLat]:
    """At most ``limit`` points, keeping the shape of the street (corners included)."""
    if len(points) <= limit:
        return points
    tolerance = SIMPLIFY_TOLERANCE_M
    simplified = simplify(points, tolerance)
    while len(simplified) > limit:
        tolerance *= 2
        simplified = simplify(points, tolerance)
    return simplified


def dedupe(points: Iterable[LngLat], min_gap_m: float = DEDUPE_M) -> list[LngLat]:
    result: list[LngLat] = []
    for point in points:
        if not result or distance_m(result[-1], point) >= min_gap_m:
            result.append(point)
    return result


def _as_points(coordinates: Iterable[Iterable[float]]) -> list[LngLat]:
    return [(float(lng), float(lat)) for lng, lat in coordinates]


# ---------------------------------------------------------------- OSRM client


class _LRU(OrderedDict[str, Any]):
    def __init__(self, size: int) -> None:
        super().__init__()
        self.size = size

    def get_fresh(self, key: str) -> Any:
        if key not in self:
            return None
        self.move_to_end(key)
        return self[key]

    def put(self, key: str, value: Any) -> None:
        self[key] = value
        self.move_to_end(key)
        while len(self) > self.size:
            self.popitem(last=False)


_ROUTE_CACHE = _LRU(256)
_MATCH_CACHE = _LRU(128)
_REROUTE_CACHE = _LRU(128)
_match_window_size = MATCH_WINDOW


class _TooBigError(Exception):
    """The routing server rejected the number of coordinates in one request."""


def _osrm_request(url: str, timeout: float = OSRM_TIMEOUT_S) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "erp-tracking/1.0"})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            data: dict[str, Any] = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        # OSRM answers 400 with a JSON body (e.g. NoMatch / NoSegment).
        data = json.loads(exc.read().decode() or "{}")
    return data


def _coords(points: Iterable[LngLat]) -> str:
    return ";".join(f"{lng:.6f},{lat:.6f}" for lng, lat in points)


def straight_route(origin: LngLat, destination: LngLat) -> dict[str, Any]:
    distance = distance_m(origin, destination)
    return {
        "coordinates": [list(origin), list(destination)],
        "distance_m": distance,
        "duration_s": distance / (FALLBACK_SPEED_KMH / 3.6),
        "source": "straight",
    }


async def plan_route(base_url: str | None, origin: LngLat, destination: LngLat) -> dict[str, Any]:
    """Fastest driving route via OSRM, cached per origin/destination; straight line as fallback."""
    if not base_url:
        return straight_route(origin, destination)
    key = f"{origin[0]:.5f},{origin[1]:.5f};{destination[0]:.5f},{destination[1]:.5f}"
    cached = _ROUTE_CACHE.get_fresh(key)
    if cached is not None:
        return dict(cached)
    url = (
        f"{base_url.rstrip('/')}/route/v1/driving/{_coords([origin, destination])}"
        "?overview=full&geometries=geojson&alternatives=false&steps=false"
    )
    try:
        data = await asyncio.to_thread(_osrm_request, url)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.warning("osrm_route_failed", error=str(exc))
        return straight_route(origin, destination)
    if data.get("code") != "Ok" or not data.get("routes"):
        logger.warning("osrm_route_rejected", code=data.get("code"))
        return straight_route(origin, destination)
    best = data["routes"][0]
    route = {
        "coordinates": best["geometry"]["coordinates"],
        "distance_m": float(best["distance"]),
        "duration_s": float(best["duration"]),
        "source": "osrm",
    }
    _ROUTE_CACHE.put(key, route)
    return dict(route)


_ENDPOINTS = 2


def _polyline(points: list[LngLat]) -> dict[str, Any]:
    distance = sum(distance_m(a, b) for a, b in pairwise(points))
    return {
        "coordinates": [list(point) for point in points],
        "distance_m": distance,
        "duration_s": distance / (FALLBACK_SPEED_KMH / 3.6),
        "source": "straight",
    }


async def plan_path(base_url: str | None, points: list[LngLat]) -> dict[str, Any]:
    """Driving route through every point in order; a polyline as fallback."""
    if len(points) == _ENDPOINTS:
        return await plan_route(base_url, points[0], points[1])
    if not base_url or len(points) < _ENDPOINTS:
        return _polyline(points)
    url = (
        f"{base_url.rstrip('/')}/route/v1/driving/{_coords(points)}"
        "?overview=full&geometries=geojson&alternatives=false&steps=false"
    )
    try:
        data = await asyncio.to_thread(_osrm_request, url)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.warning("osrm_path_failed", error=str(exc))
        return _polyline(points)
    if data.get("code") != "Ok" or not data.get("routes"):
        return _polyline(points)
    best = data["routes"][0]
    return {
        "coordinates": best["geometry"]["coordinates"],
        "distance_m": float(best["distance"]),
        "duration_s": float(best["duration"]),
        "source": "osrm",
    }


#: Snapping a joystick position must answer fast or be skipped.
NEAREST_TIMEOUT_S = 2.0
NEAREST_MAX_M = 80


async def nearest_road(base_url: str | None, point: LngLat) -> LngLat:
    """The closest point on a drivable street, or ``point`` itself."""
    if not base_url:
        return point
    url = f"{base_url.rstrip('/')}/nearest/v1/driving/{_coords([point])}?number=1"
    try:
        data = await asyncio.to_thread(_osrm_request, url, NEAREST_TIMEOUT_S)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return point
    waypoints = data.get("waypoints") or []
    if data.get("code") != "Ok" or not waypoints:
        return point
    lng, lat = waypoints[0]["location"]
    snapped = (float(lng), float(lat))
    # Lejos de cualquier calle (campo abierto, predio) se respeta lo que maneja el usuario.
    return snapped if distance_m(point, snapped) <= NEAREST_MAX_M else point


async def _match_window(base_url: str, points: list[LngLat]) -> list[LngLat] | None:
    radiuses = ";".join([str(GPS_RADIUS_M)] * len(points))
    query = urllib.parse.urlencode(
        {
            "geometries": "geojson",
            "overview": "full",
            "gaps": "split",
            "tidy": "true",
            "radiuses": radiuses,
        }
    )
    url = f"{base_url.rstrip('/')}/match/v1/driving/{_coords(points)}?{query}"
    try:
        data = await asyncio.to_thread(_osrm_request, url)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.warning("osrm_match_failed", error=str(exc))
        return None
    if data.get("code") == "TooBig":
        raise _TooBigError
    if data.get("code") != "Ok" or not data.get("matchings"):
        return None
    geometry: list[LngLat] = []
    for matching in data["matchings"]:
        segment = _as_points(matching["geometry"]["coordinates"])
        if geometry and segment and distance_m(geometry[-1], segment[0]) < 1:
            segment = segment[1:]
        geometry.extend(segment)
    return geometry


async def match_trail(
    base_url: str | None, cache_key: str, points: list[LngLat]
) -> tuple[list[LngLat], bool]:
    """Snap the GPS trail to the road network.

    Matching is incremental: the snapped geometry and the number of input
    points already matched are cached per ``cache_key`` (the transfer), so each
    poll only sends the new fixes. Windows that cannot be matched keep their
    raw points. Returns (geometry, fully_matched).
    """
    global _match_window_size  # noqa: PLW0603
    points = dedupe(points)
    if not base_url or len(points) < 2:  # noqa: PLR2004
        return points, False
    cached = _MATCH_CACHE.get_fresh(cache_key)
    if cached and cached["first"] == points[0] and cached["inputs"] <= len(points):
        geometry: list[LngLat] = list(cached["geometry"])
        start, fully_matched = cached["inputs"] - 1, cached["matched"]
    else:
        geometry, start, fully_matched = [], 0, True
    while start < len(points) - 1:
        window = points[start : start + _match_window_size]
        try:
            snapped = await _match_window(base_url, window)
        except _TooBigError:
            if _match_window_size > MIN_MATCH_WINDOW:
                _match_window_size = max(MIN_MATCH_WINDOW, _match_window_size // 2)
                logger.info("osrm_match_window_reduced", size=_match_window_size)
                continue
            snapped = None
        if snapped is None:
            snapped, fully_matched = window, False
        if geometry and snapped and distance_m(geometry[-1], snapped[0]) < 1:
            snapped = snapped[1:]
        geometry.extend(snapped)
        start += len(window) - 1  # la ventana siguiente comparte el último punto
    _MATCH_CACHE.put(
        cache_key,
        {"first": points[0], "inputs": len(points), "geometry": geometry, "matched": fully_matched},
    )
    return geometry, fully_matched


async def resolve_active_route(
    base_url: str | None,
    cache_key: str,
    planned: dict[str, Any],
    destination: LngLat,
    current: LngLat,
) -> tuple[dict[str, Any], bool, float]:
    """Route the vehicle should follow now.

    * On (or back on) the planned route → planned route, cached detour dropped.
    * Off the planned route but still on the last recalculated route → keep it.
    * Otherwise → recalculate from the current position to the destination.

    Returns (active route, rerouted, deviation from the planned route in metres).
    """
    _, deviation, _ = split_route(current, _as_points(planned["coordinates"]))
    if deviation <= OFF_ROUTE_M:
        _REROUTE_CACHE.pop(cache_key, None)
        return planned, False, deviation
    detour = _REROUTE_CACHE.get_fresh(cache_key)
    if detour is not None:
        _, detour_lateral, _ = split_route(current, _as_points(detour["coordinates"]))
        if detour_lateral <= REJOIN_M:
            return detour, True, deviation
    detour = await plan_route(base_url, current, destination)
    _REROUTE_CACHE.put(cache_key, detour)
    logger.info("transfer_rerouted", transfer=cache_key, deviation_m=round(deviation))
    return detour, True, deviation


# ---------------------------------------------------------------- progress


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def raw_trail(positions: list[dict[str, Any]]) -> list[LngLat]:
    return [
        (float(p["longitude"]), float(p["latitude"]))
        for p in positions
        if p.get("latitude") is not None and p.get("longitude") is not None
    ]


def build_transfer_progress(
    *,
    route: dict[str, Any],
    destination: LngLat,
    positions: list[dict[str, Any]],
    now: datetime,
    trail: list[LngLat] | None = None,
    active_route: dict[str, Any] | None = None,
    rerouted: bool = False,
    deviation_m: float | None = None,
    arrival_radius_m: float | None = None,
) -> dict[str, Any]:
    """Trail, current position, progress, ETA, arrival and deviation for a transfer.

    ``trail`` is the (optionally street-matched) driven path; ``active_route``
    the route currently being followed (the planned one or a recalculation).
    ``arrival_radius_m`` is the destination site's geofence radius.
    """
    driven = trail if trail is not None else raw_trail(positions)
    active = active_route or route
    result: dict[str, Any] = {
        "trail": [list(point) for point in downsample(driven)],
        "remaining_route": [list(point) for point in downsample(_as_points(active["coordinates"]))],
        "position": None,
        "progress": 0.0,
        "remaining_m": round(active["distance_m"]),
        "eta": None,
        "arrived": False,
        "rerouted": False,
        "off_route": False,
        "off_route_m": 0.0,
    }
    raw = raw_trail(positions)
    if not raw:
        return result
    last = positions[-1]
    current = raw[-1]
    result["position"] = {
        "latitude": current[1],
        "longitude": current[0],
        "speed_kmh": round(float(last.get("speed") or 0) * KNOTS_TO_KMH, 1),
        "course": float(last.get("course") or 0),
        "fix_time": _parse_time(last.get("fixTime")),
    }
    arrived = distance_m(current, destination) <= (arrival_radius_m or ARRIVAL_RADIUS_M)
    active_points = _as_points(active["coordinates"])
    active_total = route_length_m(active_points) or active["distance_m"] or 1.0
    along, lateral, remaining_geometry = split_route(current, active_points)
    remaining = 0.0 if arrived else max(active_total - along, 0.0)
    if rerouted:
        # Sobre una ruta recalculada el avance se mide con lo recorrido realmente.
        travelled = route_length_m(driven)
        progress = travelled / (travelled + remaining) if travelled + remaining else 0.0
    else:
        progress = along / active_total
    deviation = lateral if deviation_m is None else deviation_m
    result.update(
        remaining_route=[] if arrived else [list(p) for p in downsample(remaining_geometry)],
        progress=1.0 if arrived else round(max(0.0, min(progress, 0.999)), 4),
        remaining_m=round(remaining),
        arrived=arrived,
        rerouted=rerouted and not arrived,
        off_route=not arrived and not rerouted and deviation > OFF_ROUTE_M,
        off_route_m=round(deviation),
    )
    if not arrived and active["distance_m"] > 0:
        result["eta"] = now + timedelta(seconds=active["duration_s"] * (remaining / active_total))
    return result
