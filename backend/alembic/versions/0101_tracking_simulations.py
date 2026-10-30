"""Tracking simulator sessions and the simulated flag on alerts and trails."""

from alembic import op

revision = "0101"
down_revision = "0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Una sesión maneja un GPS virtual en Traccar para un vehículo; el GPS real no se toca.
    op.execute("""
        CREATE TABLE tracking_simulations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          vehicle_id uuid NOT NULL,
          branch_id uuid NOT NULL,
          transfer_id uuid,
          traccar_device_id integer NOT NULL,
          device_unique_id varchar(64) NOT NULL,
          mode varchar(10) NOT NULL,
          state varchar(10) NOT NULL DEFAULT 'running',
          route jsonb NOT NULL DEFAULT '[]'::jsonb,
          route_length_m numeric(12,1) NOT NULL DEFAULT 0,
          progress_m numeric(12,1) NOT NULL DEFAULT 0,
          speed_kmh numeric(6,1) NOT NULL DEFAULT 40,
          current_speed_kmh numeric(6,1) NOT NULL DEFAULT 0,
          longitude numeric(9,6) NOT NULL,
          latitude numeric(9,6) NOT NULL,
          course numeric(5,1) NOT NULL DEFAULT 0,
          stop_until timestamptz,
          signal_lost_until timestamptz,
          last_report_at timestamptz,
          last_activity_at timestamptz NOT NULL DEFAULT now(),
          started_by uuid REFERENCES users(id) ON DELETE SET NULL,
          started_at timestamptz NOT NULL DEFAULT now(),
          ended_by uuid REFERENCES users(id) ON DELETE SET NULL,
          ended_at timestamptz,
          end_reason text,
          CONSTRAINT fk_tracking_simulations_vehicle
            FOREIGN KEY (company_id, vehicle_id)
            REFERENCES fleet_vehicles (company_id, id) ON DELETE CASCADE,
          CONSTRAINT fk_tracking_simulations_branch
            FOREIGN KEY (branch_id, company_id)
            REFERENCES branches (id, company_id) ON DELETE RESTRICT,
          CONSTRAINT fk_tracking_simulations_transfer
            FOREIGN KEY (company_id, transfer_id)
            REFERENCES inventory_transfers (company_id, id) ON DELETE CASCADE,
          CONSTRAINT ck_tracking_simulations_mode CHECK (mode IN ('route','joystick')),
          CONSTRAINT ck_tracking_simulations_state
            CHECK (state IN ('running','paused','arrived','ended')),
          CONSTRAINT ck_tracking_simulations_speed CHECK (speed_kmh BETWEEN 1 AND 300),
          CONSTRAINT ck_tracking_simulations_progress
            CHECK (progress_m >= 0 AND progress_m <= route_length_m + 1),
          CONSTRAINT ck_tracking_simulations_ended
            CHECK ((state = 'ended') = (ended_at IS NOT NULL))
        );
        CREATE UNIQUE INDEX uq_tracking_simulations_open_vehicle
          ON tracking_simulations (vehicle_id) WHERE state <> 'ended';
        CREATE INDEX ix_tracking_simulations_company_state
          ON tracking_simulations (company_id, state);
        CREATE INDEX ix_tracking_simulations_device
          ON tracking_simulations (traccar_device_id, ended_at);
    """)
    # Lo generado con datos simulados queda marcado y nunca se confunde con la operación real.
    op.execute("""
        ALTER TABLE tracking_alerts ADD COLUMN simulated boolean NOT NULL DEFAULT false;
        ALTER TABLE inventory_transfer_tracks ADD COLUMN simulated boolean NOT NULL DEFAULT false;
    """)
    op.execute("""
        INSERT INTO permissions (id, code, description, module, created_at)
        VALUES (gen_random_uuid(), 'tracking:simulate',
                'Usar las herramientas de simulación del seguimiento GPS', 'tracking', now())
        ON CONFLICT DO NOTHING;
        INSERT INTO role_permissions (role_id, permission_id, created_at)
        SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
        WHERE p.code = 'tracking:simulate' AND p.deleted_at IS NULL AND r.deleted_at IS NULL
          AND ((r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE AND r.company_id IS NULL)
               OR r.name = 'ADMINISTRADOR DE OPERACIONES')
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code = 'tracking:simulate');
        DELETE FROM permissions WHERE code = 'tracking:simulate';
        ALTER TABLE inventory_transfer_tracks DROP COLUMN simulated;
        ALTER TABLE tracking_alerts DROP COLUMN simulated;
        DROP TABLE tracking_simulations;
    """)
