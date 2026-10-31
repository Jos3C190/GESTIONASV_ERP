"""Append-only valuation events and company/product balance projections."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPKMixin


class InventoryValuationSettingModel(Base):
    __tablename__ = "inventory_valuation_settings"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opened_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    opening_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    opening_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    physical_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)


class InventoryCostAverageModel(Base):
    __tablename__ = "inventory_cost_averages"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    inventory_value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    average_unit_cost: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id"], ["inventory_valuation_settings.company_id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "quantity_base >= 0 AND inventory_value >= 0 AND average_unit_cost >= 0",
            name="ck_cost_average_nonnegative",
        ),
        CheckConstraint(
            "quantity_base > 0 OR inventory_value = 0", name="ck_cost_average_zero_balance"
        ),
    )


class InventoryValuationEntryModel(UUIDPKMixin, Base):
    __tablename__ = "inventory_valuation_entries"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    source_value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    original_entry_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    movement_line_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    purchase_detail_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    retaceo_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    operational_date: Mapped[date] = mapped_column(Date, nullable=False)
    accounting_date: Mapped[date] = mapped_column(Date, nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    posted_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_delta: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    balance_quantity: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    balance_value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    average_unit_cost: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    cost_breakdown: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_valuation_entry_company_id"),
        UniqueConstraint("company_id", "sequence", name="uq_valuation_entry_sequence"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_valuation_entry_key"),
        UniqueConstraint("movement_line_id", name="uq_valuation_movement_line"),
        ForeignKeyConstraint(
            ["company_id"], ["inventory_valuation_settings.company_id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "original_entry_id"],
            ["inventory_valuation_entries.company_id", "inventory_valuation_entries.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "movement_line_id"],
            ["inventory_movement_lines.company_id", "inventory_movement_lines.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "purchase_detail_id"],
            ["purchase_details.company_id", "purchase_details.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "retaceo_id"],
            ["retaceos.company_id", "retaceos.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "kind IN ('opening','receipt','issue','supplier_return','customer_return','adjustment_in','adjustment_out','cost_adjustment','supplier_credit')",
            name="ck_valuation_entry_kind",
        ),
        CheckConstraint(
            "quantity_base >= 0 AND balance_quantity >= 0 AND balance_value >= 0",
            name="ck_valuation_entry_nonnegative",
        ),
        Index("ix_valuation_item_sequence", "company_id", "inventory_item_id", "sequence"),
    )


class InventoryRetaceoApplicationModel(UUIDPKMixin, Base):
    __tablename__ = "inventory_retaceo_applications"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    retaceo_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    applied_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "retaceo_id", name="uq_retaceo_application_retaceo"),
        UniqueConstraint("company_id", "purchase_id", name="uq_retaceo_application_purchase"),
        ForeignKeyConstraint(
            ["company_id", "retaceo_id"],
            ["retaceos.company_id", "retaceos.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "purchase_id"],
            ["purchases.company_id", "purchases.id"],
            ondelete="RESTRICT",
        ),
    )
