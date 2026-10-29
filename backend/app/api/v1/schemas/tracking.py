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


class TransferPlaceOut(BaseModel):
    warehouse_name: str
    branch_name: str
    latitude: float | None = None
    longitude: float | None = None


class TrackedTransferOut(BaseModel):
    id: uuid.UUID
    code: str
    status: str
    dispatched_at: datetime | None = None
    vehicle_code: str | None = None
    vehicle_name: str | None = None
    origin: TransferPlaceOut
    destination: TransferPlaceOut


class TransferRouteOut(BaseModel):
    coordinates: list[LngLat]
    distance_m: float
    duration_s: float
    source: Literal["osrm", "straight"]


class TransferPositionOut(BaseModel):
    latitude: float
    longitude: float
    speed_kmh: float
    course: float
    fix_time: datetime | None = None


class TransferTrackOut(TrackedTransferOut):
    gps_configured: bool
    device_found: bool
    route: TransferRouteOut | None = None
    trail: list[LngLat] = []
    #: Whether the driven path was snapped to the street network.
    trail_matched: bool = False
    #: Route still ahead of the vehicle (planned or recalculated).
    remaining_route: list[LngLat] = []
    rerouted: bool = False
    position: TransferPositionOut | None = None
    progress: float = 0
    remaining_m: float | None = None
    eta: datetime | None = None
    arrived: bool = False
    off_route: bool = False
    off_route_m: float = 0
