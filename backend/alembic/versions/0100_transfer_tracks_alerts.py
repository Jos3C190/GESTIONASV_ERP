"""Stored transfer trails and tracking alerts."""

import sqlalchemy as sa
from alembic import op

revision = "0100"
down_revision = "0099"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # El recorrido de un traslado cerrado queda en el ERP: no depende de que Traccar lo conserve.
    op.execute("""
        CREATE TABLE inventory_transfer_tracks (
          transfer_id uuid PRIMARY KEY,
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          traccar_device_id integer,
          started_at timestamptz NOT NULL,
          ended_at timestamptz NOT NULL,
          points jsonb NOT NULL DEFAULT '[]'::jsonb,
          matched jsonb NOT NULL DEFAULT '[]'::jsonb,
          trail_matched boolean NOT NULL DEFAULT false,
          point_count integer NOT NULL DEFAULT 0,
          distance_m numeric(12,1) NOT NULL DEFAULT 0,
          max_speed_kmh numeric(6,1),
          captured_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_transfer_tracks_transfer
            FOREIGN KEY (company_id, transfer_id)
            REFERENCES inventory_transfers (company_id, id) ON DELETE CASCADE,
          CONSTRAINT ck_transfer_tracks_window CHECK (ended_at >= started_at)
        );
    """)
    op.execute("""
        CREATE TABLE tracking_alerts (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
          transfer_id uuid NOT NULL,
          origin_branch_id uuid,
          destination_branch_id uuid,
          kind varchar(16) NOT NULL,
          severity varchar(10) NOT NULL,
          message text NOT NULL,
          details jsonb NOT NULL DEFAULT '{}'::jsonb,
          opened_at timestamptz NOT NULL DEFAULT now(),
          last_seen_at timestamptz NOT NULL DEFAULT now(),
          resolved_at timestamptz,
          acknowledged_at timestamptz,
          acknowledged_by uuid REFERENCES users(id) ON DELETE SET NULL,
          CONSTRAINT fk_tracking_alerts_transfer
            FOREIGN KEY (company_id, transfer_id)
            REFERENCES inventory_transfers (company_id, id) ON DELETE CASCADE,
          CONSTRAINT ck_tracking_alerts_kind
            CHECK (kind IN ('arrived', 'delayed', 'long_stop', 'gps_lost', 'off_route')),
          CONSTRAINT ck_tracking_alerts_severity
            CHECK (severity IN ('info', 'warning', 'critical')),
          CONSTRAINT ck_tracking_alerts_ack
            CHECK ((acknowledged_at IS NULL) = (acknowledged_by IS NULL))
        );
        -- Una sola alerta abierta por traslado y tipo: el monitor la actualiza, no la repite.
        CREATE UNIQUE INDEX uq_tracking_alerts_open
          ON tracking_alerts (transfer_id, kind) WHERE resolved_at IS NULL;
        CREATE INDEX ix_tracking_alerts_company_open
          ON tracking_alerts (company_id, opened_at DESC) WHERE resolved_at IS NULL;
        CREATE INDEX ix_tracking_alerts_transfer ON tracking_alerts (transfer_id, opened_at DESC);
    """)


def downgrade() -> None:
    # Empty installations can be rolled back; operational history must never be discarded.
    op.execute("LOCK TABLE inventory_transfer_tracks, tracking_alerts IN ACCESS EXCLUSIVE MODE")
    populated = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM inventory_transfer_tracks) "
            "OR EXISTS (SELECT 1 FROM tracking_alerts)"
        )
    )
    if populated:
        raise RuntimeError("0100 is not reversible: it would drop stored trails and alert history.")
    op.drop_table("tracking_alerts")
    op.drop_table("inventory_transfer_tracks")
