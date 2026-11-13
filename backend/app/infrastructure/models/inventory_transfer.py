"""Company-scoped transfer documents, vehicle locations and audit events."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

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
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class InventoryVehicleModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_vehicles"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    transit_warehouse_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    transit_location_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_vehicles_company_id"),
        UniqueConstraint("company_id", "code", name="uq_inventory_vehicles_company_code"),
        UniqueConstraint(
            "company_id", "transit_location_id", name="uq_inventory_vehicles_transit_location"
        ),
        ForeignKeyConstraint(
            ["company_id", "transit_warehouse_id"],
            ["warehouses.company_id", "warehouses.id"],
            name="fk_inventory_vehicles_transit_warehouse_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["transit_location_id", "transit_warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            name="fk_inventory_vehicles_transit_location_warehouse",
            ondelete="RESTRICT",
        ),
        CheckConstraint("status IN ('active','inactive')", name="ck_inventory_vehicles_status"),
        Index("ix_inventory_vehicles_company_status", "company_id", "status"),
    )


class InventoryTransferSettingsModel(TimestampMixin, Base):
    """A company's transfer rules; branch routes start turned off and approval on."""

    __tablename__ = "inventory_transfer_settings"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    allow_branch_to_branch: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    allow_branch_to_central: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    require_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class InventoryTransferModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_transfers"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    origin_warehouse_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    destination_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="preparation")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    dispatched_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    received_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatch_command_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    dispatch_movement_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    driver_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    compliance_override_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    compliance_override_reason: Mapped[str | None] = mapped_column(Text)
    route_type: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="central_distribution"
    )
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    approval_round: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    last_edited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    approved_vehicle_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    approved_driver_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    assignment_substitution_code: Mapped[str | None] = mapped_column(String(24))
    assignment_substitution_reason: Mapped[str | None] = mapped_column(Text)
    assignment_substitution_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    assignment_substitution_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_transfers_company_id"),
        ForeignKeyConstraint(
            ["company_id", "approved_vehicle_id"],
            ["inventory_vehicles.company_id", "inventory_vehicles.id"],
            name="fk_inventory_transfers_approved_vehicle_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "approved_driver_id"],
            ["drivers.company_id", "drivers.id"],
            name="fk_inventory_transfers_approved_driver_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(assignment_substitution_code IS NULL AND assignment_substitution_reason IS NULL "
            "AND assignment_substitution_by_id IS NULL AND assignment_substitution_at IS NULL) "
            "OR (assignment_substitution_code IN ('vehicle_unfit','vehicle_unavailable',"
            "'driver_unfit','driver_unavailable','load_change','other') "
            "AND assignment_substitution_reason IS NOT NULL "
            "AND char_length(btrim(assignment_substitution_reason)) >= 10 "
            "AND assignment_substitution_by_id IS NOT NULL "
            "AND assignment_substitution_at IS NOT NULL)",
            name="ck_inventory_transfers_assignment_substitution",
        ),
        ForeignKeyConstraint(
            ["company_id", "driver_id"],
            ["drivers.company_id", "drivers.id"],
            name="fk_inventory_transfers_driver_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(compliance_override_by IS NULL) = (compliance_override_reason IS NULL)",
            name="ck_inventory_transfers_compliance_override",
        ),
        UniqueConstraint("company_id", "code", name="uq_inventory_transfers_company_code"),
        UniqueConstraint(
            "company_id", "dispatch_command_id", name="uq_inventory_transfers_dispatch_command"
        ),
        UniqueConstraint(
            "company_id", "dispatch_movement_id", name="uq_inventory_transfers_dispatch_movement"
        ),
        ForeignKeyConstraint(
            ["company_id", "origin_warehouse_id"],
            ["warehouses.company_id", "warehouses.id"],
            name="fk_inventory_transfers_origin_warehouse_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "destination_warehouse_id"],
            ["warehouses.company_id", "warehouses.id"],
            name="fk_inventory_transfers_destination_warehouse_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "vehicle_id"],
            ["inventory_vehicles.company_id", "inventory_vehicles.id"],
            name="fk_inventory_transfers_vehicle_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "dispatch_movement_id"],
            ["inventory_movements.company_id", "inventory_movements.id"],
            name="fk_inventory_transfers_dispatch_movement",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "dispatch_command_id"],
            ["inventory_transfer_commands.company_id", "inventory_transfer_commands.id"],
            name="fk_inventory_transfers_dispatch_command",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('preparation','pending_approval','approved','in_transit',"
            "'partially_received','discrepancy','received','closed_with_adjustment',"
            "'incident','cancelled')",
            name="ck_inventory_transfers_status",
        ),
        CheckConstraint(
            "origin_warehouse_id <> destination_warehouse_id",
            name="ck_inventory_transfers_distinct_warehouses",
        ),
        CheckConstraint(
            "route_type IN ('central_distribution','branch_to_branch','branch_to_central')",
            name="ck_inventory_transfers_route_type",
        ),
        CheckConstraint("approval_round >= 0", name="ck_inventory_transfers_approval_round"),
        CheckConstraint(
            "(submitted_by_id IS NULL) = (submitted_at IS NULL)",
            name="ck_inventory_transfers_submitted_pair",
        ),
        CheckConstraint(
            "(approved_by_id IS NULL) = (approved_at IS NULL)",
            name="ck_inventory_transfers_approved_pair",
        ),
        CheckConstraint(
            "(rejected_by_id IS NULL) = (rejected_at IS NULL)",
            name="ck_inventory_transfers_rejected_pair",
        ),
        CheckConstraint(
            "rejection_reason IS NULL OR (rejected_by_id IS NOT NULL "
            "AND char_length(btrim(rejection_reason)) >= 5)",
            name="ck_inventory_transfers_rejection_reason",
        ),
        CheckConstraint(
            "status NOT IN ('pending_approval','approved') OR "
            "(route_type <> 'central_distribution' AND requires_approval "
            "AND submitted_by_id IS NOT NULL AND approval_round >= 1)",
            name="ck_inventory_transfers_approval_state",
        ),
        CheckConstraint(
            "status <> 'approved' OR approved_by_id IS NOT NULL",
            name="ck_inventory_transfers_approved_state",
        ),
        Index("ix_inventory_transfers_company_status", "company_id", "status", "created_at"),
        Index(
            "ix_inventory_transfers_destination", "company_id", "destination_warehouse_id", "status"
        ),
        Index("ix_inventory_transfers_origin", "company_id", "origin_warehouse_id", "status"),
        Index(
            "ix_inventory_transfers_pending_approval",
            "company_id",
            "origin_warehouse_id",
            postgresql_where=text("status = 'pending_approval'"),
        ),
    )


class InventoryTransferDetailModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_transfer_details"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    transfer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    inventory_lot_detail_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source_handling_unit_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    transit_handling_unit_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    quantity_planned: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quantity_dispatched: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, server_default="0"
    )
    quantity_received: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, server_default="0"
    )
    quantity_returned: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, server_default="0"
    )
    quantity_adjusted_out: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, server_default="0"
    )
    quantity_received_damaged: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, server_default="0"
    )
    quantity_surplus: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, server_default="0"
    )
    excess_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "transfer_id"],
            ["inventory_transfers.company_id", "inventory_transfers.id"],
            name="fk_inventory_transfer_details_transfer_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            name="fk_inventory_transfer_details_item_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_lot_detail_id"],
            ["inventory_lot_details.company_id", "inventory_lot_details.id"],
            name="fk_inventory_transfer_details_lot_detail_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "source_handling_unit_id"],
            [
                "inventory_handling_units.company_id",
                "inventory_handling_units.inventory_item_id",
                "inventory_handling_units.id",
            ],
            name="fk_inventory_transfer_details_source_hu",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "transit_handling_unit_id"],
            [
                "inventory_handling_units.company_id",
                "inventory_handling_units.inventory_item_id",
                "inventory_handling_units.id",
            ],
            name="fk_inventory_transfer_details_transit_hu",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("transfer_id", "line_number", name="uq_inventory_transfer_details_line"),
        UniqueConstraint("company_id", "id", name="uq_inventory_transfer_details_company_id"),
        CheckConstraint("line_number > 0", name="ck_inventory_transfer_details_line_positive"),
        CheckConstraint(
            "quantity_planned > 0 AND quantity_dispatched >= 0 AND quantity_received >= 0 "
            "AND quantity_returned >= 0 AND quantity_adjusted_out >= 0 "
            "AND quantity_received + quantity_returned + quantity_adjusted_out <= quantity_dispatched",
            name="ck_inventory_transfer_details_quantities",
        ),
        CheckConstraint(
            "quantity_received_damaged >= 0 AND quantity_surplus >= 0 "
            "AND quantity_received_damaged <= quantity_received",
            name="ck_inventory_transfer_details_condition_quantities",
        ),
        Index("ix_inventory_transfer_details_company_transfer", "company_id", "transfer_id"),
        Index("ix_inventory_transfer_details_transit_hu", "company_id", "transit_handling_unit_id"),
    )


class InventoryTransferDemandAllocationModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_transfer_demand_allocations"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    transfer_detail_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_request_detail_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    allocated_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quantity_dispatched: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, server_default="0"
    )
    quantity_received: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, server_default="0"
    )
    quantity_adjusted_out: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, server_default="0"
    )
    quantity_damaged: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, server_default="0"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "transfer_detail_id"],
            ["inventory_transfer_details.company_id", "inventory_transfer_details.id"],
            name="fk_transfer_demand_allocations_transfer_detail",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["purchase_request_detail_id", "company_id"],
            ["purchase_request_details.id", "purchase_request_details.company_id"],
            name="fk_transfer_demand_allocations_request_detail",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "transfer_detail_id",
            "purchase_request_detail_id",
            name="uq_transfer_demand_allocations_source",
        ),
        CheckConstraint(
            "allocated_quantity > 0 AND quantity_dispatched >= 0 AND quantity_received >= 0 "
            "AND quantity_adjusted_out >= 0 AND quantity_received + quantity_adjusted_out <= quantity_dispatched "
            "AND quantity_dispatched <= allocated_quantity",
            name="ck_transfer_demand_allocations_quantities",
        ),
        CheckConstraint(
            "quantity_damaged >= 0 AND quantity_damaged <= quantity_received",
            name="ck_transfer_demand_allocations_damaged",
        ),
        Index(
            "ix_transfer_demand_allocations_request_detail",
            "company_id",
            "purchase_request_detail_id",
        ),
    )


class InventoryTransferCommandModel(UUIDPKMixin, Base):
    __tablename__ = "inventory_transfer_commands"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    transfer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    actor_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_transfer_commands_company_id"),
        ForeignKeyConstraint(
            ["company_id", "transfer_id"],
            ["inventory_transfers.company_id", "inventory_transfers.id"],
            name="fk_inventory_transfer_commands_transfer",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "company_id", "action", "idempotency_key", name="uq_inventory_transfer_commands_key"
        ),
        CheckConstraint(
            "action IN ('create','update','cancel','dispatch','receive','incident','resolve',"
            "'resolve_adjustment','return','submit','approve','reject','withdraw',"
            "'close_reception','discrepancy_adjust','discrepancy_claim','discrepancy_release',"
            "'discrepancy_found','discrepancy_dismiss','resolve_discrepancy','origin_count')",
            name="ck_inventory_transfer_commands_action",
        ),
        Index("ix_inventory_transfer_commands_transfer", "company_id", "transfer_id", "created_at"),
    )


