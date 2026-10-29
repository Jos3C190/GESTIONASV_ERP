"""GPS tracking DTOs (Traccar-backed)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


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


LngLat = Annotated[list[float], Field(min_length=2, max_length=2)]


class CircleShape(BaseModel):
    type: Literal["circle"]
    center: LngLat
    radius_m: float = Field(gt=10, le=100_000)


class PolygonShape(BaseModel):
    type: Literal["polygon"]
    coordinates: list[LngLat] = Field(min_length=3, max_length=500)


GeofenceShape = Annotated[CircleShape | PolygonShape, Field(discriminator="type")]


class GeofenceOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    shape: GeofenceShape
    speed_limit_kmh: int | None = None


class GeofenceCreate(BaseModel):
    company_id: uuid.UUID
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    shape: GeofenceShape
    speed_limit_kmh: int | None = Field(default=None, ge=5, le=200)


class TrackingEventOut(BaseModel):
    id: int
    type: str
    event_time: datetime | None = None
    device_id: int
    device_name: str
    device_unique_id: str
    geofence_name: str | None = None
    alarm: str | None = None
    speed_kmh: float | None = None
    latitude: float | None = None
    longitude: float | None = None
