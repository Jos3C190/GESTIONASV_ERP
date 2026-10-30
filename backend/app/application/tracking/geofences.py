"""Geofences and events on top of Traccar.

Traccar stores geofence areas as WKT with *latitude first*:
``CIRCLE (lat lon, radius)`` and ``POLYGON ((lat lon, lat lon, ...))``. The ERP
exposes GeoJSON-style ``[lng, lat]`` pairs and converts at this boundary.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.application.tracking.traccar import KNOTS_TO_KMH

#: Event types the tracking module surfaces; the rest (online/offline/moving) is noise.
TRACKED_EVENT_TYPES = frozenset(
    {
        "geofenceEnter",
        "geofenceExit",
        "deviceOverspeed",
        "ignitionOn",
        "ignitionOff",
        "deviceStopped",
        "alarm",
        "maintenance",
    }
)

_COORDINATE_PARTS = 2
_MIN_POLYGON_POINTS = 3
_NUMBER = r"-?\d+(?:\.\d+)?"
_CIRCLE = re.compile(
    rf"^\s*CIRCLE\s*\(\s*({_NUMBER})\s+({_NUMBER})\s*,\s*({_NUMBER})\s*\)\s*$", re.I
)
_POLYGON = re.compile(r"^\s*POLYGON\s*\(\s*\((.+)\)\s*\)\s*$", re.I)


def parse_area(area: str) -> dict[str, Any] | None:
    """Translate Traccar WKT into the ERP shape; unsupported areas return ``None``."""
    if match := _CIRCLE.match(area or ""):
        lat, lon, radius = (float(value) for value in match.groups())
        return {"type": "circle", "center": [lon, lat], "radius_m": radius}
    if match := _POLYGON.match(area or ""):
        coordinates: list[list[float]] = []
        for pair in match.group(1).split(","):
            parts = pair.split()
            if len(parts) != _COORDINATE_PARTS:
                return None
            lat, lon = float(parts[0]), float(parts[1])
            coordinates.append([lon, lat])
        if len(coordinates) >= _MIN_POLYGON_POINTS and coordinates[0] == coordinates[-1]:
            coordinates.pop()
        if len(coordinates) < _MIN_POLYGON_POINTS:
            return None
        return {"type": "polygon", "coordinates": coordinates}
    return None


def build_area(shape: dict[str, Any]) -> str:
    """Translate the ERP shape into Traccar WKT."""
    if shape["type"] == "circle":
        lon, lat = shape["center"]
        return f"CIRCLE ({lat:.6f} {lon:.6f}, {float(shape['radius_m']):.1f})"
    ring = [*shape["coordinates"], shape["coordinates"][0]]
    return "POLYGON ((" + ", ".join(f"{lat:.6f} {lon:.6f}" for lon, lat in ring) + "))"


def to_geofence(item: dict[str, Any]) -> dict[str, Any] | None:
    shape = parse_area(str(item.get("area", "")))
    if shape is None:
        return None
    speed_limit = (item.get("attributes") or {}).get("speedLimit")
    speed_limit_kmh = (
        round(float(speed_limit) * KNOTS_TO_KMH)
        if isinstance(speed_limit, int | float | str) and speed_limit != ""
        else None
    )
    return {
        "id": item["id"],
        "name": str(item.get("name", "")),
        "description": item.get("description") or None,
        "shape": shape,
        "speed_limit_kmh": speed_limit_kmh,
    }


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_events(
    events: list[dict[str, Any]],
    devices: dict[int, dict[str, Any]],
    geofences: dict[int, str],
    positions: dict[int, dict[str, Any]],
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Enrich raw Traccar events with device, geofence and position details."""
    result: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") not in TRACKED_EVENT_TYPES:
            continue
        device = devices.get(event.get("deviceId") or 0)
        if device is None:
            continue
        position = positions.get(event.get("positionId") or 0)
        attributes = event.get("attributes") or {}
        result.append(
            {
                "id": event["id"],
                "type": event["type"],
                "event_time": _parse_time(event.get("eventTime")),
                "device_id": device["id"],
                "device_name": str(device.get("name", "")),
                "device_unique_id": str(device.get("uniqueId", "")),
                "geofence_id": event.get("geofenceId") or None,
                "geofence_name": geofences.get(event.get("geofenceId") or 0),
                "alarm": attributes.get("alarm"),
                "speed_kmh": round(float(position.get("speed") or 0) * KNOTS_TO_KMH, 1)
                if position
                else None,
                "latitude": position.get("latitude") if position else None,
                "longitude": position.get("longitude") if position else None,
            }
        )
    result.sort(
        key=lambda item: item["event_time"] or datetime.min.replace(tzinfo=UTC), reverse=True
    )
    return result[:limit]
