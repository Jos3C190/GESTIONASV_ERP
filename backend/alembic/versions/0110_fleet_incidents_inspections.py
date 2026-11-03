"""Incidents per vehicle, and pre-departure inspections whose critical failures stop dispatch.

Revision ID: 0110
Revises: 0109
"""

from alembic import op
from sqlalchemy import text

revision = "0110"
down_revision = "0109"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("fleet:incidents", "Registrar y dar seguimiento a incidentes de vehículos"),
    ("fleet:inspections", "Realizar inspecciones y resolver sus fallas"),
)
# name, critical
_DEFAULT_ITEMS = (
    ("Frenos", True),
    ("Dirección", True),
    ("Llantas", True),
    ("Luces y direccionales", True),
    ("Cinturones de seguridad", True),
    ("Niveles de aceite y refrigerante", False),
    ("Espejos y limpiaparabrisas", False),
    ("Documentos a bordo", False),
    ("Extintor y triángulos", False),
)


def _items_values() -> str:
    return ", ".join(
        f"(company, '{name}', {'true' if critical else 'false'}, {(index + 1) * 10})"
        for index, (name, critical) in enumerate(_DEFAULT_ITEMS)
    )


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fleet_incidents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            vehicle_id uuid NOT NULL,
            driver_id uuid,
            kind varchar(16) NOT NULL,
            severity varchar(16) NOT NULL,
            responsible varchar(16) NOT NULL DEFAULT 'unknown',
            status varchar(16) NOT NULL DEFAULT 'open',
            occurred_at timestamptz NOT NULL,
            location varchar(200),
            description text NOT NULL,
            cost numeric(12, 2),
            insurance_claim varchar(80),
            document_id uuid REFERENCES document_records (id) ON DELETE SET NULL,
            resolution varchar(1000),
            reported_by uuid REFERENCES users (id) ON DELETE SET NULL,
            closed_at timestamptz,
            closed_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_fleet_incidents_vehicle_company FOREIGN KEY (company_id, vehicle_id)
                REFERENCES fleet_vehicles (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_fleet_incidents_driver_company FOREIGN KEY (company_id, driver_id)
                REFERENCES drivers (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_fleet_incidents_kind
                CHECK (kind IN ('accident', 'theft', 'fine', 'damage', 'other')),
            CONSTRAINT ck_fleet_incidents_severity
                CHECK (severity IN ('minor', 'moderate', 'severe')),
            CONSTRAINT ck_fleet_incidents_responsible
                CHECK (responsible IN ('company', 'driver', 'third_party', 'unknown')),
            CONSTRAINT ck_fleet_incidents_status
                CHECK (status IN ('open', 'in_review', 'closed')),
            CONSTRAINT ck_fleet_incidents_cost CHECK (cost IS NULL OR cost >= 0),
            CONSTRAINT ck_fleet_incidents_closed
                CHECK (status <> 'closed' OR (closed_at IS NOT NULL AND resolution IS NOT NULL))
        )
    """)
    op.execute(
        "CREATE INDEX ix_fleet_incidents_vehicle ON fleet_incidents (vehicle_id, occurred_at)"
    )
    op.execute("CREATE INDEX ix_fleet_incidents_driver ON fleet_incidents (driver_id, occurred_at)")
    op.execute(
        "CREATE INDEX ix_fleet_incidents_company ON fleet_incidents (company_id, occurred_at)"
    )

    op.execute("""
        CREATE TABLE fleet_inspection_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE CASCADE,
            name varchar(120) NOT NULL,
            is_critical boolean NOT NULL DEFAULT false,
            is_active boolean NOT NULL DEFAULT true,
            sort_order integer NOT NULL DEFAULT 100,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_fleet_inspection_items_company_id UNIQUE (company_id, id)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_fleet_inspection_items_company_name
        ON fleet_inspection_items (company_id, lower(name))
    """)
    op.execute("""
        CREATE TABLE fleet_inspections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            vehicle_id uuid NOT NULL,
            driver_id uuid,
            inspected_at timestamptz NOT NULL,
            passed boolean NOT NULL,
            notes varchar(1000),
            inspected_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_fleet_inspections_company_id UNIQUE (company_id, id),
            CONSTRAINT fk_fleet_inspections_vehicle_company FOREIGN KEY (company_id, vehicle_id)
                REFERENCES fleet_vehicles (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_fleet_inspections_driver_company FOREIGN KEY (company_id, driver_id)
                REFERENCES drivers (company_id, id) ON DELETE RESTRICT
        )
    """)
    op.execute("""
        CREATE INDEX ix_fleet_inspections_vehicle ON fleet_inspections (vehicle_id, inspected_at)
    """)
    op.execute("""
        CREATE TABLE fleet_inspection_results (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            inspection_id uuid NOT NULL,
            vehicle_id uuid NOT NULL,
            item_id uuid NOT NULL,
            item_name varchar(120) NOT NULL,
            is_critical boolean NOT NULL,
            passed boolean NOT NULL,
            notes varchar(500),
            photo_url varchar(2048),
            resolved_at timestamptz,
            resolved_by uuid REFERENCES users (id) ON DELETE SET NULL,
            resolution varchar(500),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_fleet_inspection_results_inspection
                FOREIGN KEY (company_id, inspection_id)
                REFERENCES fleet_inspections (company_id, id) ON DELETE CASCADE,
            CONSTRAINT fk_fleet_inspection_results_item FOREIGN KEY (company_id, item_id)
                REFERENCES fleet_inspection_items (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_fleet_inspection_results_resolved
                CHECK (resolved_at IS NULL OR (NOT passed AND resolution IS NOT NULL))
        )
    """)
    op.execute("""
        CREATE INDEX ix_fleet_inspection_results_open_critical
        ON fleet_inspection_results (vehicle_id)
        WHERE is_critical AND NOT passed AND resolved_at IS NULL
    """)
    op.execute(f"""
        CREATE FUNCTION seed_fleet_inspection_items(company uuid) RETURNS void AS $$
        BEGIN
          INSERT INTO fleet_inspection_items (company_id, name, is_critical, sort_order)
          VALUES {_items_values()}
          ON CONFLICT DO NOTHING;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("SELECT seed_fleet_inspection_items(id) FROM companies")
    op.execute("""
        CREATE FUNCTION seed_fleet_inspection_items_for_company() RETURNS trigger AS $$
        BEGIN
          PERFORM seed_fleet_inspection_items(NEW.id);
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_companies_seed_fleet_inspection_items
        AFTER INSERT ON companies FOR EACH ROW
        EXECUTE FUNCTION seed_fleet_inspection_items_for_company()
    """)
    for code, description in _PERMISSIONS:
        op.execute(f"""
            INSERT INTO permissions (id, code, description, module, created_at)
            VALUES (gen_random_uuid(), '{code}', '{description}', 'fleet', now())
            ON CONFLICT DO NOTHING
        """)
        op.execute(f"""
            INSERT INTO role_permissions (role_id, permission_id, created_at)
            SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
            WHERE p.code = '{code}' AND p.deleted_at IS NULL AND r.deleted_at IS NULL
              AND r.name IN ('SUPER_ADMIN', 'ADMINISTRADOR DE OPERACIONES')
            ON CONFLICT DO NOTHING
        """)


def downgrade() -> None:
    bind = op.get_bind()
    defaults = ", ".join(f"'{name}'" for name, _ in _DEFAULT_ITEMS)
    blocked = bind.execute(
        text(f"""
            SELECT (SELECT count(*) FROM fleet_incidents)
                 + (SELECT count(*) FROM fleet_inspections)
                 + (SELECT count(*) FROM fleet_inspection_items WHERE name NOT IN ({defaults}))
        """)
    ).scalar()
    if blocked:
        raise RuntimeError(
            f"Hay {blocked} registros de incidentes e inspecciones que se perderían."
        )
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE FROM role_permissions WHERE permission_id IN
              (SELECT id FROM permissions WHERE code = '{code}');
            DELETE FROM permissions WHERE code = '{code}';
        """)
    op.execute("DROP TRIGGER trg_companies_seed_fleet_inspection_items ON companies")
    op.execute("DROP FUNCTION seed_fleet_inspection_items_for_company()")
    op.execute("DROP FUNCTION seed_fleet_inspection_items(uuid)")
    op.execute("DROP TABLE fleet_inspection_results")
    op.execute("DROP TABLE fleet_inspections")
    op.execute("DROP TABLE fleet_inspection_items")
    op.execute("DROP TABLE fleet_incidents")
