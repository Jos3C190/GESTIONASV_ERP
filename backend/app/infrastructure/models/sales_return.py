"""Customer returns linked to immutable physical sales allocations."""

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
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class SalesReturnModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_returns"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sale_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    received_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    cancelled_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_returns_company_id"),
        UniqueConstraint("company_id", "code", name="uq_sales_returns_company_code"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "sale_id"], ["sales.company_id", "sales.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by_id", "company_id"], ["user_companies.user_id", "user_companies.company_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["updated_by_id", "company_id"], ["user_companies.user_id", "user_companies.company_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["received_by_id", "company_id"], ["user_companies.user_id", "user_companies.company_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["cancelled_by_id", "company_id"], ["user_companies.user_id", "user_companies.company_id"], ondelete="RESTRICT"),
        CheckConstraint("status IN ('draft','received','under_review','accepted','rejected','mixed','cancelled')", name="ck_sales_returns_status"),
        CheckConstraint("(status IN ('draft','cancelled')) = (received_at IS NULL AND received_by_id IS NULL)", name="ck_sales_returns_received_state"),
        CheckConstraint("(status = 'cancelled') = (cancelled_at IS NOT NULL AND cancelled_by_id IS NOT NULL AND cancellation_reason IS NOT NULL)", name="ck_sales_returns_cancellation"),
        Index("ix_sales_returns_sale_status", "company_id", "sale_id", "status"),
    )


class SalesReturnLineModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_return_lines"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    return_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sale_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    delivery_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    delivery_line_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    delivery_allocation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_valuation_entry_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_handling_unit_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_warehouse_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_location_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_lot_detail_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_unit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    lot_code: Mapped[str | None] = mapped_column(String(120))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    quantity_received_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    declared_condition: Mapped[str] = mapped_column(String(24), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_return_lines_company_id"),
        UniqueConstraint("return_id", "line_number", name="uq_sales_return_lines_number"),
        ForeignKeyConstraint(["company_id", "return_id"], ["sales_returns.company_id", "sales_returns.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "sale_id"], ["sales.company_id", "sales.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "delivery_id"], ["sales_deliveries.company_id", "sales_deliveries.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "delivery_line_id"], ["sales_delivery_lines.company_id", "sales_delivery_lines.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "delivery_allocation_id"], ["sales_delivery_allocations.company_id", "sales_delivery_allocations.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "inventory_item_id"], ["inventory_items.company_id", "inventory_items.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "source_valuation_entry_id"], ["inventory_valuation_entries.company_id", "inventory_valuation_entries.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "inventory_item_id", "source_handling_unit_id"], ["inventory_handling_units.company_id", "inventory_handling_units.inventory_item_id", "inventory_handling_units.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "inventory_lot_detail_id"], ["inventory_lot_details.company_id", "inventory_lot_details.id"], ondelete="RESTRICT"),
        CheckConstraint("line_number > 0 AND quantity_received_base > 0", name="ck_sales_return_lines_quantity"),
        CheckConstraint("declared_condition IN ('resalable','damaged','wrong_item','other')", name="ck_sales_return_lines_condition"),
        Index("ix_sales_return_lines_source", "company_id", "delivery_allocation_id"),
    )


class SalesReturnEventModel(UUIDPKMixin, Base):
    """Append-only, partial decision for one received return line."""

    __tablename__ = "sales_return_events"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    return_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    return_line_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    condition: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    destination_location_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    movement_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    movement_line_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    valuation_entry_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    actor_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_return_events_company_id"),
        ForeignKeyConstraint(["company_id", "return_id"], ["sales_returns.company_id", "sales_returns.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "return_line_id"], ["sales_return_lines.company_id", "sales_return_lines.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "movement_id"], ["inventory_movements.company_id", "inventory_movements.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "movement_line_id"], ["inventory_movement_lines.company_id", "inventory_movement_lines.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id", "valuation_entry_id"], ["inventory_valuation_entries.company_id", "inventory_valuation_entries.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["destination_location_id"], ["locations.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["actor_id", "company_id"], ["user_companies.user_id", "user_companies.company_id"], ondelete="RESTRICT"),
        CheckConstraint("decision IN ('accepted','rejected')", name="ck_sales_return_event_decision"),
        CheckConstraint("quantity_base > 0", name="ck_sales_return_event_quantity"),
        CheckConstraint("condition IN ('resalable','damaged','wrong_item','other')", name="ck_sales_return_event_condition"),
        CheckConstraint("(decision = 'accepted') = (destination_location_id IS NOT NULL AND movement_id IS NOT NULL AND movement_line_id IS NOT NULL AND valuation_entry_id IS NOT NULL)", name="ck_sales_return_event_inventory_link"),
        Index("ix_sales_return_events_line", "company_id", "return_line_id"),
    )


class SalesReturnCommandModel(UUIDPKMixin, Base):
    __tablename__ = "sales_return_commands"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    return_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "action", "idempotency_key", name="uq_sales_return_command_key"),
        ForeignKeyConstraint(["company_id", "return_id"], ["sales_returns.company_id", "sales_returns.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["actor_id", "company_id"], ["user_companies.user_id", "user_companies.company_id"], ondelete="RESTRICT"),
        CheckConstraint("action IN ('create','receive','resolve','cancel')", name="ck_sales_return_command_action"),
    )


class SalesReturnDocumentModel(Base):
    """Links a return to an already-uploaded, company-owned evidence file."""

    __tablename__ = "sales_return_documents"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    return_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    attached_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    attached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(["company_id", "return_id"], ["sales_returns.company_id", "sales_returns.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["document_id", "company_id"], ["document_assets.id", "document_assets.company_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["attached_by_id", "company_id"], ["user_companies.user_id", "user_companies.company_id"], ondelete="RESTRICT"),
        Index("ix_sales_return_documents_return", "company_id", "return_id"),
    )


__all__ = ["SalesReturnCommandModel", "SalesReturnDocumentModel", "SalesReturnEventModel", "SalesReturnLineModel", "SalesReturnModel"]
