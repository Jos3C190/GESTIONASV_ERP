"""Physical sales deliveries linked to inventory movements and valuation."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class SalesDeliveryModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_deliveries"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sale_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_deliveries_company_id"),
        UniqueConstraint("company_id", "code", name="uq_sales_deliveries_company_code"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_deliveries_branch_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "sale_id"],
            ["sales.company_id", "sales.id"],
            ondelete="RESTRICT",
            name="fk_sales_deliveries_sale_company",
        ),
        ForeignKeyConstraint(
            ["created_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_deliveries_creator_company",
        ),
        ForeignKeyConstraint(
            ["confirmed_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_deliveries_confirmer_company",
        ),
        ForeignKeyConstraint(
            ["cancelled_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_deliveries_canceller_company",
        ),
        CheckConstraint(
            "status IN ('draft','confirmed','cancelled')", name="ck_sales_deliveries_status"
        ),
        CheckConstraint("version >= 1", name="ck_sales_deliveries_version"),
        CheckConstraint(
            "(status = 'confirmed') = (confirmed_at IS NOT NULL AND confirmed_by_id IS NOT NULL)",
            name="ck_sales_deliveries_confirmation",
        ),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL AND cancelled_by_id IS NOT NULL AND cancellation_reason IS NOT NULL)",
            name="ck_sales_deliveries_cancellation",
        ),
        Index("ix_sales_deliveries_sale_status", "company_id", "sale_id", "status"),
    )


class SalesDeliveryLineModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_delivery_lines"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    delivery_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sale_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sale_line_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_unit_name: Mapped[str] = mapped_column(String(120), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_delivery_lines_company_id"),
        UniqueConstraint(
            "company_id", "delivery_id", "sale_line_id", name="uq_sales_delivery_lines_source"
        ),
        UniqueConstraint("delivery_id", "line_number", name="uq_sales_delivery_lines_number"),
        ForeignKeyConstraint(
            ["company_id", "delivery_id"],
            ["sales_deliveries.company_id", "sales_deliveries.id"],
            ondelete="RESTRICT",
            name="fk_sales_delivery_lines_header_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "sale_id", "sale_line_id"],
            ["sales_lines.company_id", "sales_lines.sale_id", "sales_lines.id"],
            ondelete="RESTRICT",
            name="fk_sales_delivery_lines_sale_line",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_sales_delivery_lines_item_company",
        ),
        CheckConstraint(
            "line_number > 0 AND quantity_base > 0 AND unit_factor > 0",
            name="ck_sales_delivery_lines_quantity",
        ),
        Index("ix_sales_delivery_lines_sale", "company_id", "sale_id", "sale_line_id"),
    )


class SalesDeliveryAllocationModel(UUIDPKMixin, Base):
    __tablename__ = "sales_delivery_allocations"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    delivery_line_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    handling_unit_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_lot_detail_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    lot_code: Mapped[str | None] = mapped_column(String(120))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    packaging_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    movement_line_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    valuation_entry_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    applied_total_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    applied_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_delivery_allocations_company_id"),
        UniqueConstraint(
            "company_id",
            "delivery_line_id",
            "handling_unit_id",
            name="uq_sales_delivery_allocation_unit",
        ),
        UniqueConstraint("movement_line_id", name="uq_sales_delivery_allocation_movement_line"),
        ForeignKeyConstraint(
            ["company_id", "delivery_line_id"],
            ["sales_delivery_lines.company_id", "sales_delivery_lines.id"],
            ondelete="RESTRICT",
            name="fk_sales_delivery_allocation_line",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "handling_unit_id"],
            [
                "inventory_handling_units.company_id",
                "inventory_handling_units.inventory_item_id",
                "inventory_handling_units.id",
            ],
            ondelete="RESTRICT",
            name="fk_sales_delivery_allocation_unit",
        ),
        ForeignKeyConstraint(
            ["location_id", "warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            ondelete="RESTRICT",
            name="fk_sales_delivery_allocation_location",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_lot_detail_id"],
            ["inventory_lot_details.company_id", "inventory_lot_details.id"],
            ondelete="RESTRICT",
            name="fk_sales_delivery_allocation_lot",
        ),
        ForeignKeyConstraint(
            ["company_id", "movement_line_id"],
            ["inventory_movement_lines.company_id", "inventory_movement_lines.id"],
            ondelete="RESTRICT",
            name="fk_sales_delivery_allocation_movement_line",
        ),
        ForeignKeyConstraint(
            ["company_id", "valuation_entry_id"],
            ["inventory_valuation_entries.company_id", "inventory_valuation_entries.id"],
            ondelete="RESTRICT",
            name="fk_sales_delivery_allocation_valuation_entry",
        ),
        CheckConstraint("quantity_base > 0", name="ck_sales_delivery_allocation_quantity"),
        CheckConstraint(
            "(movement_line_id IS NULL AND valuation_entry_id IS NULL AND applied_total_cost IS NULL AND applied_unit_cost IS NULL) "
            "OR (movement_line_id IS NOT NULL AND valuation_entry_id IS NOT NULL AND applied_total_cost IS NOT NULL AND applied_unit_cost IS NOT NULL)",
            name="ck_sales_delivery_allocation_posted_cost",
        ),
        CheckConstraint(
            "applied_total_cost IS NULL OR applied_total_cost >= 0",
            name="ck_sales_delivery_allocation_cost_nonnegative",
        ),
        Index("ix_sales_delivery_allocation_unit", "company_id", "handling_unit_id"),
    )


class SalesDeliveryCommandModel(UUIDPKMixin, Base):
    __tablename__ = "sales_delivery_commands"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    delivery_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "action", "idempotency_key", name="uq_sales_delivery_command_key"
        ),
        ForeignKeyConstraint(
            ["company_id", "delivery_id"],
            ["sales_deliveries.company_id", "sales_deliveries.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["actor_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("action IN ('create','confirm')", name="ck_sales_delivery_command_action"),
    )


__all__ = [
    "SalesDeliveryAllocationModel",
    "SalesDeliveryCommandModel",
    "SalesDeliveryLineModel",
    "SalesDeliveryModel",
]
