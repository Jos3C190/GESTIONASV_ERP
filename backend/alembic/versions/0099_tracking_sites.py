"""Warehouse locations of their own, arrival radius and tracking site sync state."""

import sqlalchemy as sa
from alembic import op

revision = "0099"
down_revision = "0098_fleet"
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
    op.execute("LOCK TABLE warehouses, branches, tracking_sync_state IN ACCESS EXCLUSIVE MODE")
    populated = op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM warehouses WHERE location_mode <> 'branch' "
            "OR latitude IS NOT NULL OR longitude IS NOT NULL OR geofence_radius_m IS NOT NULL) "
            "OR EXISTS (SELECT 1 FROM branches WHERE geofence_radius_m <> 150) "
            "OR EXISTS (SELECT 1 FROM tracking_sync_state)"
        )
    )
    if populated:
        raise RuntimeError("0099 is not reversible: it would drop warehouse locations.")
    op.drop_table("tracking_sync_state")
    op.drop_constraint("ck_branches_geofence_radius", "branches", type_="check")
    op.drop_column("branches", "geofence_radius_m")
    for name in (
        "ck_warehouses_location_mode",
        "ck_warehouses_location_coordinates",
        "ck_warehouses_geofence_radius",
    ):
        op.drop_constraint(name, "warehouses", type_="check")
    for name in ("location_mode", "latitude", "longitude", "geofence_radius_m"):
        op.drop_column("warehouses", name)
