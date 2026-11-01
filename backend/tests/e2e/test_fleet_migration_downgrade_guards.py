"""Unused fleet schemas can roll back without allowing operational data loss."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import connect

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("populated", ["track", "alert", "vehicle", "location", "radius", "sync"])
def test_downgrade_refuses_operational_data_and_rolls_back_the_entire_graph(populated: str) -> None:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"

    with connect(dsn) as connection:
        company_id, warehouse_id, branch_id = connection.execute(
            "SELECT company_id, id, branch_id FROM warehouses "
            "WHERE branch_id IS NOT NULL ORDER BY id LIMIT 1"
        ).fetchone()
        if populated in {"track", "alert"}:
            destination_id = connection.execute(
                "SELECT id FROM warehouses WHERE company_id = %s AND id <> %s LIMIT 1",
                (company_id, warehouse_id),
            ).fetchone()[0]
            user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
            transfer_id = connection.execute(
                "INSERT INTO inventory_transfers (id, company_id, code, origin_warehouse_id, "
                "destination_warehouse_id, created_by_id, created_at, updated_at) "
                "VALUES (gen_random_uuid(), %s, 'GUARD-TRIP', %s, %s, %s, now(), now()) RETURNING id",
                (company_id, warehouse_id, destination_id, user_id),
            ).fetchone()[0]
            if populated == "track":
                connection.execute(
                    "INSERT INTO inventory_transfer_tracks "
                    "(transfer_id, company_id, started_at, ended_at) VALUES (%s, %s, now(), now())",
                    (transfer_id, company_id),
                )
                verify_sql = "SELECT count(*) FROM inventory_transfer_tracks"
            else:
                connection.execute(
                    "INSERT INTO tracking_alerts (company_id, transfer_id, kind, severity, message) "
                    "VALUES (%s, %s, 'arrived', 'info', 'Preserve alert history')",
                    (company_id, transfer_id),
                )
                verify_sql = "SELECT count(*) FROM tracking_alerts"
            expected_error = "stored trails and alert history"
        elif populated == "vehicle":
            # Soft deletion does not make operational history disposable.
            connection.execute(
                "INSERT INTO fleet_vehicles (company_id, branch_id, code, plate, kind, brand, "
                "model, year, capacity_kg, deleted_at) VALUES (%s, %s, 'GUARD', 'GUARD', "
                "'cargo_van', 'Test', 'Test', 2026, 1000, now())",
                (company_id, branch_id),
            )
            verify_sql = "SELECT count(*) FROM fleet_vehicles WHERE deleted_at IS NOT NULL"
            expected_error = "datos de flota o despachos"
        elif populated == "location":
            connection.execute(
                "UPDATE warehouses SET location_mode = 'own', latitude = 13.7, longitude = -89.1 "
                "WHERE id = %s",
                (warehouse_id,),
            )
            verify_sql = "SELECT count(*) FROM warehouses WHERE location_mode = 'own'"
            expected_error = "warehouse locations"
        elif populated == "radius":
            connection.execute(
                "UPDATE branches SET geofence_radius_m = 200 WHERE id = %s", (branch_id,)
            )
            verify_sql = "SELECT count(*) FROM branches WHERE geofence_radius_m = 200"
            expected_error = "warehouse locations"
        else:
            connection.execute(
                "INSERT INTO tracking_sync_state (company_id, sites_synced_at) VALUES (%s, now())",
                (company_id,),
            )
            verify_sql = "SELECT count(*) FROM tracking_sync_state"
            expected_error = "warehouse locations"
        before = connection.execute(verify_sql).fetchone()

    with pytest.raises(RuntimeError, match=expected_error):
        command.downgrade(config, "0097")

    with connect(dsn) as connection:
        assert connection.execute(verify_sql).fetchone() == before
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            ("0104",)
        ]
        # Changes made by 0103..0101 downgrades are rolled back too.
        assert connection.execute("SELECT to_regclass('tracking_simulations')").fetchone() == (
            "tracking_simulations",
        )
