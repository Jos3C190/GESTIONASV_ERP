"""Authorized inventory adjustments, evidence, and transfer loss accounting."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0087"
down_revision = "0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_inventory_transfer_incidents_transfer_identity",
        "inventory_transfer_incidents",
        ["company_id", "transfer_id", "id"],
    )
    op.add_column(
        "inventory_transfer_details",
        sa.Column(
            "quantity_adjusted_out",
            sa.Numeric(18, 6),
            nullable=False,
            server_default="0",
        ),
    )
    op.drop_constraint("ck_inventory_transfer_details_quantities", "inventory_transfer_details", type_="check")
    op.create_check_constraint(
        "ck_inventory_transfer_details_quantities",
        "inventory_transfer_details",
        "quantity_planned > 0 AND quantity_dispatched >= 0 AND quantity_received >= 0 "
        "AND quantity_returned >= 0 AND quantity_adjusted_out >= 0 "
        "AND quantity_received + quantity_returned + quantity_adjusted_out <= quantity_dispatched",
    )
    op.add_column(
        "inventory_transfer_demand_allocations",
        sa.Column(
            "quantity_adjusted_out",
            sa.Numeric(18, 6),
            nullable=False,
            server_default="0",
        ),
    )
    op.drop_constraint(
        "ck_transfer_demand_allocations_quantities",
        "inventory_transfer_demand_allocations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_transfer_demand_allocations_quantities",
        "inventory_transfer_demand_allocations",
        "allocated_quantity > 0 AND quantity_dispatched >= 0 AND quantity_received >= 0 "
        "AND quantity_adjusted_out >= 0 AND quantity_received + quantity_adjusted_out <= quantity_dispatched "
        "AND quantity_dispatched <= allocated_quantity",
    )
    op.drop_constraint("ck_inventory_transfers_status", "inventory_transfers", type_="check")
    op.create_check_constraint(
        "ck_inventory_transfers_status",
        "inventory_transfers",
        "status IN ('preparation','in_transit','received','closed_with_adjustment','incident','cancelled')",
    )
    op.drop_constraint("ck_inventory_transfer_commands_action", "inventory_transfer_commands", type_="check")
    op.create_check_constraint(
        "ck_inventory_transfer_commands_action",
        "inventory_transfer_commands",
        "action IN ('create','update','cancel','dispatch','receive','incident','resolve','resolve_adjustment','return')",
    )

    op.execute("""
        CREATE TABLE inventory_adjustments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
            code varchar(40) NOT NULL,
            warehouse_id uuid NOT NULL,
            operational_date date NOT NULL,
            accounting_date date NOT NULL,
            reason text NOT NULL,
            document_reference varchar(240) NOT NULL,
            notes text,
            status varchar(16) NOT NULL DEFAULT 'draft',
            version integer NOT NULL DEFAULT 1,
            approved_version integer,
            correction_of_id uuid,
            transfer_id uuid,
            transfer_incident_id uuid,
            created_by_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            approved_by_id uuid,
            applied_by_id uuid,
            cancelled_by_id uuid,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            approved_at timestamptz,
            applied_at timestamptz,
            cancelled_at timestamptz,
            cancellation_reason text,
            approval_revocation_reason text,
            apply_idempotency_key varchar(120),
            apply_fingerprint varchar(64),
            applied_movements jsonb,
            create_idempotency_key varchar(120),
            create_fingerprint varchar(64),
            CONSTRAINT uq_inventory_adjustments_company_id UNIQUE(company_id,id),
            CONSTRAINT uq_inventory_adjustments_company_code UNIQUE(company_id,code),
            CONSTRAINT uq_inventory_adjustments_apply_key UNIQUE(company_id,apply_idempotency_key),
            CONSTRAINT fk_inventory_adjustments_warehouse_company FOREIGN KEY(company_id,warehouse_id)
                REFERENCES warehouses(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustments_correction_company FOREIGN KEY(company_id,correction_of_id)
                REFERENCES inventory_adjustments(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustments_transfer_company FOREIGN KEY(company_id,transfer_id)
                REFERENCES inventory_transfers(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustments_incident_transfer_company
                FOREIGN KEY(company_id,transfer_id,transfer_incident_id)
                REFERENCES inventory_transfer_incidents(company_id,transfer_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustments_approver_company FOREIGN KEY(approved_by_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustments_applier_company FOREIGN KEY(applied_by_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustments_canceller_company FOREIGN KEY(cancelled_by_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
            CONSTRAINT ck_inventory_adjustments_status CHECK(status IN ('draft','approved','applied','cancelled')),
            CONSTRAINT ck_inventory_adjustments_version CHECK(version >= 1),
            CONSTRAINT ck_inventory_adjustments_lifecycle CHECK(
                (status='draft' AND approved_at IS NULL AND applied_at IS NULL) OR
                (status='approved' AND approved_at IS NOT NULL AND applied_at IS NULL AND approved_version=version) OR
                (status='applied' AND approved_at IS NOT NULL AND applied_at IS NOT NULL AND approved_version=version) OR
                (status='cancelled' AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL)
            ),
            CONSTRAINT ck_inventory_adjustments_transfer_context CHECK(
                (transfer_id IS NULL AND transfer_incident_id IS NULL) OR
                (transfer_id IS NOT NULL AND transfer_incident_id IS NOT NULL)
            )
        )
    """)
    op.create_index("ix_inventory_adjustments_company_status", "inventory_adjustments", ["company_id", "status", "created_at"])
    op.create_index(
        "uq_inventory_adjustments_create_key",
        "inventory_adjustments",
        ["company_id", "create_idempotency_key"],
        unique=True,
        postgresql_where=sa.text("create_idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "uq_inventory_adjustments_active_correction",
        "inventory_adjustments",
        ["company_id", "correction_of_id"],
        unique=True,
        postgresql_where=sa.text("correction_of_id IS NOT NULL AND status <> 'cancelled'"),
    )
    op.execute("""
        CREATE TABLE inventory_adjustment_details (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            adjustment_id uuid NOT NULL,
            line_number integer NOT NULL,
            warehouse_id uuid NOT NULL,
            inventory_item_id uuid NOT NULL,
            location_id uuid NOT NULL,
            stock_status varchar(20) NOT NULL,
            direction varchar(12) NOT NULL,
            quantity_base numeric(18,6) NOT NULL,
            inventory_lot_detail_id uuid,
            handling_unit_id uuid,
            packaging_definition_id uuid,
            documented_unit_cost numeric(24,6),
            documented_total_cost numeric(24,6),
            actual_gross_weight_kg numeric(18,6),
            actual_volume_m3 numeric(18,6),
            transfer_detail_id uuid,
            movement_id uuid,
            movement_line_id uuid,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_inventory_adjustment_details_header_company FOREIGN KEY(company_id,adjustment_id)
                REFERENCES inventory_adjustments(company_id,id) ON DELETE CASCADE,
            CONSTRAINT fk_inventory_adjustment_details_warehouse_company FOREIGN KEY(company_id,warehouse_id)
                REFERENCES warehouses(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustment_details_item_company FOREIGN KEY(company_id,inventory_item_id)
                REFERENCES inventory_items(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustment_details_location_warehouse FOREIGN KEY(location_id,warehouse_id)
                REFERENCES locations(id,warehouse_id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustment_details_lot_company FOREIGN KEY(company_id,inventory_lot_detail_id)
                REFERENCES inventory_lot_details(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustment_details_handling_unit FOREIGN KEY(company_id,inventory_item_id,handling_unit_id)
                REFERENCES inventory_handling_units(company_id,inventory_item_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustment_details_packaging FOREIGN KEY(company_id,inventory_item_id,packaging_definition_id)
                REFERENCES inventory_packaging_definitions(company_id,inventory_item_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustment_details_transfer_detail FOREIGN KEY(company_id,transfer_detail_id)
                REFERENCES inventory_transfer_details(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustment_details_movement FOREIGN KEY(company_id,movement_id)
                REFERENCES inventory_movements(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustment_details_movement_line FOREIGN KEY(company_id,movement_line_id)
                REFERENCES inventory_movement_lines(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT uq_inventory_adjustment_line_number UNIQUE(adjustment_id,line_number),
            CONSTRAINT uq_inventory_adjustment_details_company_id UNIQUE(company_id,id),
            CONSTRAINT ck_inventory_adjustment_details_positive CHECK(line_number > 0 AND quantity_base > 0),
            CONSTRAINT ck_inventory_adjustment_details_direction CHECK(direction IN ('increase','decrease')),
            CONSTRAINT ck_inventory_adjustment_details_stock_status CHECK(stock_status IN ('available','quarantine','damaged','in_transit')),
            CONSTRAINT ck_inventory_adjustment_details_direction_fields CHECK(
                (direction='increase' AND stock_status='quarantine' AND handling_unit_id IS NULL AND transfer_detail_id IS NULL
                    AND (documented_unit_cost IS NULL OR documented_unit_cost >= 0)
                    AND (documented_total_cost IS NULL OR documented_total_cost >= 0)
                    AND (actual_gross_weight_kg IS NULL OR actual_gross_weight_kg > 0)
                    AND (actual_volume_m3 IS NULL OR actual_volume_m3 > 0)) OR
                (direction='decrease' AND handling_unit_id IS NOT NULL AND documented_unit_cost IS NULL AND documented_total_cost IS NULL
                    AND actual_gross_weight_kg IS NULL AND actual_volume_m3 IS NULL
                    AND ((stock_status='in_transit' AND transfer_detail_id IS NOT NULL) OR
                         (stock_status <> 'in_transit' AND transfer_detail_id IS NULL)))
            )
        )
    """)
    op.create_index("ix_inventory_adjustment_details_header", "inventory_adjustment_details", ["company_id", "adjustment_id", "line_number"])
    op.execute("""
        CREATE TABLE inventory_adjustment_documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            adjustment_id uuid NOT NULL,
            document_id uuid NOT NULL,
            checksum_sha256 varchar(64) NOT NULL,
            original_filename varchar(255) NOT NULL,
            linked_by_id uuid NOT NULL,
            linked_at timestamptz NOT NULL,
            upload_completed_at timestamptz,
            detached_by_id uuid,
            detached_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_inventory_adjustment_documents_adjustment FOREIGN KEY(company_id,adjustment_id)
                REFERENCES inventory_adjustments(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustment_documents_asset_company FOREIGN KEY(document_id,company_id)
                REFERENCES document_assets(id,company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustment_documents_linker_company FOREIGN KEY(linked_by_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
            CONSTRAINT uq_inventory_adjustment_document UNIQUE(company_id,adjustment_id,document_id),
            CONSTRAINT ck_inventory_adjustment_documents_detached_actor CHECK(detached_at IS NULL OR detached_by_id IS NOT NULL)
        )
    """)
    op.create_index("ix_inventory_adjustment_documents_active", "inventory_adjustment_documents", ["company_id", "adjustment_id", "detached_at"])
    op.execute("""
        CREATE TABLE inventory_adjustment_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            adjustment_id uuid NOT NULL,
            action varchar(32) NOT NULL,
            actor_id uuid NOT NULL,
            occurred_at timestamptz NOT NULL,
            reason text,
            version integer NOT NULL,
            details jsonb NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT fk_inventory_adjustment_events_adjustment FOREIGN KEY(company_id,adjustment_id)
                REFERENCES inventory_adjustments(company_id,id) ON DELETE RESTRICT,
            CONSTRAINT fk_inventory_adjustment_events_actor_company FOREIGN KEY(actor_id,company_id)
                REFERENCES user_companies(user_id,company_id) ON DELETE RESTRICT,
            CONSTRAINT ck_inventory_adjustment_events_version CHECK(version >= 1)
        )
    """)
    op.create_index("ix_inventory_adjustment_events_adjustment", "inventory_adjustment_events", ["company_id", "adjustment_id", "occurred_at"])
    op.execute("""
        CREATE FUNCTION reject_applied_inventory_adjustment_header_mutation() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.status = 'applied' THEN
                    RAISE EXCEPTION 'applied inventory adjustments are immutable';
                END IF;
                RETURN OLD;
            END IF;
            IF OLD.status = 'applied' THEN
                RAISE EXCEPTION 'applied inventory adjustments are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE FUNCTION reject_applied_inventory_adjustment_detail_mutation() RETURNS trigger AS $$
        DECLARE adjustment_status varchar(16);
        BEGIN
            SELECT status INTO adjustment_status
            FROM inventory_adjustments
            WHERE company_id = OLD.company_id AND id = OLD.adjustment_id;
            IF adjustment_status = 'applied' THEN
                RAISE EXCEPTION 'details of applied inventory adjustments are immutable';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE FUNCTION reject_inventory_adjustment_event_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'inventory adjustment events are append only';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_inventory_adjustments_immutable
            BEFORE UPDATE OR DELETE ON inventory_adjustments
            FOR EACH ROW EXECUTE FUNCTION reject_applied_inventory_adjustment_header_mutation();
        CREATE TRIGGER trg_inventory_adjustment_details_immutable
            BEFORE UPDATE OR DELETE ON inventory_adjustment_details
            FOR EACH ROW EXECUTE FUNCTION reject_applied_inventory_adjustment_detail_mutation();
        CREATE TRIGGER trg_inventory_adjustment_events_append_only
            BEFORE UPDATE OR DELETE ON inventory_adjustment_events
            FOR EACH ROW EXECUTE FUNCTION reject_inventory_adjustment_event_mutation();
        CREATE FUNCTION protect_linked_adjustment_document_asset() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF EXISTS (
                    SELECT 1 FROM inventory_adjustment_documents d
                    JOIN inventory_adjustments a ON a.company_id=d.company_id AND a.id=d.adjustment_id
                    WHERE d.document_id=OLD.id AND d.company_id=OLD.company_id AND d.detached_at IS NULL
                        AND a.status IN ('approved','applied')
                ) THEN
                    RAISE EXCEPTION 'document supports an approved or applied inventory adjustment';
                END IF;
                RETURN OLD;
            END IF;
            IF EXISTS (
                SELECT 1 FROM inventory_adjustment_documents d
                JOIN inventory_adjustments a ON a.company_id=d.company_id AND a.id=d.adjustment_id
                WHERE d.document_id=OLD.id AND d.company_id=OLD.company_id AND d.detached_at IS NULL
                    AND a.status IN ('approved','applied')
            ) AND (OLD.status IS DISTINCT FROM NEW.status OR
                   OLD.checksum_sha256 IS DISTINCT FROM NEW.checksum_sha256 OR
                   OLD.company_id IS DISTINCT FROM NEW.company_id OR
                   OLD.deleted_at IS DISTINCT FROM NEW.deleted_at) THEN
                RAISE EXCEPTION 'document supports an approved or applied inventory adjustment';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_inventory_adjustment_document_asset_guard
            BEFORE UPDATE OR DELETE ON document_assets
            FOR EACH ROW EXECUTE FUNCTION protect_linked_adjustment_document_asset();
    """)
    op.execute("""
        INSERT INTO permissions(id,code,description,module,created_at)
        VALUES
          (gen_random_uuid(),'inventory:adjust','Crear y administrar ajustes de inventario','inventory',now()),
          (gen_random_uuid(),'inventory:adjust_approve','Aprobar y aplicar ajustes de inventario','inventory',now())
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions(role_id,permission_id,created_at)
        SELECT r.id,p.id,now() FROM roles r CROSS JOIN permissions p
        WHERE r.name='SUPER_ADMIN' AND r.is_system IS TRUE AND r.company_id IS NULL
          AND r.deleted_at IS NULL AND p.deleted_at IS NULL
          AND p.code IN ('inventory:adjust','inventory:adjust_approve')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_inventory_adjustment_document_asset_guard ON document_assets")
    op.execute("DROP FUNCTION IF EXISTS protect_linked_adjustment_document_asset()")
    op.execute("DROP TRIGGER IF EXISTS trg_inventory_adjustment_events_append_only ON inventory_adjustment_events")
    op.execute("DROP TRIGGER IF EXISTS trg_inventory_adjustment_details_immutable ON inventory_adjustment_details")
    op.execute("DROP TRIGGER IF EXISTS trg_inventory_adjustments_immutable ON inventory_adjustments")
    op.execute("DROP FUNCTION IF EXISTS reject_inventory_adjustment_event_mutation()")
    op.execute("DROP FUNCTION IF EXISTS reject_applied_inventory_adjustment_detail_mutation()")
    op.execute("DROP FUNCTION IF EXISTS reject_applied_inventory_adjustment_header_mutation()")
    op.drop_table("inventory_adjustment_events")
    op.drop_table("inventory_adjustment_documents")
    op.drop_table("inventory_adjustment_details")
    op.drop_table("inventory_adjustments")
    op.drop_constraint("ck_inventory_transfer_commands_action", "inventory_transfer_commands", type_="check")
    op.create_check_constraint("ck_inventory_transfer_commands_action", "inventory_transfer_commands", "action IN ('create','update','cancel','dispatch','receive','incident','resolve','return')")
    op.drop_constraint("ck_inventory_transfers_status", "inventory_transfers", type_="check")
    op.create_check_constraint("ck_inventory_transfers_status", "inventory_transfers", "status IN ('preparation','in_transit','received','incident','cancelled')")
    op.drop_constraint("ck_transfer_demand_allocations_quantities", "inventory_transfer_demand_allocations", type_="check")
    op.create_check_constraint("ck_transfer_demand_allocations_quantities", "inventory_transfer_demand_allocations", "allocated_quantity > 0 AND quantity_dispatched >= 0 AND quantity_received >= 0 AND quantity_received <= quantity_dispatched AND quantity_dispatched <= allocated_quantity")
    op.drop_column("inventory_transfer_demand_allocations", "quantity_adjusted_out")
    op.drop_constraint("ck_inventory_transfer_details_quantities", "inventory_transfer_details", type_="check")
    op.create_check_constraint("ck_inventory_transfer_details_quantities", "inventory_transfer_details", "quantity_planned > 0 AND quantity_dispatched >= 0 AND quantity_received >= 0 AND quantity_returned >= 0 AND quantity_received + quantity_returned <= quantity_dispatched")
    op.drop_column("inventory_transfer_details", "quantity_adjusted_out")
    op.drop_constraint("uq_inventory_transfer_incidents_transfer_identity", "inventory_transfer_incidents", type_="unique")
