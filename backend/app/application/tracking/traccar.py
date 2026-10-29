"""Read-only Traccar client for the tracking module.

The ERP talks to Traccar server-side so its credentials never reach the browser.
Devices are scoped to a company through the custom device attribute
``erpCompanyId`` configured in Traccar.
"""

from __future__ import annotations

import asyncio
import base64
import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, cast

KNOTS_TO_KMH = 1.852
COMPANY_ATTRIBUTE = "erpCompanyId"


class TraccarUnavailableError(RuntimeError):
    """Traccar could not be reached or rejected the service credentials."""


def _get_json(url: str, user: str, password: str) -> Any:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    request = urllib.request.Request(  # noqa: S310
        url, headers={"Authorization": f"Basic {token}", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:  # noqa: S310
            return json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise TraccarUnavailableError(str(exc)) from exc


async def fetch_traccar_snapshot(
    base_url: str, user: str, password: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return Traccar devices and their latest positions."""
    root = base_url.rstrip("/")
    devices, positions = await asyncio.gather(
        asyncio.to_thread(_get_json, f"{root}/api/devices", user, password),
        asyncio.to_thread(_get_json, f"{root}/api/positions", user, password),
    )
    return cast(list[dict[str, Any]], devices), cast(list[dict[str, Any]], positions)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_tracked_devices(
    devices: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    company_id: str,
) -> list[dict[str, Any]]:
    """Join devices with their latest position, keeping only the company's devices."""
    latest = {position.get("deviceId"): position for position in positions}
    tracked: list[dict[str, Any]] = []
    for device in devices:
        attributes = device.get("attributes") or {}
        if str(attributes.get(COMPANY_ATTRIBUTE, "")).strip().lower() != company_id.lower():
            continue
        position = latest.get(device.get("id"))
        position_attributes = (position or {}).get("attributes") or {}
        tracked.append(
            {
                "id": device.get("id"),
                "unique_id": str(device.get("uniqueId", "")),
                "name": str(device.get("name", "")),
                "status": device.get("status") or "unknown",
                "last_update": _parse_time(device.get("lastUpdate")),
                "position": None
                if position is None
                else {
                    "latitude": position.get("latitude"),
                    "longitude": position.get("longitude"),
                    "speed_kmh": round(float(position.get("speed") or 0) * KNOTS_TO_KMH, 1),
                    "course": float(position.get("course") or 0),
                    "fix_time": _parse_time(position.get("fixTime")),
                    "address": position.get("address"),
                    "ignition": position_attributes.get("ignition"),
                    "battery_level": position_attributes.get("batteryLevel"),
                },
            }
        )
    return sorted(tracked, key=lambda item: item["name"])
