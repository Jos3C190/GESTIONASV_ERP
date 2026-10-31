"""Receipt-level internal inventory lots and accepted product quantities."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class InventoryLotModel(UUIDPKMixin, TimestampMixin, Base):
    """One immutable internal lot for one verified purchase receipt."""

    __tablename__ = "inventory_lots"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    label_confirmation_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_lots_company_id"),
        UniqueConstraint("company_id", "purchase_id", name="uq_inventory_lots_purchase"),
        UniqueConstraint("company_id", "code", name="uq_inventory_lots_code"),
        ForeignKeyConstraint(
            ["purchase_id", "company_id"],
            ["purchases.id", "purchases.company_id"],
            ondelete="RESTRICT",
            name="fk_inventory_lots_purchase_company",
        ),
        CheckConstraint("char_length(code) BETWEEN 3 AND 80", name="ck_inventory_lots_code"),
        Index("ix_inventory_lots_company_received", "company_id", "received_at"),
    )


class InventoryLotDetailModel(UUIDPKMixin, TimestampMixin, Base):
    """Accepted quantity for a purchase detail, expressed in both units."""

    __tablename__ = "inventory_lot_details"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_lot_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    purchase_detail_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    base_unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quantity_accepted: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    accepted_quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    entry_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    entry_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(entry_value IS NULL AND entry_currency IS NULL) OR (entry_value IS NOT NULL AND entry_value >= 0 AND entry_currency IS NOT NULL)",
            name="ck_lot_entry_value",
        ),
        UniqueConstraint("company_id", "id", name="uq_inventory_lot_details_company_id"),
        UniqueConstraint("company_id", "code", name="uq_inventory_lot_details_company_code"),
        CheckConstraint(
            "char_length(code) BETWEEN 3 AND 120", name="ck_inventory_lot_details_code"
        ),
        UniqueConstraint(
            "company_id",
            "inventory_lot_id",
            "purchase_detail_id",
            name="uq_inventory_lot_details_purchase_line",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_lot_id"],
            ["inventory_lots.company_id", "inventory_lots.id"],
            ondelete="RESTRICT",
            name="fk_inventory_lot_details_lot_company",
        ),
        ForeignKeyConstraint(
            ["purchase_detail_id", "company_id"],
            ["purchase_details.id", "purchase_details.company_id"],
            ondelete="RESTRICT",
            name="fk_inventory_lot_details_purchase_detail_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_inventory_lot_details_item_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            ondelete="RESTRICT",
            name="fk_inventory_lot_details_product_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "base_unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_inventory_lot_details_unit_company",
        ),
        CheckConstraint(
            "quantity_received > 0 AND quantity_accepted > 0 AND "
            "quantity_accepted <= quantity_received AND accepted_quantity_base > 0",
            name="ck_inventory_lot_details_quantities",
        ),
        Index(
            "ix_inventory_lot_details_item",
            "company_id",
            "inventory_lot_id",
            "inventory_item_id",
        ),
    )
