"""Company fleet settings, temporary assignments, branch loans and vehicle reservations.

Revision ID: 0111
Revises: 0110
"""

from alembic import op
from sqlalchemy import text

revision = "0111"
down_revision = "0110"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("fleet:settings", "Configurar las reglas de la flota"),
    ("fleet:loans", "Prestar vehículos entre sucursales"),
    ("fleet:reservations", "Reservar vehículos"),
)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fleet_settings (
            company_id uuid PRIMARY KEY REFERENCES companies (id) ON DELETE CASCADE,
            block_overdue_maintenance boolean NOT NULL DEFAULT false,
            require_inspection boolean NOT NULL DEFAULT false,
            inspection_valid_hours integer NOT NULL DEFAULT 24,
            document_warning_days integer NOT NULL DEFAULT 30,
            maintenance_warning_km integer NOT NULL DEFAULT 500,
            maintenance_warning_days integer NOT NULL DEFAULT 7,
            updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_fleet_settings_inspection_hours
                CHECK (inspection_valid_hours BETWEEN 1 AND 720),
            CONSTRAINT ck_fleet_settings_document_days
                CHECK (document_warning_days BETWEEN 0 AND 365),
            CONSTRAINT ck_fleet_settings_maintenance_km
                CHECK (maintenance_warning_km BETWEEN 0 AND 100000),
            CONSTRAINT ck_fleet_settings_maintenance_days
                CHECK (maintenance_warning_days BETWEEN 0 AND 365)
        )
    """)
    op.execute("""
        ALTER TABLE vehicle_driver_assignments
            ADD COLUMN expected_end_on date,
            ADD COLUMN covers_driver_id uuid,
            ADD CONSTRAINT fk_vehicle_driver_assignments_covers
                FOREIGN KEY (company_id, covers_driver_id)
                REFERENCES drivers (company_id, id) ON DELETE RESTRICT
    """)
    op.execute("""
        CREATE TABLE fleet_vehicle_loans (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            vehicle_id uuid NOT NULL,
            from_branch_id uuid NOT NULL,
            to_branch_id uuid NOT NULL,
            starts_on date NOT NULL,
            expected_return_on date NOT NULL,
            reason varchar(500) NOT NULL,
            returned_at timestamptz,
            returned_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_fleet_loans_vehicle FOREIGN KEY (company_id, vehicle_id)
                REFERENCES fleet_vehicles (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_fleet_loans_from FOREIGN KEY (from_branch_id, company_id)
                REFERENCES branches (id, company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_fleet_loans_to FOREIGN KEY (to_branch_id, company_id)
                REFERENCES branches (id, company_id) ON DELETE RESTRICT,
            CONSTRAINT ck_fleet_loans_branches CHECK (from_branch_id <> to_branch_id),
            CONSTRAINT ck_fleet_loans_dates CHECK (expected_return_on >= starts_on)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_fleet_loans_open_vehicle ON fleet_vehicle_loans (vehicle_id)
        WHERE returned_at IS NULL
    """)
    op.execute("""
        CREATE INDEX ix_fleet_loans_open_to_branch ON fleet_vehicle_loans (to_branch_id)
        WHERE returned_at IS NULL
    """)
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("""
        CREATE TABLE fleet_reservations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            vehicle_id uuid NOT NULL,
            starts_at timestamptz NOT NULL,
            ends_at timestamptz NOT NULL,
            reason varchar(300) NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'active',
            reserved_by uuid REFERENCES users (id) ON DELETE SET NULL,
            cancelled_by uuid REFERENCES users (id) ON DELETE SET NULL,
            cancel_reason varchar(500),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_fleet_reservations_vehicle FOREIGN KEY (company_id, vehicle_id)
                REFERENCES fleet_vehicles (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_fleet_reservations_status CHECK (status IN ('active', 'cancelled')),
            CONSTRAINT ck_fleet_reservations_dates CHECK (ends_at > starts_at),
            CONSTRAINT ex_fleet_reservations_overlap EXCLUDE USING gist (
                vehicle_id WITH =, tstzrange(starts_at, ends_at) WITH &&
            ) WHERE (status = 'active')
        )
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
    blocked = bind.execute(
        text("""
            SELECT (SELECT count(*) FROM fleet_settings)
                 + (SELECT count(*) FROM fleet_vehicle_loans)
                 + (SELECT count(*) FROM fleet_reservations)
                 + (SELECT count(*) FROM vehicle_driver_assignments
                    WHERE expected_end_on IS NOT NULL OR covers_driver_id IS NOT NULL)
        """)
    ).scalar()
    if blocked:
        raise RuntimeError(f"Hay {blocked} registros de operación diaria que se perderían.")
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE FROM role_permissions WHERE permission_id IN
              (SELECT id FROM permissions WHERE code = '{code}');
            DELETE FROM permissions WHERE code = '{code}';
        """)
    op.execute("DROP TABLE fleet_reservations")
    op.execute("DROP TABLE fleet_vehicle_loans")
    op.execute("""
        ALTER TABLE vehicle_driver_assignments
            DROP CONSTRAINT fk_vehicle_driver_assignments_covers,
            DROP COLUMN covers_driver_id,
            DROP COLUMN expected_end_on
    """)
    op.execute("DROP TABLE fleet_settings")
