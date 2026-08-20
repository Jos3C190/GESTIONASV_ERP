"""Inventory identities, packaging, immutable ledger and capacity reservations."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("inventory:read", "Consultar inventario y capacidad", "inventory"),
    ("inventory:manage_packaging", "Gestionar unidades base y presentaciones", "inventory"),
    ("inventory:receive", "Registrar recepciones de inventario", "inventory"),
    ("inventory:move", "Registrar movimientos y traslados", "inventory"),
    ("inventory:capacity", "Consultar proyecciones de capacidad", "inventory"),
    ("inventory:reserve", "Reservar y confirmar capacidad", "inventory"),
    ("capacity:override_operational", "Autorizar exceso del límite operativo", "inventory"),
)


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")
    )


def _sql_literal(value: str) -> str:
    """Quote developer-owned migration constants for online and offline SQL."""

    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    for code, description, module in PERMISSIONS:
        # Migration-owned constants are quoted explicitly because regular
        # DBAPI parameters are emitted as NULL by offline ``alembic --sql``.
        op.execute(
            "INSERT INTO permissions (id, code, description, module, created_at) "
            f"VALUES (gen_random_uuid(), {_sql_literal(code)}, "
            f"{_sql_literal(description)}, {_sql_literal(module)}, now()) "
            "ON CONFLICT DO NOTHING"
        )

    # Only the canonical global system role has a stable identity in the RBAC
    # schema.  Company-owned role names are mutable/user-owned, so granting by
    # labels such as "ADMINISTRADOR DE OPERACIONES" would be an unsafe privilege
    # escalation.  Their assignments are managed explicitly by administrators
    # (and by the development seed where applicable).
    quoted_all = ",".join(f"'{code}'" for code, _description, _module in PERMISSIONS)
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id, created_at) "
        "SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p "
        "WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE "
        "AND r.company_id IS NULL AND r.deleted_at IS NULL "
        f"AND p.deleted_at IS NULL AND p.code IN ({quoted_all}) "
        "ON CONFLICT DO NOTHING"
    )

    op.create_table(
        "inventory_items",
        _uuid_pk(),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("variant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("base_unit_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            ondelete="RESTRICT",
            name="fk_inventory_items_product_company",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "variant_id"],
            ["product_variants.company_id", "product_variants.id"],
            ondelete="RESTRICT",
            name="fk_inventory_items_variant_company",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "base_unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_inventory_items_base_unit_company",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_inventory_items_company_id"),
        sa.CheckConstraint(
            "(product_id IS NOT NULL) <> (variant_id IS NOT NULL)",
            name="ck_inventory_items_exact_target",
        ),
    )
    op.create_index(
        "uq_inventory_items_product",
        "inventory_items",
        ["company_id", "product_id"],
        unique=True,
        postgresql_where=sa.text("product_id IS NOT NULL"),
    )
    op.create_index(
        "uq_inventory_items_variant",
        "inventory_items",
        ["company_id", "variant_id"],
        unique=True,
        postgresql_where=sa.text("variant_id IS NOT NULL"),
    )
    op.create_index(
        "ix_inventory_items_company_active",
        "inventory_items",
        ["company_id", "is_active"],
    )

    op.create_table(
        "inventory_packaging_definitions",
        _uuid_pk(),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_item_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("packaging_type", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("base_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("gross_weight_kg", sa.Numeric(18, 6), nullable=True),
        sa.Column("length_m", sa.Numeric(18, 6), nullable=True),
        sa.Column("width_m", sa.Numeric(18, 6), nullable=True),
        sa.Column("height_m", sa.Numeric(18, 6), nullable=True),
        sa.Column("volume_m3", sa.Numeric(18, 6), nullable=True),
        sa.Column("stackable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_stack", sa.Integer(), nullable=True),
        sa.Column("supersedes_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="CASCADE",
            name="fk_inventory_packaging_item_company",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "supersedes_id"],
            [
                "inventory_packaging_definitions.company_id",
                "inventory_packaging_definitions.inventory_item_id",
                "inventory_packaging_definitions.id",
            ],
            ondelete="RESTRICT",
            name="fk_inventory_packaging_supersedes_item",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_inventory_packaging_company_id"),
        sa.UniqueConstraint(
            "company_id",
            "inventory_item_id",
            "id",
            name="uq_inventory_packaging_item_identity",
        ),
        sa.UniqueConstraint(
            "company_id",
            "inventory_item_id",
            "code",
            "version",
            name="uq_inventory_packaging_code_version",
        ),
        sa.CheckConstraint(
            "packaging_type IN ('piece','box','bag','package','roll','drum','container','loose_other')",
            name="ck_inventory_packaging_type",
        ),
        sa.CheckConstraint("base_quantity > 0", name="ck_inventory_packaging_quantity_positive"),
        sa.CheckConstraint(
            "gross_weight_kg IS NULL OR gross_weight_kg > 0",
            name="ck_inventory_packaging_weight_positive",
        ),
        sa.CheckConstraint(
            "length_m IS NULL OR length_m > 0", name="ck_inventory_packaging_length_positive"
        ),
        sa.CheckConstraint(
            "width_m IS NULL OR width_m > 0", name="ck_inventory_packaging_width_positive"
        ),
        sa.CheckConstraint(
            "height_m IS NULL OR height_m > 0", name="ck_inventory_packaging_height_positive"
        ),
        sa.CheckConstraint(
            "volume_m3 IS NULL OR volume_m3 > 0", name="ck_inventory_packaging_volume_positive"
        ),
        sa.CheckConstraint(
            "(length_m IS NULL AND width_m IS NULL AND height_m IS NULL) OR "
            "(length_m IS NOT NULL AND width_m IS NOT NULL AND height_m IS NOT NULL)",
            name="ck_inventory_packaging_dimensions_complete",
        ),
        sa.CheckConstraint(
            "(stackable AND (max_stack IS NULL OR max_stack >= 1)) OR "
            "(NOT stackable AND max_stack IS NULL)",
            name="ck_inventory_packaging_stack",
        ),
        sa.CheckConstraint("version >= 1", name="ck_inventory_packaging_version_positive"),
    )
    op.create_index(
        "uq_inventory_packaging_current_code",
        "inventory_packaging_definitions",
        ["company_id", "inventory_item_id", "code"],
        unique=True,
        postgresql_where=sa.text("is_current AND is_active"),
    )

    op.create_table(
        "inventory_handling_units",
        _uuid_pk(),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_item_id", UUID(as_uuid=True), nullable=False),
        sa.Column("packaging_definition_id", UUID(as_uuid=True), nullable=True),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("lot_code", sa.String(120), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("quantity_base", sa.Numeric(18, 6), nullable=False),
        sa.Column("packaging_snapshot", JSONB(), nullable=True),
        sa.Column("actual_gross_weight_kg", sa.Numeric(18, 6), nullable=True),
        sa.Column("actual_length_m", sa.Numeric(18, 6), nullable=True),
        sa.Column("actual_width_m", sa.Numeric(18, 6), nullable=True),
        sa.Column("actual_height_m", sa.Numeric(18, 6), nullable=True),
        sa.Column("actual_volume_m3", sa.Numeric(18, 6), nullable=True),
        sa.Column("occupied_weight_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("occupied_volume_m3", sa.Numeric(18, 6), nullable=False),
        sa.Column("stock_status", sa.String(20), nullable=False),
        sa.Column("measurement_status", sa.String(20), nullable=False),
        sa.Column("measurement_source", sa.String(20), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["location_id", "warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            ondelete="RESTRICT",
            name="fk_inventory_handling_units_location_warehouse",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_inventory_handling_units_item_company",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "packaging_definition_id"],
            [
                "inventory_packaging_definitions.company_id",
                "inventory_packaging_definitions.inventory_item_id",
                "inventory_packaging_definitions.id",
            ],
            ondelete="RESTRICT",
            name="fk_inventory_handling_units_packaging_item",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_inventory_handling_units_company_id"),
        sa.UniqueConstraint(
            "company_id",
            "inventory_item_id",
            "id",
            name="uq_inventory_handling_units_item_identity",
        ),
        sa.CheckConstraint(
            "quantity_base > 0", name="ck_inventory_handling_units_quantity_positive"
        ),
        sa.CheckConstraint(
            "occupied_weight_kg >= 0", name="ck_inventory_handling_units_weight_nonnegative"
        ),
        sa.CheckConstraint(
            "occupied_volume_m3 >= 0", name="ck_inventory_handling_units_volume_nonnegative"
        ),
        sa.CheckConstraint(
            "actual_gross_weight_kg IS NULL OR actual_gross_weight_kg > 0",
            name="ck_inventory_handling_units_actual_weight_positive",
        ),
        sa.CheckConstraint(
            "actual_length_m IS NULL OR actual_length_m > 0",
            name="ck_inventory_handling_units_actual_length_positive",
        ),
        sa.CheckConstraint(
            "actual_width_m IS NULL OR actual_width_m > 0",
            name="ck_inventory_handling_units_actual_width_positive",
        ),
        sa.CheckConstraint(
            "actual_height_m IS NULL OR actual_height_m > 0",
            name="ck_inventory_handling_units_actual_height_positive",
        ),
        sa.CheckConstraint(
            "actual_volume_m3 IS NULL OR actual_volume_m3 > 0",
            name="ck_inventory_handling_units_actual_volume_positive",
        ),
        sa.CheckConstraint(
            "(actual_length_m IS NULL AND actual_width_m IS NULL AND actual_height_m IS NULL) OR "
            "(actual_length_m IS NOT NULL AND actual_width_m IS NOT NULL AND actual_height_m IS NOT NULL)",
            name="ck_inventory_handling_units_dimensions_complete",
        ),
        sa.CheckConstraint(
            "stock_status IN ('available','quarantine','blocked','damaged','in_transit')",
            name="ck_inventory_handling_units_stock_status",
        ),
        sa.CheckConstraint(
            "measurement_status IN ('complete','incomplete','verified')",
            name="ck_inventory_handling_units_measurement_status",
        ),
        sa.CheckConstraint(
            "measurement_source IN ('master','receipt','manual','device')",
            name="ck_inventory_handling_units_measurement_source",
        ),
        sa.CheckConstraint(
            "measurement_status <> 'incomplete' OR "
            "(stock_status = 'quarantine' AND occupied_weight_kg = 0 AND occupied_volume_m3 = 0)",
            name="ck_inventory_handling_units_incomplete_quarantine",
        ),
        sa.CheckConstraint(
            "measurement_status = 'incomplete' OR (occupied_weight_kg > 0 AND occupied_volume_m3 > 0)",
            name="ck_inventory_handling_units_measured_values",
        ),
        sa.CheckConstraint(
            "measurement_status = 'incomplete' OR measurement_source = 'master' OR "
            "(actual_gross_weight_kg IS NOT NULL AND actual_volume_m3 IS NOT NULL)",
            name="ck_inventory_handling_units_actual_measure_evidence",
        ),
    )
    op.create_index(
        "uq_inventory_handling_units_code",
        "inventory_handling_units",
        ["company_id", sa.text("lower(code)")],
        unique=True,
    )
    op.create_index(
        "ix_inventory_handling_units_location_status",
        "inventory_handling_units",
        ["location_id", "stock_status"],
    )

    op.create_table(
        "inventory_capacity_reservations",
        _uuid_pk(),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_item_id", UUID(as_uuid=True), nullable=False),
        sa.Column("packaging_definition_id", UUID(as_uuid=True), nullable=True),
        sa.Column("quantity_base", sa.Numeric(18, 6), nullable=False),
        sa.Column("reserved_weight_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("reserved_volume_m3", sa.Numeric(18, 6), nullable=False),
        sa.Column("measurement_status", sa.String(20), nullable=False, server_default="complete"),
        sa.Column("stock_status", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("operational_override_id", UUID(as_uuid=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["location_id", "warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            ondelete="RESTRICT",
            name="fk_inventory_capacity_reservations_location_warehouse",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_inventory_capacity_reservations_item_company",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "packaging_definition_id"],
            [
                "inventory_packaging_definitions.company_id",
                "inventory_packaging_definitions.inventory_item_id",
                "inventory_packaging_definitions.id",
            ],
            ondelete="RESTRICT",
            name="fk_inventory_capacity_reservations_packaging_item",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "id", name="uq_inventory_capacity_reservations_company_id"
        ),
        sa.CheckConstraint(
            "quantity_base > 0", name="ck_inventory_capacity_reservations_quantity_positive"
        ),
        sa.CheckConstraint(
            "reserved_weight_kg >= 0", name="ck_inventory_capacity_reservations_weight_nonnegative"
        ),
        sa.CheckConstraint(
            "reserved_volume_m3 >= 0", name="ck_inventory_capacity_reservations_volume_nonnegative"
        ),
        sa.CheckConstraint(
            "status IN ('active','confirmed','consumed','cancelled','expired')",
            name="ck_inventory_capacity_reservations_status",
        ),
        sa.CheckConstraint(
            "stock_status IN ('available','quarantine','blocked','damaged','in_transit')",
            name="ck_inventory_capacity_reservations_stock_status",
        ),
        sa.CheckConstraint(
            "measurement_status IN ('complete','incomplete','verified')",
            name="ck_inventory_capacity_reservations_measurement_status",
        ),
        sa.CheckConstraint(
            "measurement_status <> 'incomplete' OR "
            "(stock_status = 'quarantine' AND reserved_weight_kg = 0 AND reserved_volume_m3 = 0)",
            name="ck_inventory_capacity_reservations_incomplete_quarantine",
        ),
        sa.CheckConstraint(
            "measurement_status = 'incomplete' OR (reserved_weight_kg > 0 AND reserved_volume_m3 > 0)",
            name="ck_inventory_capacity_reservations_measured_values",
        ),
    )
    op.create_index(
        "ix_inventory_capacity_reservations_location_status",
        "inventory_capacity_reservations",
        ["location_id", "status", "expires_at"],
    )

    op.create_table(
        "inventory_capacity_operational_overrides",
        _uuid_pk(),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("granted_by", UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", UUID(as_uuid=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["location_id", "warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            ondelete="RESTRICT",
            name="fk_inventory_capacity_overrides_location_warehouse",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_inventory_capacity_overrides_company_id"),
        sa.UniqueConstraint(
            "company_id",
            "location_id",
            "id",
            name="uq_inventory_capacity_overrides_location_identity",
        ),
        sa.CheckConstraint(
            "status IN ('active','revoked','expired')",
            name="ck_inventory_capacity_overrides_status",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) >= 10", name="ck_inventory_capacity_overrides_reason"
        ),
    )
    op.create_index(
        "uq_inventory_capacity_overrides_active_location",
        "inventory_capacity_operational_overrides",
        ["company_id", "location_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_inventory_capacity_overrides_location_status",
        "inventory_capacity_operational_overrides",
        ["location_id", "status", "valid_until"],
    )
    op.create_foreign_key(
        "fk_inventory_capacity_reservations_override_location",
        "inventory_capacity_reservations",
        "inventory_capacity_operational_overrides",
        ["company_id", "location_id", "operational_override_id"],
        ["company_id", "location_id", "id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "inventory_movements",
        _uuid_pk(),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("movement_type", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("source_reference", sa.String(160), nullable=True),
        sa.Column("reversal_of_id", UUID(as_uuid=True), nullable=True),
        sa.Column("reservation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("posted_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["company_id", "reversal_of_id"],
            ["inventory_movements.company_id", "inventory_movements.id"],
            ondelete="RESTRICT",
            name="fk_inventory_movements_reversal_company",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "reservation_id"],
            ["inventory_capacity_reservations.company_id", "inventory_capacity_reservations.id"],
            ondelete="RESTRICT",
            name="fk_inventory_movements_reservation_company",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_inventory_movements_company_id"),
        sa.UniqueConstraint(
            "company_id", "idempotency_key", name="uq_inventory_movements_idempotency"
        ),
        sa.CheckConstraint(
            "movement_type IN ('receipt','putaway','transfer','pick','shipment','adjustment_in','adjustment_out','reversal')",
            name="ck_inventory_movements_type",
        ),
    )
    op.create_index(
        "ix_inventory_movements_company_posted", "inventory_movements", ["company_id", "posted_at"]
    )

    op.create_table(
        "inventory_movement_lines",
        _uuid_pk(),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("movement_id", UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", UUID(as_uuid=True), nullable=False),
        sa.Column("handling_unit_id", UUID(as_uuid=True), nullable=True),
        sa.Column("operational_override_id", UUID(as_uuid=True), nullable=True),
        sa.Column("lot_code", sa.String(120), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("from_warehouse_id", UUID(as_uuid=True), nullable=True),
        sa.Column("from_location_id", UUID(as_uuid=True), nullable=True),
        sa.Column("to_warehouse_id", UUID(as_uuid=True), nullable=True),
        sa.Column("to_location_id", UUID(as_uuid=True), nullable=True),
        sa.Column("from_stock_status", sa.String(20), nullable=True),
        sa.Column("to_stock_status", sa.String(20), nullable=True),
        sa.Column("quantity_base", sa.Numeric(18, 6), nullable=False),
        sa.Column("occupied_weight_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("occupied_volume_m3", sa.Numeric(18, 6), nullable=False),
        sa.Column("measurement_status", sa.String(20), nullable=False),
        sa.Column("packaging_snapshot", JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id", "movement_id"],
            ["inventory_movements.company_id", "inventory_movements.id"],
            ondelete="RESTRICT",
            name="fk_inventory_movement_lines_header_company",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_inventory_movement_lines_item_company",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "handling_unit_id"],
            [
                "inventory_handling_units.company_id",
                "inventory_handling_units.inventory_item_id",
                "inventory_handling_units.id",
            ],
            ondelete="RESTRICT",
            name="fk_inventory_movement_lines_handling_unit_item",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "to_location_id", "operational_override_id"],
            [
                "inventory_capacity_operational_overrides.company_id",
                "inventory_capacity_operational_overrides.location_id",
                "inventory_capacity_operational_overrides.id",
            ],
            ondelete="RESTRICT",
            name="fk_inventory_movement_lines_override_location",
        ),
        sa.ForeignKeyConstraint(
            ["from_location_id", "from_warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            ondelete="RESTRICT",
            name="fk_inventory_movement_lines_from_location",
        ),
        sa.ForeignKeyConstraint(
            ["to_location_id", "to_warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            ondelete="RESTRICT",
            name="fk_inventory_movement_lines_to_location",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "movement_id", "line_number", name="uq_inventory_movement_lines_number"
        ),
        sa.CheckConstraint("line_number >= 1", name="ck_inventory_movement_lines_number_positive"),
        sa.CheckConstraint(
            "quantity_base > 0", name="ck_inventory_movement_lines_quantity_positive"
        ),
        sa.CheckConstraint(
            "occupied_weight_kg >= 0", name="ck_inventory_movement_lines_weight_nonnegative"
        ),
        sa.CheckConstraint(
            "occupied_volume_m3 >= 0", name="ck_inventory_movement_lines_volume_nonnegative"
        ),
        sa.CheckConstraint(
            "measurement_status IN ('complete','incomplete','verified')",
            name="ck_inventory_movement_lines_measurement_status",
        ),
        sa.CheckConstraint(
            "measurement_status <> 'incomplete' OR (occupied_weight_kg = 0 AND occupied_volume_m3 = 0)",
            name="ck_inventory_movement_lines_incomplete_values",
        ),
        sa.CheckConstraint(
            "measurement_status = 'incomplete' OR (occupied_weight_kg > 0 AND occupied_volume_m3 > 0)",
            name="ck_inventory_movement_lines_measured_values",
        ),
        sa.CheckConstraint(
            "(from_location_id IS NULL) = (from_warehouse_id IS NULL)",
            name="ck_inventory_movement_lines_from_complete",
        ),
        sa.CheckConstraint(
            "(to_location_id IS NULL) = (to_warehouse_id IS NULL)",
            name="ck_inventory_movement_lines_to_complete",
        ),
        sa.CheckConstraint(
            "from_location_id IS NOT NULL OR to_location_id IS NOT NULL",
            name="ck_inventory_movement_lines_endpoint_required",
        ),
        sa.CheckConstraint(
            "operational_override_id IS NULL OR to_location_id IS NOT NULL",
            name="ck_inventory_movement_lines_override_destination",
        ),
        sa.CheckConstraint(
            "(from_location_id IS NULL) = (from_stock_status IS NULL)",
            name="ck_inventory_movement_lines_from_status_complete",
        ),
        sa.CheckConstraint(
            "(to_location_id IS NULL) = (to_stock_status IS NULL)",
            name="ck_inventory_movement_lines_to_status_complete",
        ),
        sa.CheckConstraint(
            "from_stock_status IS NULL OR from_stock_status IN ('available','quarantine','blocked','damaged','in_transit')",
            name="ck_inventory_movement_lines_from_status",
        ),
        sa.CheckConstraint(
            "to_stock_status IS NULL OR to_stock_status IN ('available','quarantine','blocked','damaged','in_transit')",
            name="ck_inventory_movement_lines_to_status",
        ),
    )

    op.create_table(
        "inventory_balances",
        _uuid_pk(),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_item_id", UUID(as_uuid=True), nullable=False),
        sa.Column("stock_status", sa.String(20), nullable=False),
        sa.Column("lot_code", sa.String(120), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("quantity_base", sa.Numeric(18, 6), nullable=False),
        sa.Column("occupied_weight_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("occupied_volume_m3", sa.Numeric(18, 6), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["location_id", "warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            ondelete="RESTRICT",
            name="fk_inventory_balances_location_warehouse",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_inventory_balances_item_company",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("quantity_base >= 0", name="ck_inventory_balances_quantity_nonnegative"),
        sa.CheckConstraint(
            "occupied_weight_kg >= 0", name="ck_inventory_balances_weight_nonnegative"
        ),
        sa.CheckConstraint(
            "occupied_volume_m3 >= 0", name="ck_inventory_balances_volume_nonnegative"
        ),
        sa.CheckConstraint(
            "stock_status IN ('available','quarantine','blocked','damaged','in_transit')",
            name="ck_inventory_balances_stock_status",
        ),
    )
    op.create_index(
        "uq_inventory_balances_projection",
        "inventory_balances",
        [
            "company_id",
            "location_id",
            "inventory_item_id",
            "stock_status",
            sa.text("coalesce(lot_code, '')"),
            sa.text("coalesce(expiry_date, DATE '0001-01-01')"),
        ],
        unique=True,
    )
    op.create_index(
        "ix_inventory_balances_location",
        "inventory_balances",
        ["company_id", "warehouse_id", "location_id"],
    )

    # PostgreSQL enforces the ledger's append-only contract independently of API code.
    op.execute(
        """
        CREATE FUNCTION reject_inventory_ledger_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'inventory ledger rows are immutable';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_inventory_movements_immutable
        BEFORE UPDATE OR DELETE ON inventory_movements
        FOR EACH ROW EXECUTE FUNCTION reject_inventory_ledger_mutation();
        CREATE TRIGGER trg_inventory_movement_lines_immutable
        BEFORE UPDATE OR DELETE ON inventory_movement_lines
        FOR EACH ROW EXECUTE FUNCTION reject_inventory_ledger_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_inventory_movement_lines_immutable ON inventory_movement_lines"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_inventory_movements_immutable ON inventory_movements")
    op.execute("DROP FUNCTION IF EXISTS reject_inventory_ledger_mutation()")
    for table in (
        "inventory_balances",
        "inventory_movement_lines",
        "inventory_movements",
        "inventory_capacity_reservations",
        "inventory_capacity_operational_overrides",
        "inventory_handling_units",
        "inventory_packaging_definitions",
        "inventory_items",
    ):
        op.drop_table(table)
    # RBAC catalogue rows and grants are additive shared data.  Because upgrade
    # uses ON CONFLICT, a downgrade cannot distinguish pre-existing assignments
    # from rows created by this revision.  Preserve them rather than deleting
    # user-owned or historical authorization state.
