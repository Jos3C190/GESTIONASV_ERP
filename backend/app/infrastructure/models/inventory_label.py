"""Append-only print history for inventory labels."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPKMixin


class InventoryLabelPrintModel(UUIDPKMixin, Base):
    """A successful label print attempt, retaining the exact printed data."""

    __tablename__ = "inventory_label_prints"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_lot_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_lot_detail_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    handling_unit_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity_printed: Mapped[int] = mapped_column(Integer, nullable=False)
    print_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(16), nullable=False)
    label_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    printed_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    printed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_label_prints_company_id"),
        UniqueConstraint(
            "company_id", "idempotency_key", name="uq_inventory_label_prints_idempotency"
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_inventory_label_prints_item_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_lot_id"],
            ["inventory_lots.company_id", "inventory_lots.id"],
            ondelete="RESTRICT",
            name="fk_inventory_label_prints_lot_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_lot_detail_id"],
            ["inventory_lot_details.company_id", "inventory_lot_details.id"],
            ondelete="RESTRICT",
            name="fk_inventory_label_prints_detail_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "handling_unit_id"],
            ["inventory_handling_units.company_id", "inventory_handling_units.id"],
            ondelete="RESTRICT",
            name="fk_inventory_label_prints_unit_company",
        ),
        ForeignKeyConstraint(
            ["printed_by"],
            ["users.id"],
            ondelete="RESTRICT",
            name="fk_inventory_label_prints_actor",
        ),
        CheckConstraint("quantity_printed > 0", name="ck_inventory_label_prints_quantity"),
        CheckConstraint("reason IN ('initial','reprint')", name="ck_inventory_label_prints_reason"),
        CheckConstraint(
            "(inventory_lot_detail_id IS NOT NULL) <> (handling_unit_id IS NOT NULL)",
            name="ck_inventory_label_prints_target",
        ),
        Index(
            "ix_inventory_label_prints_lot_date",
            "company_id",
            "inventory_lot_id",
            "print_date",
        ),
        Index(
            "ix_inventory_label_prints_unit_date",
            "company_id",
            "handling_unit_id",
            "print_date",
        ),
    )


__all__ = ["InventoryLabelPrintModel"]
