"""Audited confirmation that the current physical handling-unit label was placed."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPKMixin


class InventoryLabelConfirmationModel(UUIDPKMixin, Base):
    __tablename__ = "inventory_label_confirmations"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    handling_unit_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    label_print_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    handling_unit_code: Mapped[str] = mapped_column(String(120), nullable=False)
    label_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    label_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "idempotency_key", name="uq_inventory_label_confirmations_key"
        ),
        UniqueConstraint(
            "company_id",
            "handling_unit_id",
            "label_revision",
            name="uq_inventory_label_confirmations_unit_revision",
        ),
        ForeignKeyConstraint(
            ["company_id", "handling_unit_id"],
            ["inventory_handling_units.company_id", "inventory_handling_units.id"],
            ondelete="RESTRICT",
            name="fk_inventory_label_confirmations_unit_company",
        ),
        ForeignKeyConstraint(
            ["label_print_id"],
            ["inventory_label_prints.id"],
            ondelete="RESTRICT",
            name="fk_inventory_label_confirmations_print",
        ),
        ForeignKeyConstraint(
            ["confirmed_by"],
            ["users.id"],
            ondelete="RESTRICT",
            name="fk_inventory_label_confirmations_actor",
        ),
    )


__all__ = ["InventoryLabelConfirmationModel"]
