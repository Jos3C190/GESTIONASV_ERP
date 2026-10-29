"""Live tracking of an inventory transfer between two branches.

Pure helpers: the router supplies the transfer, the branch coordinates, the
vehicle's GPS history from Traccar and a planned route, and these functions
derive progress, ETA, arrival and route deviation.
"""

from __future__ import annotations

import asyncio
import json
import math
import urllib.error
import urllib.request
from collections import OrderedDict
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Any

from app.application.tracking.traccar import KNOTS_TO_KMH

LngLat = tuple[float, float]

EARTH_RADIUS_M = 6_371_000
#: Distance to the destination branch that counts as arrived.
ARRIVAL_RADIUS_M = 300
#: Lateral distance from the planned route that counts as a deviation.
OFF_ROUTE_M = 1_000
#: Speed assumed for straight-line fallbacks when no routing service answers.
FALLBACK_SPEED_KMH = 45
MAX_TRAIL_POINTS = 500


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


def locate_on_route(point: LngLat, route: list[LngLat]) -> tuple[float, float]:
    """Return (distance travelled along the route, lateral distance) in metres."""
    best_lateral = math.inf
    best_along = 0.0
    travelled = 0.0
    for start, end in pairwise(route):
        segment = distance_m(start, end)
        t, closest = _project(point, start, end)
        lateral = distance_m(point, closest)
        if lateral < best_lateral:
            best_lateral = lateral
            best_along = travelled + segment * t
        travelled += segment
    return best_along, (0.0 if best_lateral is math.inf else best_lateral)


def route_length_m(route: list[LngLat]) -> float:
    return sum(distance_m(a, b) for a, b in pairwise(route))


def downsample(points: list[LngLat], limit: int = MAX_TRAIL_POINTS) -> list[LngLat]:
    if len(points) <= limit:
        return points
    step = (len(points) - 1) / (limit - 1)
    return [points[round(i * step)] for i in range(limit)]


def straight_route(origin: LngLat, destination: LngLat) -> dict[str, Any]:
    distance = distance_m(origin, destination)
    return {
        "coordinates": [list(origin), list(destination)],
        "distance_m": distance,
        "duration_s": distance / (FALLBACK_SPEED_KMH / 3.6),
        "source": "straight",
    }


_ROUTE_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_ROUTE_CACHE_SIZE = 64


def _osrm_request(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "erp-tracking/1.0"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=8) as response:  # noqa: S310
        data: dict[str, Any] = json.loads(response.read().decode())
    return data


async def plan_route(base_url: str | None, origin: LngLat, destination: LngLat) -> dict[str, Any]:
    """Driving route via OSRM, cached per origin/destination; straight line as fallback."""
    if not base_url:
        return straight_route(origin, destination)
    key = f"{origin[0]:.5f},{origin[1]:.5f};{destination[0]:.5f},{destination[1]:.5f}"
    if key in _ROUTE_CACHE:
        _ROUTE_CACHE.move_to_end(key)
        return _ROUTE_CACHE[key]
    url = (
        f"{base_url.rstrip('/')}/route/v1/driving/{key}"
        "?overview=full&geometries=geojson&alternatives=false&steps=false"
    )
    try:
        data = await asyncio.to_thread(_osrm_request, url)
        best = data["routes"][0]
        route = {
            "coordinates": best["geometry"]["coordinates"],
            "distance_m": float(best["distance"]),
            "duration_s": float(best["duration"]),
            "source": "osrm",
        }
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError):
        return straight_route(origin, destination)
    _ROUTE_CACHE[key] = route
    if len(_ROUTE_CACHE) > _ROUTE_CACHE_SIZE:
        _ROUTE_CACHE.popitem(last=False)
    return route


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_transfer_progress(
    *,
    route: dict[str, Any],
    destination: LngLat,
    positions: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    """Trail, current position, progress, ETA, arrival and deviation for a transfer."""
    trail: list[LngLat] = [
        (float(p["longitude"]), float(p["latitude"]))
        for p in positions
        if p.get("latitude") is not None and p.get("longitude") is not None
    ]
    result: dict[str, Any] = {
        "trail": [list(point) for point in downsample(trail)],
        "position": None,
        "progress": 0.0,
        "remaining_m": route["distance_m"],
        "eta": None,
        "arrived": False,
        "off_route": False,
        "off_route_m": 0.0,
    }
    if not trail:
        return result
    last = positions[-1]
    current = trail[-1]
    result["position"] = {
        "latitude": current[1],
        "longitude": current[0],
        "speed_kmh": round(float(last.get("speed") or 0) * KNOTS_TO_KMH, 1),
        "course": float(last.get("course") or 0),
        "fix_time": _parse_time(last.get("fixTime")),
    }
    coordinates: list[LngLat] = [(float(lng), float(lat)) for lng, lat in route["coordinates"]]
    total = route_length_m(coordinates) or route["distance_m"] or 1.0
    along, lateral = locate_on_route(current, coordinates)
    arrived = distance_m(current, destination) <= ARRIVAL_RADIUS_M
    progress = 1.0 if arrived else max(0.0, min(along / total, 0.999))
    remaining = 0.0 if arrived else max(total - along, 0.0)
    result.update(
        progress=round(progress, 4),
        remaining_m=round(remaining),
        arrived=arrived,
        off_route=not arrived and lateral > OFF_ROUTE_M,
        off_route_m=round(lateral),
    )
    if not arrived and route["distance_m"] > 0:
        remaining_s = route["duration_s"] * (remaining / total)
        result["eta"] = now + timedelta(seconds=remaining_s)
    return result
