"""Void odometer readings and fuel logs with a reason; meter replacement; tank size.

Revision ID: 0108
Revises: 0107
"""

from alembic import op
from sqlalchemy import text

revision = "0108"
down_revision = "0107"
branch_labels = None
depends_on = None

_PERMISSION = "fleet:correct_records"
_VOID = """
    ADD COLUMN voided_at timestamptz,
    ADD COLUMN voided_by uuid REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN void_reason varchar(500)
"""


def upgrade() -> None:
    op.execute(f"ALTER TABLE fleet_odometer_readings {_VOID}")
    op.execute(f"ALTER TABLE fleet_fuel_logs {_VOID}")
    op.execute(
        "ALTER TABLE fleet_odometer_readings DROP CONSTRAINT ck_fleet_odometer_readings_source"
    )
    op.execute("ALTER TABLE fleet_odometer_readings ALTER COLUMN source TYPE varchar(24)")
    op.execute("""
        ALTER TABLE fleet_odometer_readings ADD CONSTRAINT ck_fleet_odometer_readings_source
        CHECK (source IN ('manual', 'fuel', 'maintenance', 'gps', 'meter_replacement'))
    """)
    op.execute("ALTER TABLE fleet_vehicles ADD COLUMN tank_liters numeric(8, 2)")
    op.execute("""
        ALTER TABLE fleet_vehicles ADD CONSTRAINT ck_fleet_vehicles_tank
        CHECK (tank_liters IS NULL OR tank_liters > 0)
    """)
    op.execute(f"""
        INSERT INTO permissions (id, code, description, module, created_at)
        VALUES (gen_random_uuid(), '{_PERMISSION}',
                'Corregir lecturas de uso y cargas de combustible', 'fleet', now())
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
            SELECT (SELECT count(*) FROM fleet_odometer_readings
                    WHERE voided_at IS NOT NULL OR source = 'meter_replacement')
                 + (SELECT count(*) FROM fleet_fuel_logs WHERE voided_at IS NOT NULL)
                 + (SELECT count(*) FROM fleet_maintenance_plans WHERE last_service_km < 0)
        """)
    ).scalar()
    if blocked:
        raise RuntimeError(f"Hay {blocked} correcciones que se perderían al revertir.")
    op.execute(f"""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code = '{_PERMISSION}');
        DELETE FROM permissions WHERE code = '{_PERMISSION}';
    """)
    op.execute("ALTER TABLE fleet_vehicles DROP CONSTRAINT ck_fleet_vehicles_tank")
    op.execute("ALTER TABLE fleet_vehicles DROP COLUMN tank_liters")
    op.execute(
        "ALTER TABLE fleet_odometer_readings DROP CONSTRAINT ck_fleet_odometer_readings_source"
    )
    op.execute("""
        ALTER TABLE fleet_odometer_readings ADD CONSTRAINT ck_fleet_odometer_readings_source
        CHECK (source IN ('manual', 'fuel', 'maintenance', 'gps'))
    """)
    op.execute("ALTER TABLE fleet_odometer_readings ALTER COLUMN source TYPE varchar(16)")
    for table in ("fleet_odometer_readings", "fleet_fuel_logs"):
        op.execute(
            f"ALTER TABLE {table} DROP COLUMN void_reason, DROP COLUMN voided_by, "
            "DROP COLUMN voided_at"
        )
