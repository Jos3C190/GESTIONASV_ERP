"""Convert GPS positions between Traccar's shape and the compact form stored by the ERP."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from itertools import pairwise
from typing import Any

from app.application.tracking.alerts import Fix
from app.application.tracking.traccar import KNOTS_TO_KMH
from app.application.tracking.transfers import distance_m


def _time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _valid(position: dict[str, Any]) -> bool:
    return position.get("latitude") is not None and position.get("longitude") is not None


def compact_points(positions: Sequence[dict[str, Any]]) -> list[list[Any]]:
    """``[lng, lat, fix_time, speed_kmh, course]`` per position, in order."""
    return [
        [
            float(p["longitude"]),
            float(p["latitude"]),
            p.get("fixTime"),
            round(float(p.get("speed") or 0) * KNOTS_TO_KMH, 1),
            float(p.get("course") or 0),
        ]
        for p in positions
        if _valid(p)
    ]


def positions_from_points(points: Sequence[Sequence[Any]]) -> list[dict[str, Any]]:
    """Back to Traccar's shape so the same progress rules apply to stored trails."""
    return [
        {
            "longitude": point[0],
            "latitude": point[1],
            "fixTime": point[2],
            "speed": float(point[3] or 0) / KNOTS_TO_KMH,
            "course": point[4] if len(point) > 4 else 0,  # noqa: PLR2004 - optional course
        }
        for point in points
    ]


def fixes(positions: Sequence[dict[str, Any]]) -> list[Fix]:
    result: list[Fix] = []
    for p in positions:
        at = _time(p.get("fixTime"))
        if at is None or not _valid(p):
            continue
        result.append(
            Fix(
                at=at,
                point=(float(p["longitude"]), float(p["latitude"])),
                speed_kmh=float(p.get("speed") or 0) * KNOTS_TO_KMH,
            )
        )
    return result


def trail_stats(points: Sequence[Sequence[Any]]) -> tuple[float, float | None]:
    """Driven distance in metres and top speed in km/h."""
    distance = sum(distance_m((a[0], a[1]), (b[0], b[1])) for a, b in pairwise(points))
    speeds = [float(point[3]) for point in points if point[3] is not None]
    return round(distance, 1), (max(speeds) if speeds else None)
