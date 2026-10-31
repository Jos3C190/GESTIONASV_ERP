"""Idempotent preparation actions, separate from posted inventory movements."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPKMixin


class InventoryPreparationActionModel(UUIDPKMixin, Base):
    __tablename__ = "inventory_preparation_actions"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    handling_unit_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_preparation_action_key"),
        ForeignKeyConstraint(
            ["company_id", "handling_unit_id"],
            ["inventory_handling_units.company_id", "inventory_handling_units.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("action IN ('split','place')", name="ck_preparation_action"),
    )
