"""Add company-scoped transfer documents and mobile vehicle locations."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0086"
down_revision = "0085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_warehouses_company_identity", "warehouses", ["company_id", "id"]
    )
    op.add_column(
        "warehouses",
        sa.Column("is_transit", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "ck_warehouses_central_not_transit",
        "warehouses",
        "NOT (is_central AND is_transit)",
    )
    op.drop_constraint("ck_locations_type", "locations", type_="check")
    op.create_check_constraint(
        "ck_locations_type",
        "locations",
        "location_type IN ('standard','bulk','receiving','reserve','picking','staging',"
        "'quality','packing','shipping','returns','virtual','vehicle')",
    )

    op.create_table(
        "inventory_vehicles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transit_warehouse_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transit_location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_inventory_vehicles_company_id"),
        sa.UniqueConstraint("company_id", "code", name="uq_inventory_vehicles_company_code"),
        sa.UniqueConstraint(
            "company_id", "transit_location_id", name="uq_inventory_vehicles_transit_location"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["company_id", "transit_warehouse_id"],
            ["warehouses.company_id", "warehouses.id"],
            name="fk_inventory_vehicles_transit_warehouse_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["transit_location_id", "transit_warehouse_id"],
            ["locations.id", "locations.warehouse_id"],
            name="fk_inventory_vehicles_transit_location_warehouse",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_inventory_vehicles_status"),
    )
    op.create_index(
        "ix_inventory_vehicles_company_status", "inventory_vehicles", ["company_id", "status"]
    )

    op.create_table(
        "inventory_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("origin_warehouse_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("destination_warehouse_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="preparation", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dispatched_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("received_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatch_command_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dispatch_movement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_inventory_transfers_company_id"),
        sa.UniqueConstraint("company_id", "code", name="uq_inventory_transfers_company_code"),
        sa.UniqueConstraint(
            "company_id", "dispatch_command_id", name="uq_inventory_transfers_dispatch_command"
        ),
        sa.UniqueConstraint(
            "company_id", "dispatch_movement_id", name="uq_inventory_transfers_dispatch_movement"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["company_id", "origin_warehouse_id"],
            ["warehouses.company_id", "warehouses.id"],
            name="fk_inventory_transfers_origin_warehouse_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "destination_warehouse_id"],
            ["warehouses.company_id", "warehouses.id"],
            name="fk_inventory_transfers_destination_warehouse_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "vehicle_id"],
            ["inventory_vehicles.company_id", "inventory_vehicles.id"],
            name="fk_inventory_transfers_vehicle_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "dispatch_movement_id"],
            ["inventory_movements.company_id", "inventory_movements.id"],
            name="fk_inventory_transfers_dispatch_movement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('preparation','in_transit','received','incident','cancelled')",
            name="ck_inventory_transfers_status",
        ),
        sa.CheckConstraint(
            "origin_warehouse_id <> destination_warehouse_id",
            name="ck_inventory_transfers_distinct_warehouses",
        ),
    )
    op.create_index(
        "ix_inventory_transfers_company_status",
        "inventory_transfers",
        ["company_id", "status", "created_at"],
    )
    op.create_index(
        "ix_inventory_transfers_destination",
        "inventory_transfers",
        ["company_id", "destination_warehouse_id", "status"],
    )

    op.create_table(
        "inventory_transfer_details",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_lot_detail_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_handling_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transit_handling_unit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quantity_planned", sa.Numeric(18, 6), nullable=False),
        sa.Column("quantity_dispatched", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("quantity_received", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("quantity_returned", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("excess_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transfer_id", "line_number", name="uq_inventory_transfer_details_line"),
        sa.UniqueConstraint("company_id", "id", name="uq_inventory_transfer_details_company_id"),
        sa.ForeignKeyConstraint(
            ["company_id", "transfer_id"],
            ["inventory_transfers.company_id", "inventory_transfers.id"],
            name="fk_inventory_transfer_details_transfer_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            name="fk_inventory_transfer_details_item_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_lot_detail_id"],
            ["inventory_lot_details.company_id", "inventory_lot_details.id"],
            name="fk_inventory_transfer_details_lot_detail_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "source_handling_unit_id"],
            ["inventory_handling_units.company_id", "inventory_handling_units.inventory_item_id", "inventory_handling_units.id"],
            name="fk_inventory_transfer_details_source_hu",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "transit_handling_unit_id"],
            ["inventory_handling_units.company_id", "inventory_handling_units.inventory_item_id", "inventory_handling_units.id"],
            name="fk_inventory_transfer_details_transit_hu",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("line_number > 0", name="ck_inventory_transfer_details_line_positive"),
        sa.CheckConstraint(
            "quantity_planned > 0 AND quantity_dispatched >= 0 AND quantity_received >= 0 "
            "AND quantity_returned >= 0 AND quantity_received + quantity_returned <= quantity_dispatched",
            name="ck_inventory_transfer_details_quantities",
        ),
    )
    op.create_index(
        "ix_inventory_transfer_details_company_transfer",
        "inventory_transfer_details",
        ["company_id", "transfer_id"],
    )
    op.create_index(
        "ix_inventory_transfer_details_transit_hu",
        "inventory_transfer_details",
        ["company_id", "transit_handling_unit_id"],
    )

    op.create_table(
        "inventory_transfer_demand_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transfer_detail_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_request_detail_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allocated_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("quantity_dispatched", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("quantity_received", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "transfer_detail_id", "purchase_request_detail_id", name="uq_transfer_demand_allocations_source"
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "transfer_detail_id"],
            ["inventory_transfer_details.company_id", "inventory_transfer_details.id"],
            name="fk_transfer_demand_allocations_transfer_detail",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_request_detail_id", "company_id"],
            ["purchase_request_details.id", "purchase_request_details.company_id"],
            name="fk_transfer_demand_allocations_request_detail",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "allocated_quantity > 0 AND quantity_dispatched >= 0 AND quantity_received >= 0 "
            "AND quantity_received <= quantity_dispatched AND quantity_dispatched <= allocated_quantity",
            name="ck_transfer_demand_allocations_quantities",
        ),
    )
    op.create_index(
        "ix_transfer_demand_allocations_request_detail",
        "inventory_transfer_demand_allocations",
        ["company_id", "purchase_request_detail_id"],
    )

    op.create_table(
        "inventory_transfer_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_inventory_transfer_commands_company_id"),
        sa.UniqueConstraint(
            "company_id", "action", "idempotency_key", name="uq_inventory_transfer_commands_key"
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "transfer_id"],
            ["inventory_transfers.company_id", "inventory_transfers.id"],
            name="fk_inventory_transfer_commands_transfer",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "action IN ('create','update','cancel','dispatch','receive','incident','resolve','return')",
            name="ck_inventory_transfer_commands_action",
        ),
    )
    op.create_index(
        "ix_inventory_transfer_commands_transfer",
        "inventory_transfer_commands",
        ["company_id", "transfer_id", "created_at"],
    )
    op.create_foreign_key(
        "fk_inventory_transfers_dispatch_command",
        "inventory_transfers",
        "inventory_transfer_commands",
        ["company_id", "dispatch_command_id"],
        ["company_id", "id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "inventory_transfer_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transfer_detail_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handling_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity_received", sa.Numeric(18, 6), nullable=False),
        sa.Column("received_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id", "transfer_id"],
            ["inventory_transfers.company_id", "inventory_transfers.id"],
            name="fk_inventory_transfer_receipts_transfer",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "transfer_detail_id"],
            ["inventory_transfer_details.company_id", "inventory_transfer_details.id"],
            name="fk_inventory_transfer_receipts_detail",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "command_id"],
            ["inventory_transfer_commands.company_id", "inventory_transfer_commands.id"],
            name="fk_inventory_transfer_receipts_command",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "movement_id"],
            ["inventory_movements.company_id", "inventory_movements.id"],
            name="fk_inventory_transfer_receipts_movement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "handling_unit_id"],
            ["inventory_handling_units.company_id", "inventory_handling_units.id"],
            name="fk_inventory_transfer_receipts_handling_unit",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("quantity_received > 0", name="ck_inventory_transfer_receipts_positive"),
    )
    op.create_index(
        "ix_inventory_transfer_receipts_transfer",
        "inventory_transfer_receipts",
        ["company_id", "transfer_id", "received_at"],
    )

    op.create_table(
        "inventory_transfer_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_reference", sa.String(length=500), nullable=True),
        sa.Column("opened_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolution", sa.String(length=32), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id", "transfer_id"],
            ["inventory_transfers.company_id", "inventory_transfers.id"],
            name="fk_inventory_transfer_incidents_transfer",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("status IN ('open','resolved')", name="ck_inventory_transfer_incidents_status"),
        sa.CheckConstraint(
            "(status = 'open' AND resolution IS NULL AND resolved_at IS NULL) OR "
            "(status = 'resolved' AND resolution IS NOT NULL AND resolved_at IS NOT NULL)",
            name="ck_inventory_transfer_incidents_resolution",
        ),
    )
    op.create_index(
        "uq_inventory_transfer_incidents_one_open",
        "inventory_transfer_incidents",
        ["company_id", "transfer_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )

    # Each company with a valid active central warehouse and headquarters gets
    # one non-commercial transit warehouse. Companies lacking that prerequisite
    # remain untouched and can be reported by the runtime preflight.
    op.execute(
        sa.text(
            """
            INSERT INTO warehouse_categories (id, company_id, name, description, is_active, created_at, updated_at)
            SELECT gen_random_uuid(), candidate.company_id, 'Tránsito interno',
                   'Categoría técnica para ubicaciones móviles de vehículos.', true, now(), now()
            FROM (
                SELECT DISTINCT central.company_id
                FROM warehouses AS central
                JOIN branches AS headquarters
                  ON headquarters.id = central.branch_id
                 AND headquarters.company_id = central.company_id
                WHERE central.is_central IS TRUE
                  AND central.is_active IS TRUE
                  AND central.operational_status = 'active'
                  AND central.deleted_at IS NULL
                  AND headquarters.is_headquarters IS TRUE
                  AND headquarters.is_active IS TRUE
                  AND headquarters.operational_status = 'active'
                  AND headquarters.deleted_at IS NULL
            ) AS candidate
            WHERE NOT EXISTS (
                SELECT 1 FROM warehouse_categories AS category
                WHERE category.company_id = candidate.company_id
                  AND lower(category.name) = lower('Tránsito interno')
                  AND category.deleted_at IS NULL
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO warehouses (
                id, company_id, branch_id, warehouse_category_id, name, code,
                warehouse_type, is_central, is_transit, operational_status,
                capacity_profile, capacity_enforcement_mode, storage_eligible,
                created_at, updated_at, is_active
            )
            SELECT gen_random_uuid(), central.company_id, headquarters.id,
                   category.id, 'Tránsito de vehículos',
                   'TRN-' || upper(substr(replace(central.company_id::text, '-', ''), 1, 8)),
                   'transit', false, true, 'active', 'transit', 'disabled', false,
                   now(), now(), true
            FROM warehouses AS central
            JOIN branches AS headquarters
              ON headquarters.id = central.branch_id
             AND headquarters.company_id = central.company_id
            JOIN warehouse_categories AS category
              ON category.company_id = central.company_id
             AND lower(category.name) = lower('Tránsito interno')
             AND category.deleted_at IS NULL
            WHERE central.is_central IS TRUE
              AND central.is_active IS TRUE
              AND central.operational_status = 'active'
              AND central.deleted_at IS NULL
              AND headquarters.is_headquarters IS TRUE
              AND headquarters.is_active IS TRUE
              AND headquarters.operational_status = 'active'
              AND headquarters.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM warehouses AS transit
                  WHERE transit.company_id = central.company_id
                    AND transit.is_transit IS TRUE
                    AND transit.deleted_at IS NULL
              )
            """
        )
    )
    op.create_index(
        "uq_warehouses_company_transit",
        "warehouses",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("is_transit IS TRUE AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    has_operational_data = bind.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM inventory_transfers) "
            "OR EXISTS (SELECT 1 FROM inventory_vehicles) "
            "OR EXISTS (SELECT 1 FROM locations WHERE location_type = 'vehicle')"
        )
    )
    if has_operational_data:
        raise RuntimeError(
            "No se puede revertir 0086 después de crear traslados o vehículos. "
            "Restaure una copia de seguridad validada si realmente debe revertirla."
        )

    op.drop_index("uq_warehouses_company_transit", table_name="warehouses")
    op.drop_index("uq_inventory_transfer_incidents_one_open", table_name="inventory_transfer_incidents")
    op.drop_index("ix_inventory_transfer_receipts_transfer", table_name="inventory_transfer_receipts")
    op.drop_table("inventory_transfer_incidents")
    op.drop_table("inventory_transfer_receipts")
    op.drop_constraint(
        "fk_inventory_transfers_dispatch_command", "inventory_transfers", type_="foreignkey"
    )
    op.drop_index("ix_inventory_transfer_commands_transfer", table_name="inventory_transfer_commands")
    op.drop_table("inventory_transfer_commands")
    op.drop_index(
        "ix_transfer_demand_allocations_request_detail", table_name="inventory_transfer_demand_allocations"
    )
    op.drop_table("inventory_transfer_demand_allocations")
    op.drop_index("ix_inventory_transfer_details_transit_hu", table_name="inventory_transfer_details")
    op.drop_index("ix_inventory_transfer_details_company_transfer", table_name="inventory_transfer_details")
    op.drop_table("inventory_transfer_details")
    op.drop_index("ix_inventory_transfers_destination", table_name="inventory_transfers")
    op.drop_index("ix_inventory_transfers_company_status", table_name="inventory_transfers")
    op.drop_table("inventory_transfers")
    op.drop_index("ix_inventory_vehicles_company_status", table_name="inventory_vehicles")
    op.drop_table("inventory_vehicles")
    op.execute(sa.text("DELETE FROM warehouses WHERE is_transit IS TRUE"))
    op.execute(
        sa.text(
            "DELETE FROM warehouse_categories AS category "
            "WHERE category.name = 'Tránsito interno' AND NOT EXISTS ("
            "SELECT 1 FROM warehouses WHERE warehouse_category_id = category.id)"
        )
    )
    op.drop_constraint("ck_warehouses_central_not_transit", "warehouses", type_="check")
    op.drop_column("warehouses", "is_transit")
    op.drop_constraint("ck_locations_type", "locations", type_="check")
    op.create_check_constraint(
        "ck_locations_type",
        "locations",
        "location_type IN ('standard','bulk','receiving','reserve','picking','staging',"
        "'quality','packing','shipping','returns','virtual')",
    )
    op.drop_constraint("uq_warehouses_company_identity", "warehouses", type_="unique")

