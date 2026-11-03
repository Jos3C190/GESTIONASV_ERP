"""Overlapping reservations are refused by the database, and rollback never loses settings."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import connect

pytestmark = pytest.mark.integration


def test_refuses_to_lose_settings_and_cleans_up_when_it_can(
    rebuild_test_database: Callable[..., None],
) -> None:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    rebuild_test_database()
    try:
        with connect(dsn) as connection:
            connection.execute("""
                INSERT INTO fleet_vehicles
                    (company_id, branch_id, code, plate, kind, brand, model, year, capacity_kg)
                SELECT b.company_id, b.id, 'MIG-5', 'MIG 5', t.code, 'Marca', 'Modelo', 2024, 100
                FROM branches b
                JOIN fleet_vehicle_types t ON t.company_id = b.company_id
                LIMIT 1
            """)
            insert = """
                INSERT INTO fleet_reservations
                    (company_id, vehicle_id, starts_at, ends_at, reason)
                SELECT company_id, id, %s::timestamptz, %s::timestamptz, 'Prueba'
                FROM fleet_vehicles WHERE code = 'MIG-5'
            """
            connection.execute(insert, ("2030-01-01 08:00+00", "2030-01-01 12:00+00"))
            # Tocarse en el borde no es solaparse.
            connection.execute(insert, ("2030-01-01 12:00+00", "2030-01-01 14:00+00"))
        with connect(dsn) as connection, pytest.raises(psycopg.errors.ExclusionViolation):
            connection.execute(insert, ("2030-01-01 11:00+00", "2030-01-01 13:00+00"))
        with pytest.raises(RuntimeError, match="operación diaria"):
            command.downgrade(config, "0110")
        with connect(dsn) as connection:
            connection.execute("DELETE FROM fleet_reservations")
        command.downgrade(config, "0110")
        with connect(dsn) as connection:
            assert connection.execute("SELECT to_regclass('fleet_settings')").fetchone() == (None,)
        command.upgrade(config, "0111")
    finally:
        rebuild_test_database()
