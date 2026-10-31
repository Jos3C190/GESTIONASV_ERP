"""Revocable, least-privilege public links for inventory unit traceability."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPKMixin


class InventoryTraceCapabilityModel(UUIDPKMixin, Base):
    __tablename__ = "inventory_trace_capabilities"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    handling_unit_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "token_digest",
            name="uq_inventory_trace_capabilities_token_digest",
        ),
        ForeignKeyConstraint(
            ["company_id", "handling_unit_id"],
            ["inventory_handling_units.company_id", "inventory_handling_units.id"],
            ondelete="CASCADE",
            name="fk_inventory_trace_capabilities_unit_company",
        ),
        ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="RESTRICT",
            name="fk_inventory_trace_capabilities_created_by",
        ),
        ForeignKeyConstraint(
            ["revoked_by"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_inventory_trace_capabilities_revoked_by",
        ),
        Index(
            "ix_inventory_trace_capabilities_unit_active",
            "company_id",
            "handling_unit_id",
            "revoked_at",
        ),
        Index("ix_inventory_trace_capabilities_created_at", "created_at"),
    )


__all__ = ["InventoryTraceCapabilityModel"]
