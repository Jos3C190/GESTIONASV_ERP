"""Simulator round trips: the planned stops of a session and its current leg."""

from alembic import op

revision = "0102"
down_revision = "0101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Las paradas originales sobreviven a desvíos y regresos: el primer punto es el inicio.
    op.execute("""
        ALTER TABLE tracking_simulations
          ADD COLUMN stops jsonb NOT NULL DEFAULT '[]'::jsonb,
          ADD COLUMN leg varchar(8) NOT NULL DEFAULT 'outbound',
          ADD CONSTRAINT ck_tracking_simulations_leg CHECK (leg IN ('outbound','return'));
        UPDATE tracking_simulations
           SET stops = CASE
                 WHEN jsonb_array_length(route) >= 2
                   THEN jsonb_build_array(route -> 0, route -> (jsonb_array_length(route) - 1))
                 ELSE jsonb_build_array(jsonb_build_array(longitude, latitude))
               END;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE tracking_simulations
          DROP CONSTRAINT ck_tracking_simulations_leg,
          DROP COLUMN leg,
          DROP COLUMN stops;
    """)
