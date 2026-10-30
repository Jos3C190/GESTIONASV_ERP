"""Warehouse locations of their own, arrival radius and tracking site sync state."""

from alembic import op

revision = "0099"
down_revision = "0098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Un almacén está en su sucursal (usa sus coordenadas) o en otra dirección con las suyas.
    op.execute("""
        ALTER TABLE warehouses
          ADD COLUMN location_mode varchar(8) NOT NULL DEFAULT 'branch',
          ADD COLUMN latitude numeric(9,6),
          ADD COLUMN longitude numeric(9,6),
          ADD COLUMN geofence_radius_m integer,
          ADD CONSTRAINT ck_warehouses_location_mode
            CHECK (location_mode IN ('branch', 'own')),
          ADD CONSTRAINT ck_warehouses_location_coordinates CHECK (
            (location_mode = 'own' AND latitude IS NOT NULL AND longitude IS NOT NULL
               AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)
            OR (location_mode = 'branch' AND latitude IS NULL AND longitude IS NULL
               AND geofence_radius_m IS NULL)
          ),
          ADD CONSTRAINT ck_warehouses_geofence_radius
            CHECK (geofence_radius_m IS NULL OR geofence_radius_m BETWEEN 30 AND 2000);
    """)
    op.execute("""
        ALTER TABLE branches
          ADD COLUMN geofence_radius_m integer NOT NULL DEFAULT 150,
          ADD CONSTRAINT ck_branches_geofence_radius
            CHECK (geofence_radius_m BETWEEN 30 AND 2000);
    """)
    op.execute("""
        CREATE TABLE tracking_sync_state (
          company_id uuid PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
          sites_synced_at timestamptz,
          last_attempt_at timestamptz,
          last_error text
        );
    """)


def downgrade() -> None:
    raise RuntimeError("0099 is not reversible: it would drop warehouse locations.")