class InventoryTransferReceiptModel(UUIDPKMixin, Base):
    __tablename__ = "inventory_transfer_receipts"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    transfer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    transfer_detail_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    command_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    movement_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    handling_unit_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    received_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    condition: Mapped[str] = mapped_column(String(8), nullable=False, server_default="good")

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_transfer_receipts_company_id"),
        CheckConstraint(
            "condition IN ('good','damaged')", name="ck_inventory_transfer_receipts_condition"
        ),
        ForeignKeyConstraint(
            ["company_id", "transfer_id"],
            ["inventory_transfers.company_id", "inventory_transfers.id"],
            name="fk_inventory_transfer_receipts_transfer",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "transfer_detail_id"],
            ["inventory_transfer_details.company_id", "inventory_transfer_details.id"],
            name="fk_inventory_transfer_receipts_detail",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "command_id"],
            ["inventory_transfer_commands.company_id", "inventory_transfer_commands.id"],
            name="fk_inventory_transfer_receipts_command",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "movement_id"],
            ["inventory_movements.company_id", "inventory_movements.id"],
            name="fk_inventory_transfer_receipts_movement",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "handling_unit_id"],
            ["inventory_handling_units.company_id", "inventory_handling_units.id"],
            name="fk_inventory_transfer_receipts_handling_unit",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantity_received > 0", name="ck_inventory_transfer_receipts_positive"),
        Index(
            "ix_inventory_transfer_receipts_transfer", "company_id", "transfer_id", "received_at"
        ),
    )


class InventoryTransferIncidentModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_transfer_incidents"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    transfer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(String(500))
    opened_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolution: Mapped[str | None] = mapped_column(String(32))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "transfer_id"],
            ["inventory_transfers.company_id", "inventory_transfers.id"],
            name="fk_inventory_transfer_incidents_transfer",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "company_id",
            "transfer_id",
            "id",
            name="uq_inventory_transfer_incidents_transfer_identity",
        ),
        CheckConstraint(
            "status IN ('open','resolved')", name="ck_inventory_transfer_incidents_status"
        ),
        CheckConstraint(
            "(status = 'open' AND resolution IS NULL AND resolved_at IS NULL) OR "
            "(status = 'resolved' AND resolution IS NOT NULL AND resolved_at IS NOT NULL)",
            name="ck_inventory_transfer_incidents_resolution",
        ),
        Index(
            "uq_inventory_transfer_incidents_one_open",
            "company_id",
            "transfer_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )


class InventoryTransferDiscrepancyModel(UUIDPKMixin, TimestampMixin, Base):
    """One difference found while receiving: missing, extra or damaged goods."""

    __tablename__ = "inventory_transfer_discrepancies"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    transfer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    transfer_detail_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    damage_type: Mapped[str | None] = mapped_column(String(16))
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(String(500))
    location_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    handling_unit_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    receipt_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    command_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    incident_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    opened_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claim_reference: Mapped[str | None] = mapped_column(Text)
    claimed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(String(16))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    origin_count_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    origin_counted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    origin_counted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    origin_count_notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_inventory_transfer_discrepancies_company_id"),
        UniqueConstraint(
            "company_id",
            "transfer_id",
            "id",
            name="uq_inventory_transfer_discrepancies_transfer_identity",
        ),
        ForeignKeyConstraint(
            ["company_id", "transfer_id"],
            ["inventory_transfers.company_id", "inventory_transfers.id"],
            name="fk_inventory_transfer_discrepancies_transfer",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "transfer_detail_id"],
            ["inventory_transfer_details.company_id", "inventory_transfer_details.id"],
            name="fk_inventory_transfer_discrepancies_detail",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_inventory_transfer_discrepancies_location",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "handling_unit_id"],
            ["inventory_handling_units.company_id", "inventory_handling_units.id"],
            name="fk_inventory_transfer_discrepancies_handling_unit",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "receipt_id"],
            ["inventory_transfer_receipts.company_id", "inventory_transfer_receipts.id"],
            name="fk_inventory_transfer_discrepancies_receipt",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "command_id"],
            ["inventory_transfer_commands.company_id", "inventory_transfer_commands.id"],
            name="fk_inventory_transfer_discrepancies_command",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "transfer_id", "incident_id"],
            [
                "inventory_transfer_incidents.company_id",
                "inventory_transfer_incidents.transfer_id",
                "inventory_transfer_incidents.id",
            ],
            name="fk_inventory_transfer_discrepancies_incident",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "kind IN ('shortage','surplus','damage')",
            name="ck_inventory_transfer_discrepancies_kind",
        ),
        CheckConstraint(
            "status IN ('open','in_claim','resolved','cancelled')",
            name="ck_inventory_transfer_discrepancies_status",
        ),
        CheckConstraint(
            "source IN ('receipt','reception_close','incident')",
            name="ck_inventory_transfer_discrepancies_source",
        ),
        CheckConstraint("quantity > 0", name="ck_inventory_transfer_discrepancies_quantity"),
        CheckConstraint(
            "char_length(btrim(notes)) >= 5", name="ck_inventory_transfer_discrepancies_notes"
        ),
        CheckConstraint(
            "(kind = 'damage') = (damage_type IS NOT NULL) AND (damage_type IS NULL OR "
            "damage_type IN ('broken','crushed','wet','contaminated','packaging','tampered',"
            "'temperature','other'))",
            name="ck_inventory_transfer_discrepancies_damage_type",
        ),
        CheckConstraint(
            "kind = 'shortage' OR location_id IS NOT NULL",
            name="ck_inventory_transfer_discrepancies_location",
        ),
        CheckConstraint(
            "resolution IS NULL "
            "OR (kind = 'shortage' AND resolution IN ('written_off','found')) "
            "OR (kind = 'damage' AND resolution IN ('written_off','released')) "
            "OR (kind = 'surplus' AND resolution IN ('regularized','dismissed'))",
            name="ck_inventory_transfer_discrepancies_resolution",
        ),
        CheckConstraint(
            "((claim_reference IS NULL) = (claimed_by_id IS NULL)) "
            "AND ((claimed_by_id IS NULL) = (claimed_at IS NULL)) "
            "AND (claimed_at IS NULL OR kind = 'damage')",
            name="ck_inventory_transfer_discrepancies_claim",
        ),
        CheckConstraint(
            "(status = 'open' AND resolution IS NULL AND resolved_by_id IS NULL "
            "AND resolved_at IS NULL AND claimed_at IS NULL) "
            "OR (status = 'in_claim' AND kind = 'damage' AND resolution IS NULL "
            "AND resolved_by_id IS NULL AND resolved_at IS NULL AND claimed_at IS NOT NULL) "
            "OR (status = 'resolved' AND resolved_by_id IS NOT NULL AND resolved_at IS NOT NULL "
            "AND resolution IN ('written_off','released','regularized')) "
            "OR (status = 'cancelled' AND resolved_by_id IS NOT NULL AND resolved_at IS NOT NULL "
            "AND resolution IN ('found','dismissed'))",
            name="ck_inventory_transfer_discrepancies_lifecycle",
        ),
        CheckConstraint(
            "((origin_counted_by_id IS NULL) = (origin_counted_at IS NULL)) "
            "AND (origin_counted_at IS NULL OR origin_count_required) "
            "AND (NOT origin_count_required OR kind <> 'damage')",
            name="ck_inventory_transfer_discrepancies_origin_count",
        ),
        Index(
            "ix_inventory_transfer_discrepancies_transfer", "company_id", "transfer_id", "status"
        ),
        Index(
            "uq_inventory_transfer_discrepancies_open_shortage",
            "company_id",
            "transfer_detail_id",
            unique=True,
            postgresql_where=text("kind = 'shortage' AND status = 'open'"),
        ),
        Index(
            "ix_inventory_transfer_discrepancies_origin_count",
            "company_id",
            "transfer_id",
            postgresql_where=text("origin_count_required AND origin_counted_at IS NULL"),
        ),
    )
