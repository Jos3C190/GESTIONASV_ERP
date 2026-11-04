"""What a phone or an installed GPS needs to start reporting, and how to tell it did.

The ERP cannot configure a device remotely: it only hands over the server address
and, for the phone app, a QR code carrying the same settings.
"""

from __future__ import annotations

import ipaddress
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlencode, urlsplit

#: Prefix of the identifiers generated for phones; it also tells which guide to show.
PHONE_PREFIX = "GS-"

#: Same as Traccar's default ``status.timeout``: beyond it the device counts as silent.
REPORTING_WINDOW = timedelta(minutes=10)

#: Stopped vehicles still report every 5 minutes, so they do not look silent.
_PHONE_SETTINGS = {"accuracy": "high", "distance": 50, "heartbeat": 300, "buffer": "true"}

Signal = Literal["waiting", "reporting", "silent"]

#: Believable limits: above them the reading is in another unit or is noise.
MAX_VEHICLE_VOLTS = 60
MAX_SATELLITES = 64
MAX_ENGINE_HOURS_MS = 1_000_000 * 3_600_000
TEMPERATURE_RANGE_C = (-50, 150)


@dataclass(frozen=True, slots=True)
class TrackerModel:
    key: str
    brand: str
    models: str
    port: int
    #: These send a 12-digit id: the last 11 digits of the IMEI with a leading zero.
    short_identifier: bool = False


@dataclass(frozen=True, slots=True)
class PublicServer:
    url: str
    host: str
    private: bool


#: Ports from https://www.traccar.org/devices/ ; each one is published in ``compose.yaml``.
TRACKER_MODELS: tuple[TrackerModel, ...] = (
    TrackerModel("gt06", "Concox / Jimi", "GT06 y compatibles", 5023),
    TrackerModel("teltonika", "Teltonika", "Series FMB y FMC", 5027),
    TrackerModel("gps103", "Coban", "TK103-2B, GPS-103", 5001),
    TrackerModel("tk103", "Coban", "TK103A, TK103B", 5002, short_identifier=True),
    TrackerModel("queclink", "Queclink", "Series GL y GV", 5004),
    TrackerModel("sinotrack", "Sinotrack", "ST-901", 5013),
)


def _number(value: object, low: float, high: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if low <= value <= high else None


def device_readings(attributes: Mapping[str, Any]) -> dict[str, bool | float]:
    """What a device reported that is safe to show, without guessing.

    Names and units are Traccar's, but it warns the voltage unit varies by device, so a
    value outside a believable range is left out rather than shown as if it were true.
    """
    ignition = attributes.get("ignition")
    hours = _number(attributes.get("hours"), 0, MAX_ENGINE_HOURS_MS)
    readings: dict[str, bool | float | None] = {
        "ignition": ignition if isinstance(ignition, bool) else None,
        "voltage": _number(attributes.get("power"), 0.1, MAX_VEHICLE_VOLTS),
        "satellites": _number(attributes.get("sat"), 0, MAX_SATELLITES),
        "engine_hours": None if hours is None else hours / 3_600_000,
        "temperature": _number(attributes.get("temp1"), *TEMPERATURE_RANGE_C),
    }
    return {key: value for key, value in readings.items() if value is not None}


def enabled_trackers(setting: str | None) -> tuple[TrackerModel, ...]:
    """Models to offer: a model whose port is closed would be a dead end. Empty means all."""
    keys = {key.strip() for key in (setting or "").split(",") if key.strip()}
    return tuple(model for model in TRACKER_MODELS if not keys or model.key in keys)


def is_private_host(host: str) -> bool:
    """Whether a vehicle on mobile data could not reach this address."""
    name = host.lower()
    if name == "localhost" or name.endswith((".local", ".localhost")):
        return True
    try:
        address = ipaddress.ip_address(name)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local


def public_server(value: str | None) -> PublicServer | None:
    """The address devices report to, or None when it is missing or malformed."""
    parts = urlsplit((value or "").strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return None
    url = f"{parts.scheme}://{parts.netloc}"
    return PublicServer(url=url, host=parts.hostname, private=is_private_host(parts.hostname))


def new_phone_identifier() -> str:
    """The reporting port has no login, so this id must be hard to guess."""
    return f"{PHONE_PREFIX}{secrets.token_hex(6).upper()}"


def is_phone_identifier(unique_id: str | None) -> bool:
    return bool(unique_id) and str(unique_id).startswith(PHONE_PREFIX)


def client_config_uri(server_url: str, unique_id: str) -> str:
    """URL for the QR the phone app scans: the server plus its settings as query keys."""
    return f"{server_url}?{urlencode({'id': unique_id, **_PHONE_SETTINGS})}"


def device_signal(last_update: datetime | None, now: datetime) -> Signal:
    if last_update is None:
        return "waiting"
    return "reporting" if now - last_update <= REPORTING_WINDOW else "silent"
