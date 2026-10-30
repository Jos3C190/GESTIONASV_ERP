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
