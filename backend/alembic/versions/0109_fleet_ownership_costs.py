"""Who owns each vehicle, other costs, and suppliers and invoices on fuel and service.

Revision ID: 0109
Revises: 0108
"""

from alembic import op
from sqlalchemy import text

revision = "0109"
down_revision = "0108"
branch_labels = None
depends_on = None

_PERMISSION = "fleet:costs"


def _supplier_fk(table: str, name: str) -> str:
    return f"""
        ALTER TABLE {table} ADD CONSTRAINT {name}
        FOREIGN KEY (company_id, supplier_id)
        REFERENCES suppliers (company_id, id_supplier) ON DELETE RESTRICT
    """


def upgrade() -> None:
    op.execute("""
        ALTER TABLE fleet_vehicles
            ADD COLUMN ownership varchar(16) NOT NULL DEFAULT 'owned',
            ADD COLUMN owner_supplier_id integer,
            ADD COLUMN contract_reference varchar(80),
            ADD COLUMN contract_ends_on date,
            ADD COLUMN monthly_fee numeric(12, 2)
    """)
    op.execute("""
        ALTER TABLE fleet_vehicles
            ADD CONSTRAINT ck_fleet_vehicles_ownership
                CHECK (ownership IN ('owned', 'leased', 'rented', 'third_party')),
            ADD CONSTRAINT ck_fleet_vehicles_owned_no_contract
                CHECK (ownership <> 'owned' OR (
                    owner_supplier_id IS NULL AND contract_reference IS NULL
                    AND contract_ends_on IS NULL AND monthly_fee IS NULL
                )),
            ADD CONSTRAINT ck_fleet_vehicles_monthly_fee
                CHECK (monthly_fee IS NULL OR monthly_fee >= 0),
            ADD CONSTRAINT fk_fleet_vehicles_owner_supplier
                FOREIGN KEY (company_id, owner_supplier_id)
                REFERENCES suppliers (company_id, id_supplier) ON DELETE RESTRICT
    """)
    op.execute("ALTER TABLE fleet_maintenance_orders ADD COLUMN supplier_id integer")
    op.execute(_supplier_fk("fleet_maintenance_orders", "fk_fleet_maintenance_orders_supplier"))
    op.execute("""
        ALTER TABLE fleet_maintenance_orders ADD COLUMN receipt_document_id uuid
        REFERENCES document_records (id) ON DELETE SET NULL
    """)
    op.execute("ALTER TABLE fleet_fuel_logs ADD COLUMN supplier_id integer")
    op.execute(_supplier_fk("fleet_fuel_logs", "fk_fleet_fuel_logs_supplier"))
    op.execute("""
        CREATE TABLE fleet_costs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            vehicle_id uuid NOT NULL,
            category varchar(16) NOT NULL,
            incurred_on date NOT NULL,
            amount numeric(12, 2) NOT NULL,
            description varchar(300),
            supplier_id integer,
            document_id uuid REFERENCES document_records (id) ON DELETE SET NULL,
            recorded_by uuid REFERENCES users (id) ON DELETE SET NULL,
            voided_at timestamptz,
            voided_by uuid REFERENCES users (id) ON DELETE SET NULL,
            void_reason varchar(500),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_fleet_costs_vehicle_company FOREIGN KEY (company_id, vehicle_id)
                REFERENCES fleet_vehicles (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_fleet_costs_supplier FOREIGN KEY (company_id, supplier_id)
                REFERENCES suppliers (company_id, id_supplier) ON DELETE RESTRICT,
            CONSTRAINT ck_fleet_costs_category
                CHECK (category IN ('insurance', 'tax', 'washing', 'fee', 'toll', 'other')),
            CONSTRAINT ck_fleet_costs_amount CHECK (amount > 0)
        )
    """)
    op.execute("CREATE INDEX ix_fleet_costs_vehicle_date ON fleet_costs (vehicle_id, incurred_on)")
    op.execute("CREATE INDEX ix_fleet_costs_company_date ON fleet_costs (company_id, incurred_on)")
    op.execute(f"""
        INSERT INTO permissions (id, code, description, module, created_at)
        VALUES (gen_random_uuid(), '{_PERMISSION}', 'Registrar y anular costos de vehículos',
                'fleet', now())
        ON CONFLICT DO NOTHING
    """)
    op.execute(f"""
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
        WHERE p.code = '{_PERMISSION}' AND p.deleted_at IS NULL AND r.deleted_at IS NULL
          AND r.name IN ('SUPER_ADMIN', 'ADMINISTRADOR DE OPERACIONES')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    bind = op.get_bind()
    blocked = bind.execute(
        text("""
            SELECT (SELECT count(*) FROM fleet_costs)
                 + (SELECT count(*) FROM fleet_vehicles WHERE ownership <> 'owned')
                 + (SELECT count(*) FROM fleet_maintenance_orders
                    WHERE supplier_id IS NOT NULL OR receipt_document_id IS NOT NULL)
                 + (SELECT count(*) FROM fleet_fuel_logs
                    WHERE supplier_id IS NOT NULL OR receipt_document_id IS NOT NULL)
        """)
    ).scalar()
    if blocked:
        raise RuntimeError(f"Hay {blocked} registros de propiedad y costos que se perderían.")
    op.execute(f"""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code = '{_PERMISSION}');
        DELETE FROM permissions WHERE code = '{_PERMISSION}';
    """)
    op.execute("DROP TABLE fleet_costs")
    op.execute("ALTER TABLE fleet_fuel_logs DROP COLUMN supplier_id")
    op.execute(
        "ALTER TABLE fleet_maintenance_orders DROP COLUMN receipt_document_id, "
        "DROP COLUMN supplier_id"
    )
    op.execute("""
        ALTER TABLE fleet_vehicles
            DROP CONSTRAINT fk_fleet_vehicles_owner_supplier,
            DROP CONSTRAINT ck_fleet_vehicles_monthly_fee,
            DROP CONSTRAINT ck_fleet_vehicles_owned_no_contract,
            DROP CONSTRAINT ck_fleet_vehicles_ownership,
            DROP COLUMN monthly_fee,
            DROP COLUMN contract_ends_on,
            DROP COLUMN contract_reference,
            DROP COLUMN owner_supplier_id,
            DROP COLUMN ownership
    """)
