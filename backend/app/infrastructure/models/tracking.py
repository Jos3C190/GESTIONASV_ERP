"""Tracking bookkeeping kept by the ERP (Traccar holds no source data)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class TrackingSyncStateModel(Base):
    """Last reconciliation of a company's branch/warehouse geofences with Traccar."""

    __tablename__ = "tracking_sync_state"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    sites_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class TransferTrackModel(Base):
    """GPS trail of a closed transfer, kept by the ERP as evidence of the trip."""

    __tablename__ = "inventory_transfer_tracks"

    transfer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    traccar_device_id: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: ``[[lng, lat, iso_time, speed_kmh, course], ...]`` as reported by the device.
    points: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    #: Trail snapped to the street network (or the raw trail if matching failed).
    matched: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    trail_matched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    point_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distance_m: Mapped[Decimal] = mapped_column(Numeric(12, 1), nullable=False, default=0)
    max_speed_kmh: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    #: Recorded from the simulator's virtual GPS, not from the vehicle.
    simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "transfer_id"],
            ["inventory_transfers.company_id", "inventory_transfers.id"],
            name="fk_transfer_tracks_transfer",
            ondelete="CASCADE",
        ),
    )


ALERT_KINDS = ("arrived", "delayed", "long_stop", "gps_lost", "off_route")


class TrackingAlertModel(Base):
    """A condition detected on a transfer in transit; one open alert per transfer and kind."""

    __tablename__ = "tracking_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    transfer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    origin_branch_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    destination_branch_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    #: Raised from the simulator's virtual GPS.
    simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "transfer_id"],
            ["inventory_transfers.company_id", "inventory_transfers.id"],
            name="fk_tracking_alerts_transfer",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "kind IN ('arrived', 'delayed', 'long_stop', 'gps_lost', 'off_route')",
            name="ck_tracking_alerts_kind",
        ),
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')", name="ck_tracking_alerts_severity"
        ),
        Index(
            "uq_tracking_alerts_open",
            "transfer_id",
            "kind",
            unique=True,
            postgresql_where=text("resolved_at IS NULL"),
        ),
    )


SIMULATION_MODES = ("route", "joystick")
SIMULATION_STATES = ("running", "paused", "arrived", "ended")


class TrackingSimulationModel(Base):
    """A simulator session: a virtual GPS in Traccar that stands in for one vehicle.

    While a session is open, tracking reads the vehicle from the virtual device;
    the vehicle's real GPS keeps reporting to Traccar untouched.
    """

    __tablename__ = "tracking_simulations"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    traccar_device_id: Mapped[int] = mapped_column(Integer, nullable=False)
    device_unique_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    state: Mapped[str] = mapped_column(String(10), nullable=False, default="running")
    #: Planned path ``[[lng, lat], ...]``; empty while driving with the joystick.
    route: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    #: Planned stops ``[[lng, lat], ...]``: the first one is the starting point.
    stops: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    #: ``outbound`` or ``return`` (heading back to the starting point).
    leg: Mapped[str] = mapped_column(String(8), nullable=False, default="outbound")
    route_length_m: Mapped[Decimal] = mapped_column(Numeric(12, 1), nullable=False, default=0)
    progress_m: Mapped[Decimal] = mapped_column(Numeric(12, 1), nullable=False, default=0)
    speed_kmh: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=40)
    current_speed_kmh: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=0)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    course: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False, default=0)
    #: When ``progress_m`` was last computed (the engine's tick or a user action).
    advanced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    stop_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signal_lost_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_report_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "vehicle_id"],
            ["fleet_vehicles.company_id", "fleet_vehicles.id"],
            name="fk_tracking_simulations_vehicle",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_tracking_simulations_branch",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "transfer_id"],
            ["inventory_transfers.company_id", "inventory_transfers.id"],
            name="fk_tracking_simulations_transfer",
            ondelete="CASCADE",
        ),
        CheckConstraint("mode IN ('route', 'joystick')", name="ck_tracking_simulations_mode"),
        CheckConstraint(
            "state IN ('running', 'paused', 'arrived', 'ended')",
            name="ck_tracking_simulations_state",
        ),
        CheckConstraint("speed_kmh BETWEEN 1 AND 300", name="ck_tracking_simulations_speed"),
        CheckConstraint("leg IN ('outbound', 'return')", name="ck_tracking_simulations_leg"),
        CheckConstraint(
            "progress_m >= 0 AND progress_m <= route_length_m + 1",
            name="ck_tracking_simulations_progress",
        ),
        CheckConstraint(
            "(state = 'ended') = (ended_at IS NOT NULL)", name="ck_tracking_simulations_ended"
        ),
        Index(
            "uq_tracking_simulations_open_vehicle",
            "vehicle_id",
            unique=True,
            postgresql_where=text("state <> 'ended'"),
        ),
        Index("ix_tracking_simulations_company_state", "company_id", "state"),
        Index("ix_tracking_simulations_device", "traccar_device_id", "ended_at"),
    )
