"""GPS tracking DTOs (Traccar-backed)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TrackedPositionOut(BaseModel):
    latitude: float
    longitude: float
    speed_kmh: float
    course: float
    fix_time: datetime | None = None
    address: str | None = None
    ignition: bool | None = None
    battery_level: float | None = None


class TrackedDeviceOut(BaseModel):
    id: int
    unique_id: str
    name: str
    status: Literal["online", "offline", "unknown"]
    last_update: datetime | None = None
    position: TrackedPositionOut | None = None


class TrackingSnapshotOut(BaseModel):
    configured: bool
    devices: list[TrackedDeviceOut]
