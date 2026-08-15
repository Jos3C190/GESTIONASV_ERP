"""Persistence models for versioned location codes and staged bulk jobs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class LocationCodeScheme(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "location_code_schemes"

    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    separator: Mapped[str] = mapped_column(String(3), nullable=False, server_default="-")
    segments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint("version > 0", name="ck_location_code_schemes_version_positive"),
        UniqueConstraint(
            "warehouse_id", "version", name="uq_location_code_schemes_warehouse_version"
        ),
        UniqueConstraint(
            "id",
            "warehouse_id",
            "version",
            name="uq_location_code_schemes_identity_scope_version",
        ),
        Index(
            "uq_location_code_schemes_active",
            "warehouse_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
    )


class LocationCodeAlias(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "location_code_aliases"

    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    alias_code: Mapped[str] = mapped_column(String(120), nullable=False)
    code_scheme_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True)
    )
    scheme_version: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(32), nullable=False, server_default="recode")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["location_id", "warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            name="fk_location_code_aliases_location_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["code_scheme_id", "warehouse_id", "scheme_version"],
            [
                "location_code_schemes.id",
                "location_code_schemes.warehouse_id",
                "location_code_schemes.version",
            ],
            name="fk_location_code_aliases_scheme_scope_version",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(code_scheme_id IS NULL) = (scheme_version IS NULL)",
            name="ck_location_code_aliases_scheme_reference_complete",
        ),
        Index(
            "uq_location_code_aliases_warehouse_code",
            "warehouse_id",
            func.lower(alias_code),
            unique=True,
        ),
        Index("ix_location_code_aliases_location", "location_id"),
    )


class LocationBatchJob(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "location_batch_jobs"

    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="preview")
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    input_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    code_scheme_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    scheme_version: Mapped[int] = mapped_column(Integer, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    create_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    update_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        ForeignKeyConstraint(
            ["code_scheme_id", "warehouse_id", "scheme_version"],
            [
                "location_code_schemes.id",
                "location_code_schemes.warehouse_id",
                "location_code_schemes.version",
            ],
            name="fk_location_batch_jobs_scheme_scope_version",
            ondelete="RESTRICT",
        ),
        CheckConstraint("kind IN ('generate','import')", name="ck_location_batch_jobs_kind"),
        CheckConstraint(
            "status IN ('preview','publishing','published','failed','cancelled')",
            name="ck_location_batch_jobs_status",
        ),
        UniqueConstraint(
            "warehouse_id",
            "kind",
            "idempotency_key",
            name="uq_location_batch_jobs_idempotency",
        ),
        Index("ix_location_batch_jobs_warehouse_created", "warehouse_id", "created_at"),
    )


class LocationBatchRow(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "location_batch_rows"

    job_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("location_batch_jobs.id", ondelete="CASCADE"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str | None] = mapped_column(String(120))
    normalized_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    diff: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    errors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    published_location_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint(
            "operation IN ('create','update','unchanged','conflict','error')",
            name="ck_location_batch_rows_operation",
        ),
        UniqueConstraint("job_id", "row_number", name="uq_location_batch_rows_job_row"),
        Index("ix_location_batch_rows_job_operation", "job_id", "operation"),
    )
