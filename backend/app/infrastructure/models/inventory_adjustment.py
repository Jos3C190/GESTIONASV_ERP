"""Authorized inventory adjustment documents and their immutable evidence."""

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
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class InventoryAdjustmentModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_adjustments"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    operational_date: Mapped[date] = mapped_column(Date, nullable=False)
    accounting_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    document_reference: Mapped[str] = mapped_column(String(240), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    approved_version: Mapped[int | None] = mapped_column(Integer)
    correction_of_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    transfer_incident_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    applied_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    cancelled_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    approval_revocation_reason: Mapped[str | None] = mapped_column(Text)
    apply_idempotency_key: Mapped[str | None] = mapped_column(String(120))
    apply_fingerprint: Mapped[str | None] = mapped_column(String(64))
    applied_movements: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    create_idempotency_key: Mapped[str | None] = mapped_column(String(120))
    create_fingerprint: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_adjustments_company_id"),
        UniqueConstraint("company_id", "code", name="uq_inventory_adjustments_company_code"),
        UniqueConstraint(
            "company_id", "apply_idempotency_key", name="uq_inventory_adjustments_apply_key"
        ),
        Index(
            "uq_inventory_adjustments_create_key",
            "company_id",
            "create_idempotency_key",
            unique=True,
            postgresql_where=text("create_idempotency_key IS NOT NULL"),
        ),
        ForeignKeyConstraint(
            ["company_id", "warehouse_id"],
            ["warehouses.company_id", "warehouses.id"],
            name="fk_inventory_adjustments_warehouse_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "correction_of_id"],
            ["inventory_adjustments.company_id", "inventory_adjustments.id"],
            name="fk_inventory_adjustments_correction_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "transfer_id"],
            ["inventory_transfers.company_id", "inventory_transfers.id"],
            name="fk_inventory_adjustments_transfer_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "transfer_id", "transfer_incident_id"],
            [
                "inventory_transfer_incidents.company_id",
                "inventory_transfer_incidents.transfer_id",
                "inventory_transfer_incidents.id",
            ],
            name="fk_inventory_adjustments_incident_transfer_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            name="fk_inventory_adjustments_approver_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["applied_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            name="fk_inventory_adjustments_applier_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["cancelled_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            name="fk_inventory_adjustments_canceller_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint("status IN ('draft','approved','applied','cancelled')", name="ck_inventory_adjustments_status"),
        CheckConstraint("version >= 1", name="ck_inventory_adjustments_version"),
        CheckConstraint(
            "(status = 'draft' AND approved_at IS NULL AND applied_at IS NULL) OR "
            "(status = 'approved' AND approved_at IS NOT NULL AND applied_at IS NULL "
            "AND approved_version = version) OR "
            "(status = 'applied' AND approved_at IS NOT NULL AND applied_at IS NOT NULL "
            "AND approved_version = version) OR "
            "(status = 'cancelled' AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL)",
            name="ck_inventory_adjustments_lifecycle",
        ),
        CheckConstraint(
            "(transfer_id IS NULL AND transfer_incident_id IS NULL) OR "
            "(transfer_id IS NOT NULL AND transfer_incident_id IS NOT NULL)",
            name="ck_inventory_adjustments_transfer_context",
        ),
        Index("ix_inventory_adjustments_company_status", "company_id", "status", "created_at"),
        Index(
            "uq_inventory_adjustments_active_correction",
            "company_id",
            "correction_of_id",
            unique=True,
            postgresql_where=text("correction_of_id IS NOT NULL AND status <> 'cancelled'"),
        ),
    )


class InventoryAdjustmentDetailModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_adjustment_details"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    adjustment_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    stock_status: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(12), nullable=False)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    inventory_lot_detail_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    handling_unit_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    packaging_definition_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    documented_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    documented_total_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    actual_gross_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    actual_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    transfer_detail_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    movement_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    movement_line_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "adjustment_id"],
            ["inventory_adjustments.company_id", "inventory_adjustments.id"],
            name="fk_inventory_adjustment_details_header_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["company_id", "warehouse_id"],
            ["warehouses.company_id", "warehouses.id"],
            name="fk_inventory_adjustment_details_warehouse_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            name="fk_inventory_adjustment_details_item_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["location_id", "warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            name="fk_inventory_adjustment_details_location_warehouse",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_lot_detail_id"],
            ["inventory_lot_details.company_id", "inventory_lot_details.id"],
            name="fk_inventory_adjustment_details_lot_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "handling_unit_id"],
            [
                "inventory_handling_units.company_id",
                "inventory_handling_units.inventory_item_id",
                "inventory_handling_units.id",
            ],
            name="fk_inventory_adjustment_details_handling_unit",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "packaging_definition_id"],
            [
                "inventory_packaging_definitions.company_id",
                "inventory_packaging_definitions.inventory_item_id",
                "inventory_packaging_definitions.id",
            ],
            name="fk_inventory_adjustment_details_packaging",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "transfer_detail_id"],
            ["inventory_transfer_details.company_id", "inventory_transfer_details.id"],
            name="fk_inventory_adjustment_details_transfer_detail",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "movement_id"],
            ["inventory_movements.company_id", "inventory_movements.id"],
            name="fk_inventory_adjustment_details_movement",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "movement_line_id"],
            ["inventory_movement_lines.company_id", "inventory_movement_lines.id"],
            name="fk_inventory_adjustment_details_movement_line",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("adjustment_id", "line_number", name="uq_inventory_adjustment_line_number"),
        UniqueConstraint("company_id", "id", name="uq_inventory_adjustment_details_company_id"),
        CheckConstraint("line_number > 0 AND quantity_base > 0", name="ck_inventory_adjustment_details_positive"),
        CheckConstraint("direction IN ('increase','decrease')", name="ck_inventory_adjustment_details_direction"),
        CheckConstraint(
            "stock_status IN ('available','quarantine','damaged','in_transit')",
            name="ck_inventory_adjustment_details_stock_status",
        ),
        CheckConstraint(
            "(direction = 'increase' AND stock_status = 'quarantine' AND handling_unit_id IS NULL "
            "AND transfer_detail_id IS NULL AND (documented_unit_cost IS NULL OR documented_unit_cost >= 0) "
            "AND (documented_total_cost IS NULL OR documented_total_cost >= 0) "
            "AND (actual_gross_weight_kg IS NULL OR actual_gross_weight_kg > 0) "
            "AND (actual_volume_m3 IS NULL OR actual_volume_m3 > 0)) OR "
            "(direction = 'decrease' AND handling_unit_id IS NOT NULL AND documented_unit_cost IS NULL "
            "AND documented_total_cost IS NULL AND actual_gross_weight_kg IS NULL "
            "AND actual_volume_m3 IS NULL AND "
            "((stock_status = 'in_transit' AND transfer_detail_id IS NOT NULL) OR "
            "(stock_status <> 'in_transit' AND transfer_detail_id IS NULL)))",
            name="ck_inventory_adjustment_details_direction_fields",
        ),
        Index("ix_inventory_adjustment_details_header", "company_id", "adjustment_id", "line_number"),
    )


class InventoryAdjustmentDocumentModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_adjustment_documents"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    adjustment_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    linked_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    upload_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detached_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    detached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "adjustment_id"],
            ["inventory_adjustments.company_id", "inventory_adjustments.id"],
            name="fk_inventory_adjustment_documents_adjustment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_id", "company_id"],
            ["document_assets.id", "document_assets.company_id"],
            name="fk_inventory_adjustment_documents_asset_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["linked_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            name="fk_inventory_adjustment_documents_linker_company",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("company_id", "adjustment_id", "document_id", name="uq_inventory_adjustment_document"),
        CheckConstraint(
            "detached_at IS NULL OR detached_by_id IS NOT NULL",
            name="ck_inventory_adjustment_documents_detached_actor",
        ),
        Index("ix_inventory_adjustment_documents_active", "company_id", "adjustment_id", "detached_at"),
    )


class InventoryAdjustmentEventModel(UUIDPKMixin, Base):
    __tablename__ = "inventory_adjustment_events"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    adjustment_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "adjustment_id"],
            ["inventory_adjustments.company_id", "inventory_adjustments.id"],
            name="fk_inventory_adjustment_events_adjustment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["actor_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            name="fk_inventory_adjustment_events_actor_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint("version >= 1", name="ck_inventory_adjustment_events_version"),
        Index("ix_inventory_adjustment_events_adjustment", "company_id", "adjustment_id", "occurred_at"),
    )
