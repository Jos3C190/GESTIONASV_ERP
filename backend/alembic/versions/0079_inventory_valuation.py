"""Company/product moving average, approved opening and immutable cost events."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0079"
down_revision = "0078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("retaceos", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("retaceos", sa.Column("applied_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_check_constraint(
        "ck_retaceos_application",
        "retaceos",
        "(applied_at IS NULL AND applied_by IS NULL) OR (applied_at IS NOT NULL AND applied_by IS NOT NULL AND status IN ('verified', 'closed'))",
    )
    op.create_unique_constraint(
        "uq_inventory_movement_lines_company_id", "inventory_movement_lines", ["company_id", "id"]
    )
    op.execute(
        "CREATE TABLE inventory_valuation_settings (\n\tcompany_id UUID NOT NULL, \n\tcurrency VARCHAR(3) NOT NULL, \n\topened_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\topened_by UUID NOT NULL, \n\topening_reference VARCHAR(500) NOT NULL, \n\topening_fingerprint VARCHAR(64) NOT NULL, \n\tphysical_snapshot JSONB NOT NULL, \n\tPRIMARY KEY (company_id), \n\tFOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(currency) REFERENCES currencies (code) ON DELETE RESTRICT\n)"
    )
    op.execute(
        "CREATE TABLE inventory_cost_averages (\n\tcompany_id UUID NOT NULL, \n\tinventory_item_id UUID NOT NULL, \n\tquantity_base NUMERIC(24, 6) NOT NULL, \n\tinventory_value NUMERIC(24, 6) NOT NULL, \n\taverage_unit_cost NUMERIC(24, 6) NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (company_id, inventory_item_id), \n\tFOREIGN KEY(company_id) REFERENCES inventory_valuation_settings (company_id) ON DELETE RESTRICT, \n\tFOREIGN KEY(company_id, inventory_item_id) REFERENCES inventory_items (company_id, id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_cost_average_nonnegative CHECK (quantity_base >= 0 AND inventory_value >= 0 AND average_unit_cost >= 0), \n\tCONSTRAINT ck_cost_average_zero_balance CHECK (quantity_base > 0 OR inventory_value = 0)\n)"
    )
    op.execute(
        "CREATE TABLE inventory_valuation_entries (\n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tinventory_item_id UUID NOT NULL, \n\tsequence INTEGER NOT NULL, \n\tkind VARCHAR(24) NOT NULL, \n\tquantity_base NUMERIC(24, 6) NOT NULL, \n\tsource_value NUMERIC(24, 6) NOT NULL, \n\toriginal_entry_id UUID, \n\tmovement_line_id UUID, \n\tpurchase_detail_id UUID, \n\tretaceo_id UUID, \n\tsource_reference VARCHAR(500) NOT NULL, \n\tidempotency_key VARCHAR(160) NOT NULL, \n\tfingerprint VARCHAR(64) NOT NULL, \n\toperational_date DATE NOT NULL, \n\taccounting_date DATE NOT NULL, \n\tposted_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tposted_by UUID NOT NULL, \n\tinventory_delta NUMERIC(24, 6) NOT NULL, \n\tbalance_quantity NUMERIC(24, 6) NOT NULL, \n\tbalance_value NUMERIC(24, 6) NOT NULL, \n\taverage_unit_cost NUMERIC(24, 6) NOT NULL, \n\tcost_breakdown JSONB NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_valuation_entry_company_id UNIQUE (company_id, id), \n\tCONSTRAINT uq_valuation_entry_sequence UNIQUE (company_id, sequence), \n\tCONSTRAINT uq_valuation_entry_key UNIQUE (company_id, idempotency_key), \n\tCONSTRAINT uq_valuation_movement_line UNIQUE (movement_line_id), \n\tFOREIGN KEY(company_id) REFERENCES inventory_valuation_settings (company_id) ON DELETE RESTRICT, \n\tFOREIGN KEY(company_id, inventory_item_id) REFERENCES inventory_items (company_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(company_id, original_entry_id) REFERENCES inventory_valuation_entries (company_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(company_id, movement_line_id) REFERENCES inventory_movement_lines (company_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(company_id, purchase_detail_id) REFERENCES purchase_details (company_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(company_id, retaceo_id) REFERENCES retaceos (company_id, id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_valuation_entry_kind CHECK (kind IN ('opening','receipt','issue','supplier_return','customer_return','adjustment_in','adjustment_out','cost_adjustment','supplier_credit')), \n\tCONSTRAINT ck_valuation_entry_nonnegative CHECK (quantity_base >= 0 AND balance_quantity >= 0 AND balance_value >= 0)\n)"
    )
    op.execute(
        "CREATE INDEX ix_valuation_item_sequence ON inventory_valuation_entries (company_id, inventory_item_id, sequence)"
    )
    op.execute(
        "CREATE TABLE inventory_retaceo_applications (\n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tcompany_id UUID NOT NULL, \n\tretaceo_id UUID NOT NULL, \n\tpurchase_id UUID NOT NULL, \n\tapplied_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tapplied_by UUID NOT NULL, \n\tsummary JSONB NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_retaceo_application_retaceo UNIQUE (company_id, retaceo_id), \n\tCONSTRAINT uq_retaceo_application_purchase UNIQUE (company_id, purchase_id), \n\tFOREIGN KEY(company_id, retaceo_id) REFERENCES retaceos (company_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(company_id, purchase_id) REFERENCES purchases (company_id, id) ON DELETE RESTRICT\n)"
    )
    op.execute("""
        CREATE FUNCTION guard_inventory_valuation_history() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Valuation history is immutable; append a documented adjustment';
        END;
        $$ LANGUAGE plpgsql;
    """)
    for table in (
        "inventory_valuation_entries",
        "inventory_retaceo_applications",
        "inventory_valuation_settings",
    ):
        op.execute(
            f"CREATE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION guard_inventory_valuation_history()"
        )
    op.execute("""
        INSERT INTO permissions (id, code, description, module, created_at)
        VALUES (gen_random_uuid(), 'inventory:valuation', 'Consultar y aprobar valoración de inventario', 'inventory', now())
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE
        AND r.company_id IS NULL AND r.deleted_at IS NULL
        AND p.deleted_at IS NULL AND p.code = 'inventory:valuation'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    # Financial history must be exported and reconciled before destructive rollback.
    raise RuntimeError("0079 contiene historial de valoración; requiere reversión documentada.")
