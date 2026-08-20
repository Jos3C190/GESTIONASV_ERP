"""SQLAlchemy persistence models for the inventory bounded context."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
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


class InventoryItemModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_items"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    base_unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_items_company_id"),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            ondelete="RESTRICT",
            name="fk_inventory_items_product_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "variant_id"],
            ["product_variants.company_id", "product_variants.id"],
            ondelete="RESTRICT",
            name="fk_inventory_items_variant_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "base_unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_inventory_items_base_unit_company",
        ),
        CheckConstraint(
            "(product_id IS NOT NULL) <> (variant_id IS NOT NULL)",
            name="ck_inventory_items_exact_target",
        ),
        Index(
            "uq_inventory_items_product",
            "company_id",
            "product_id",
            unique=True,
            postgresql_where=text("product_id IS NOT NULL"),
        ),
        Index(
            "uq_inventory_items_variant",
            "company_id",
            "variant_id",
            unique=True,
            postgresql_where=text("variant_id IS NOT NULL"),
        ),
        Index("ix_inventory_items_company_active", "company_id", "is_active"),
    )


class InventoryPackagingModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_packaging_definitions"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    packaging_type: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    base_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gross_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    length_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    width_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    height_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    stackable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    max_stack: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_packaging_company_id"),
        UniqueConstraint(
            "company_id",
            "inventory_item_id",
            "id",
            name="uq_inventory_packaging_item_identity",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="CASCADE",
            name="fk_inventory_packaging_item_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "supersedes_id"],
            [
                "inventory_packaging_definitions.company_id",
                "inventory_packaging_definitions.inventory_item_id",
                "inventory_packaging_definitions.id",
            ],
            ondelete="RESTRICT",
            name="fk_inventory_packaging_supersedes_item",
        ),
        UniqueConstraint(
            "company_id",
            "inventory_item_id",
            "code",
            "version",
            name="uq_inventory_packaging_code_version",
        ),
        Index(
            "uq_inventory_packaging_current_code",
            "company_id",
            "inventory_item_id",
            "code",
            unique=True,
            postgresql_where=text("is_current AND is_active"),
        ),
        CheckConstraint(
            "packaging_type IN ('piece','box','bag','package','roll','drum','container','loose_other')",
            name="ck_inventory_packaging_type",
        ),
        CheckConstraint("base_quantity > 0", name="ck_inventory_packaging_quantity_positive"),
        CheckConstraint(
            "gross_weight_kg IS NULL OR gross_weight_kg > 0",
            name="ck_inventory_packaging_weight_positive",
        ),
        CheckConstraint(
            "length_m IS NULL OR length_m > 0", name="ck_inventory_packaging_length_positive"
        ),
        CheckConstraint(
            "width_m IS NULL OR width_m > 0", name="ck_inventory_packaging_width_positive"
        ),
        CheckConstraint(
            "height_m IS NULL OR height_m > 0", name="ck_inventory_packaging_height_positive"
        ),
        CheckConstraint(
            "volume_m3 IS NULL OR volume_m3 > 0", name="ck_inventory_packaging_volume_positive"
        ),
        CheckConstraint(
            "(length_m IS NULL AND width_m IS NULL AND height_m IS NULL) "
            "OR (length_m IS NOT NULL AND width_m IS NOT NULL AND height_m IS NOT NULL)",
            name="ck_inventory_packaging_dimensions_complete",
        ),
        CheckConstraint(
            "(stackable AND (max_stack IS NULL OR max_stack >= 1)) OR "
            "(NOT stackable AND max_stack IS NULL)",
            name="ck_inventory_packaging_stack",
        ),
        CheckConstraint("version >= 1", name="ck_inventory_packaging_version_positive"),
    )


class InventoryHandlingUnitModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_handling_units"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    packaging_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    lot_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    packaging_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    actual_gross_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    actual_length_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    actual_width_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    actual_height_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    actual_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    occupied_weight_kg: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    occupied_volume_m3: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    stock_status: Mapped[str] = mapped_column(String(20), nullable=False)
    measurement_status: Mapped[str] = mapped_column(String(20), nullable=False)
    measurement_source: Mapped[str] = mapped_column(String(20), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_handling_units_company_id"),
        UniqueConstraint(
            "company_id",
            "inventory_item_id",
            "id",
            name="uq_inventory_handling_units_item_identity",
        ),
        ForeignKeyConstraint(
            ["location_id", "warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            ondelete="RESTRICT",
            name="fk_inventory_handling_units_location_warehouse",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_inventory_handling_units_item_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "packaging_definition_id"],
            [
                "inventory_packaging_definitions.company_id",
                "inventory_packaging_definitions.inventory_item_id",
                "inventory_packaging_definitions.id",
            ],
            ondelete="RESTRICT",
            name="fk_inventory_handling_units_packaging_item",
        ),
        Index(
            "uq_inventory_handling_units_code",
            "company_id",
            text("lower(code)"),
            unique=True,
        ),
        CheckConstraint("quantity_base > 0", name="ck_inventory_handling_units_quantity_positive"),
        CheckConstraint(
            "occupied_weight_kg >= 0", name="ck_inventory_handling_units_weight_nonnegative"
        ),
        CheckConstraint(
            "occupied_volume_m3 >= 0", name="ck_inventory_handling_units_volume_nonnegative"
        ),
        CheckConstraint(
            "actual_gross_weight_kg IS NULL OR actual_gross_weight_kg > 0",
            name="ck_inventory_handling_units_actual_weight_positive",
        ),
        CheckConstraint(
            "actual_length_m IS NULL OR actual_length_m > 0",
            name="ck_inventory_handling_units_actual_length_positive",
        ),
        CheckConstraint(
            "actual_width_m IS NULL OR actual_width_m > 0",
            name="ck_inventory_handling_units_actual_width_positive",
        ),
        CheckConstraint(
            "actual_height_m IS NULL OR actual_height_m > 0",
            name="ck_inventory_handling_units_actual_height_positive",
        ),
        CheckConstraint(
            "actual_volume_m3 IS NULL OR actual_volume_m3 > 0",
            name="ck_inventory_handling_units_actual_volume_positive",
        ),
        CheckConstraint(
            "(actual_length_m IS NULL AND actual_width_m IS NULL AND actual_height_m IS NULL) "
            "OR (actual_length_m IS NOT NULL AND actual_width_m IS NOT NULL "
            "AND actual_height_m IS NOT NULL)",
            name="ck_inventory_handling_units_dimensions_complete",
        ),
        CheckConstraint(
            "stock_status IN ('available','quarantine','blocked','damaged','in_transit')",
            name="ck_inventory_handling_units_stock_status",
        ),
        CheckConstraint(
            "measurement_status IN ('complete','incomplete','verified')",
            name="ck_inventory_handling_units_measurement_status",
        ),
        CheckConstraint(
            "measurement_source IN ('master','receipt','manual','device')",
            name="ck_inventory_handling_units_measurement_source",
        ),
        CheckConstraint(
            "measurement_status <> 'incomplete' OR "
            "(stock_status = 'quarantine' AND occupied_weight_kg = 0 "
            "AND occupied_volume_m3 = 0)",
            name="ck_inventory_handling_units_incomplete_quarantine",
        ),
        CheckConstraint(
            "measurement_status = 'incomplete' OR "
            "(occupied_weight_kg > 0 AND occupied_volume_m3 > 0)",
            name="ck_inventory_handling_units_measured_values",
        ),
        CheckConstraint(
            "measurement_status = 'incomplete' OR measurement_source = 'master' OR "
            "(actual_gross_weight_kg IS NOT NULL AND actual_volume_m3 IS NOT NULL)",
            name="ck_inventory_handling_units_actual_measure_evidence",
        ),
        Index("ix_inventory_handling_units_location_status", "location_id", "stock_status"),
    )


class InventoryMovementModel(UUIDPKMixin, Base):
    __tablename__ = "inventory_movements"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    movement_type: Mapped[str] = mapped_column(String(24), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    posted_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_movements_company_id"),
        UniqueConstraint(
            "company_id", "idempotency_key", name="uq_inventory_movements_idempotency"
        ),
        ForeignKeyConstraint(
            ["company_id", "reversal_of_id"],
            ["inventory_movements.company_id", "inventory_movements.id"],
            ondelete="RESTRICT",
            name="fk_inventory_movements_reversal_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "reservation_id"],
            ["inventory_capacity_reservations.company_id", "inventory_capacity_reservations.id"],
            ondelete="RESTRICT",
            name="fk_inventory_movements_reservation_company",
        ),
        CheckConstraint(
            "movement_type IN ('receipt','putaway','transfer','pick','shipment',"
            "'adjustment_in','adjustment_out','reversal')",
            name="ck_inventory_movements_type",
        ),
        Index("ix_inventory_movements_company_posted", "company_id", "posted_at"),
    )


class InventoryMovementLineModel(UUIDPKMixin, Base):
    __tablename__ = "inventory_movement_lines"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    movement_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    handling_unit_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    operational_override_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    lot_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    from_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    from_location_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    to_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    to_location_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    from_stock_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_stock_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    occupied_weight_kg: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    occupied_volume_m3: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    measurement_status: Mapped[str] = mapped_column(String(20), nullable=False)
    packaging_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "movement_id"],
            ["inventory_movements.company_id", "inventory_movements.id"],
            ondelete="RESTRICT",
            name="fk_inventory_movement_lines_header_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_inventory_movement_lines_item_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "handling_unit_id"],
            [
                "inventory_handling_units.company_id",
                "inventory_handling_units.inventory_item_id",
                "inventory_handling_units.id",
            ],
            ondelete="RESTRICT",
            name="fk_inventory_movement_lines_handling_unit_item",
        ),
        ForeignKeyConstraint(
            ["company_id", "to_location_id", "operational_override_id"],
            [
                "inventory_capacity_operational_overrides.company_id",
                "inventory_capacity_operational_overrides.location_id",
                "inventory_capacity_operational_overrides.id",
            ],
            ondelete="RESTRICT",
            name="fk_inventory_movement_lines_override_location",
        ),
        ForeignKeyConstraint(
            ["from_location_id", "from_warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            ondelete="RESTRICT",
            name="fk_inventory_movement_lines_from_location",
        ),
        ForeignKeyConstraint(
            ["to_location_id", "to_warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            ondelete="RESTRICT",
            name="fk_inventory_movement_lines_to_location",
        ),
        UniqueConstraint("movement_id", "line_number", name="uq_inventory_movement_lines_number"),
        CheckConstraint("line_number >= 1", name="ck_inventory_movement_lines_number_positive"),
        CheckConstraint("quantity_base > 0", name="ck_inventory_movement_lines_quantity_positive"),
        CheckConstraint(
            "occupied_weight_kg >= 0", name="ck_inventory_movement_lines_weight_nonnegative"
        ),
        CheckConstraint(
            "occupied_volume_m3 >= 0", name="ck_inventory_movement_lines_volume_nonnegative"
        ),
        CheckConstraint(
            "measurement_status IN ('complete','incomplete','verified')",
            name="ck_inventory_movement_lines_measurement_status",
        ),
        CheckConstraint(
            "measurement_status <> 'incomplete' OR "
            "(occupied_weight_kg = 0 AND occupied_volume_m3 = 0)",
            name="ck_inventory_movement_lines_incomplete_values",
        ),
        CheckConstraint(
            "measurement_status = 'incomplete' OR "
            "(occupied_weight_kg > 0 AND occupied_volume_m3 > 0)",
            name="ck_inventory_movement_lines_measured_values",
        ),
        CheckConstraint(
            "(from_location_id IS NULL) = (from_warehouse_id IS NULL)",
            name="ck_inventory_movement_lines_from_complete",
        ),
        CheckConstraint(
            "(to_location_id IS NULL) = (to_warehouse_id IS NULL)",
            name="ck_inventory_movement_lines_to_complete",
        ),
        CheckConstraint(
            "from_location_id IS NOT NULL OR to_location_id IS NOT NULL",
            name="ck_inventory_movement_lines_endpoint_required",
        ),
        CheckConstraint(
            "operational_override_id IS NULL OR to_location_id IS NOT NULL",
            name="ck_inventory_movement_lines_override_destination",
        ),
        CheckConstraint(
            "(from_location_id IS NULL) = (from_stock_status IS NULL)",
            name="ck_inventory_movement_lines_from_status_complete",
        ),
        CheckConstraint(
            "(to_location_id IS NULL) = (to_stock_status IS NULL)",
            name="ck_inventory_movement_lines_to_status_complete",
        ),
        CheckConstraint(
            "from_stock_status IS NULL OR from_stock_status IN "
            "('available','quarantine','blocked','damaged','in_transit')",
            name="ck_inventory_movement_lines_from_status",
        ),
        CheckConstraint(
            "to_stock_status IS NULL OR to_stock_status IN "
            "('available','quarantine','blocked','damaged','in_transit')",
            name="ck_inventory_movement_lines_to_status",
        ),
    )


class InventoryBalanceModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_balances"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    stock_status: Mapped[str] = mapped_column(String(20), nullable=False)
    lot_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    occupied_weight_kg: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    occupied_volume_m3: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["location_id", "warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            ondelete="RESTRICT",
            name="fk_inventory_balances_location_warehouse",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_inventory_balances_item_company",
        ),
        Index(
            "uq_inventory_balances_projection",
            "company_id",
            "location_id",
            "inventory_item_id",
            "stock_status",
            text("coalesce(lot_code, '')"),
            text("coalesce(expiry_date, DATE '0001-01-01')"),
            unique=True,
        ),
        CheckConstraint("quantity_base >= 0", name="ck_inventory_balances_quantity_nonnegative"),
        CheckConstraint("occupied_weight_kg >= 0", name="ck_inventory_balances_weight_nonnegative"),
        CheckConstraint("occupied_volume_m3 >= 0", name="ck_inventory_balances_volume_nonnegative"),
        CheckConstraint(
            "stock_status IN ('available','quarantine','blocked','damaged','in_transit')",
            name="ck_inventory_balances_stock_status",
        ),
        Index("ix_inventory_balances_location", "company_id", "warehouse_id", "location_id"),
    )


class CapacityReservationModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_capacity_reservations"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    packaging_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reserved_weight_kg: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reserved_volume_m3: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    measurement_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="complete"
    )
    stock_status: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    operational_override_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_capacity_reservations_company_id"),
        ForeignKeyConstraint(
            ["location_id", "warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            ondelete="RESTRICT",
            name="fk_inventory_capacity_reservations_location_warehouse",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_inventory_capacity_reservations_item_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "packaging_definition_id"],
            [
                "inventory_packaging_definitions.company_id",
                "inventory_packaging_definitions.inventory_item_id",
                "inventory_packaging_definitions.id",
            ],
            ondelete="RESTRICT",
            name="fk_inventory_capacity_reservations_packaging_item",
        ),
        ForeignKeyConstraint(
            ["company_id", "location_id", "operational_override_id"],
            [
                "inventory_capacity_operational_overrides.company_id",
                "inventory_capacity_operational_overrides.location_id",
                "inventory_capacity_operational_overrides.id",
            ],
            ondelete="RESTRICT",
            name="fk_inventory_capacity_reservations_override_location",
        ),
        CheckConstraint(
            "quantity_base > 0", name="ck_inventory_capacity_reservations_quantity_positive"
        ),
        CheckConstraint(
            "reserved_weight_kg >= 0", name="ck_inventory_capacity_reservations_weight_nonnegative"
        ),
        CheckConstraint(
            "reserved_volume_m3 >= 0", name="ck_inventory_capacity_reservations_volume_nonnegative"
        ),
        CheckConstraint(
            "status IN ('active','confirmed','consumed','cancelled','expired')",
            name="ck_inventory_capacity_reservations_status",
        ),
        CheckConstraint(
            "stock_status IN ('available','quarantine','blocked','damaged','in_transit')",
            name="ck_inventory_capacity_reservations_stock_status",
        ),
        CheckConstraint(
            "measurement_status IN ('complete','incomplete','verified')",
            name="ck_inventory_capacity_reservations_measurement_status",
        ),
        CheckConstraint(
            "measurement_status <> 'incomplete' OR "
            "(stock_status = 'quarantine' AND reserved_weight_kg = 0 "
            "AND reserved_volume_m3 = 0)",
            name="ck_inventory_capacity_reservations_incomplete_quarantine",
        ),
        CheckConstraint(
            "measurement_status = 'incomplete' OR "
            "(reserved_weight_kg > 0 AND reserved_volume_m3 > 0)",
            name="ck_inventory_capacity_reservations_measured_values",
        ),
        Index(
            "ix_inventory_capacity_reservations_location_status",
            "location_id",
            "status",
            "expires_at",
        ),
    )


class CapacityOperationalOverrideModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_capacity_operational_overrides"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_capacity_overrides_company_id"),
        UniqueConstraint(
            "company_id",
            "location_id",
            "id",
            name="uq_inventory_capacity_overrides_location_identity",
        ),
        ForeignKeyConstraint(
            ["location_id", "warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            ondelete="RESTRICT",
            name="fk_inventory_capacity_overrides_location_warehouse",
        ),
        CheckConstraint(
            "status IN ('active','revoked','expired')",
            name="ck_inventory_capacity_overrides_status",
        ),
        CheckConstraint(
            "length(btrim(reason)) >= 10",
            name="ck_inventory_capacity_overrides_reason",
        ),
        Index(
            "uq_inventory_capacity_overrides_active_location",
            "company_id",
            "location_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "ix_inventory_capacity_overrides_location_status",
            "location_id",
            "status",
            "valid_until",
        ),
    )


__all__ = [
    "CapacityOperationalOverrideModel",
    "CapacityReservationModel",
    "InventoryBalanceModel",
    "InventoryHandlingUnitModel",
    "InventoryItemModel",
    "InventoryMovementLineModel",
    "InventoryMovementModel",
    "InventoryPackagingModel",
]
