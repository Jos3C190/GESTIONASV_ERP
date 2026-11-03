"""GPS tracking DTOs (Traccar-backed)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

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


class TrackedVehicleOut(BaseModel):
    """Fleet record linked to a GPS device."""

    id: uuid.UUID
    code: str
    plate: str | None
    kind: str
    brand: str
    model: str
    branch_id: uuid.UUID
    branch_name: str
    operational_status: str
    driver_name: str | None = None
    transfer_code: str | None = None
    transfer_destination: str | None = None


class TrackedDeviceOut(BaseModel):
    id: int
    unique_id: str
    name: str
    status: Literal["online", "offline", "unknown"]
    last_update: datetime | None = None
    position: TrackedPositionOut | None = None
    vehicle: TrackedVehicleOut | None = None
    #: Virtual GPS of a simulator session standing in for the vehicle.
    simulated: bool = False


class TrackingSnapshotOut(BaseModel):
    configured: bool
    devices: list[TrackedDeviceOut]
    #: Vehicles in scope (not retired) and how many have a GPS device linked.
    vehicles_total: int = 0
    vehicles_with_gps: int = 0


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
    #: ``None`` = applies to every branch of the company.
    branch_id: uuid.UUID | None = None
    branch_name: str | None = None
    can_manage: bool = False
    #: Automatic geofence of a branch or warehouse; managed from those modules.
    system: bool = False


class GeofenceCreate(BaseModel):
    #: Branch the geofence applies to; omit for a company-wide geofence.
    branch_id: uuid.UUID | None = None
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
    geofence_id: int | None = None
    geofence_name: str | None = None
    #: The geofence is the automatic one of a branch or warehouse.
    geofence_system: bool = False
    alarm: str | None = None
    speed_kmh: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    simulated: bool = False


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
    received_at: datetime | None = None
    vehicle_code: str | None = None
    vehicle_name: str | None = None
    vehicle_plate: str | None = None
    driver_name: str | None = None
    origin: TransferPlaceOut
    destination: TransferPlaceOut
    #: The trip is being read from a simulator session.
    simulated: bool = False


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


class TrackingAlertOut(BaseModel):
    id: uuid.UUID
    transfer_id: uuid.UUID
    transfer_code: str | None = None
    vehicle_code: str | None = None
    kind: Literal["arrived", "delayed", "long_stop", "gps_lost", "off_route"]
    severity: Literal["info", "warning", "critical"]
    message: str
    details: dict[str, Any] = {}
    opened_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None = None
    acknowledged_at: datetime | None = None
    simulated: bool = False


class TrackingAlertsOut(BaseModel):
    items: list[TrackingAlertOut]
    unacknowledged: int
    #: False when the GPS server is not configured (no alerts can be raised).
    monitor_active: bool


class TransferTrackOut(TrackedTransferOut):
    gps_configured: bool
    #: The trail comes from the ERP copy taken when the transfer was received.
    track_stored: bool = False
    alerts: list[TrackingAlertOut] = []
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


class SiteWarehouseOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None = None
    is_central: bool
    status: str


class SiteOut(BaseModel):
    """A fixed place on the tracking map: a branch or a warehouse in its own building."""

    kind: Literal["branch", "warehouse"]
    id: uuid.UUID
    name: str
    code: str | None = None
    address: str | None = None
    latitude: float
    longitude: float
    radius_m: int
    status: str
    branch_id: uuid.UUID
    branch_name: str
    warehouses: list[SiteWarehouseOut] = []


class MissingSiteOut(BaseModel):
    kind: Literal["branch", "warehouse"]
    id: uuid.UUID
    name: str


class SiteSyncOut(BaseModel):
    configured: bool
    synced_at: datetime | None = None
    last_attempt_at: datetime | None = None
    error: str | None = None


class SitesOut(BaseModel):
    sites: list[SiteOut]
    missing: list[MissingSiteOut]
    sync: SiteSyncOut


# ---------------------------------------------------------------- simulator


class SimulatorVehicleOut(BaseModel):
    id: uuid.UUID
    code: str
    plate: str | None
    kind: str
    branch_id: uuid.UUID
    branch_name: str
    has_gps: bool
    #: Transfer in transit with this vehicle, to simulate its trip.
    transfer_id: uuid.UUID | None = None
    transfer_code: str | None = None
    #: Where a new session starts: last known position or the home branch.
    start: LngLat | None = None


class SimulationOut(BaseModel):
    id: uuid.UUID
    vehicle_id: uuid.UUID
    vehicle_code: str
    vehicle_plate: str | None
    branch_id: uuid.UUID
    transfer_id: uuid.UUID | None = None
    transfer_code: str | None = None
    traccar_device_id: int
    mode: Literal["route", "joystick"]
    state: Literal["running", "paused", "arrived", "ended"]
    route: list[LngLat] = []
    #: Planned stops; the first one is where the session started.
    stops: list[LngLat] = []
    #: ``return`` while heading back to the starting point.
    leg: Literal["outbound", "return"] = "outbound"
    route_length_m: float
    progress_m: float
    speed_kmh: float
    current_speed_kmh: float
    longitude: float
    latitude: float
    course: float
    #: When ``progress_m`` was measured: maps replay the motion between two measurements.
    advanced_at: datetime | None = None
    stop_until: datetime | None = None
    signal_lost_until: datetime | None = None
    last_report_at: datetime | None = None
    started_at: datetime
    started_by_name: str | None = None
    can_control: bool = False


class SimulatorOut(BaseModel):
    #: The deployment allows simulation (never in production).
    enabled: bool
    #: Server clock, so the browser can line up ``advanced_at`` with its own clock.
    server_time: datetime | None = None
    #: The GPS server is configured, so a virtual device can report.
    ready: bool
    can_simulate: bool
    vehicles: list[SimulatorVehicleOut] = []
    sessions: list[SimulationOut] = []


class SimulationCreate(BaseModel):
    vehicle_id: uuid.UUID
    mode: Literal["route", "joystick"]
    #: Route mode: follow this transfer from origin to destination...
    transfer_id: uuid.UUID | None = None
    #: ...or drive through these points (the first one is the start).
    waypoints: list[LngLat] = Field(default_factory=list, max_length=25)
    #: Joystick mode: where the unit appears (defaults to its last known position).
    start: LngLat | None = None
    speed_kmh: float = Field(default=40, ge=1, le=300)


class SimulationControl(BaseModel):
    action: Literal[
        "pause",
        "resume",
        "stop",
        "signal_loss",
        "signal_restore",
        "detour",
        "speed",
        "restart",
        "return",
        "outbound",
        "take_control",
    ]
    #: Length of a timed stop or signal loss.
    minutes: int | None = Field(default=None, ge=1, le=240)
    speed_kmh: float | None = Field(default=None, ge=1, le=300)


class SimulationDrive(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    course: float = Field(ge=0, lt=360)
    speed_kmh: float = Field(ge=0, le=300)
    #: Snap the position to the nearest street.
    snap: bool = False


class SimulationDriveOut(BaseModel):
    longitude: float
    latitude: float
    snapped: bool
    reported: bool
