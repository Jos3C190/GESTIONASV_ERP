"""Rolling back ownership and costs must not silently lose a contract."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import connect

pytestmark = pytest.mark.integration


def test_rollback_refuses_while_a_contract_exists(
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
                    (company_id, branch_id, code, plate, kind, brand, model, year, capacity_kg,
                     ownership)
                SELECT b.company_id, b.id, 'MIG-1', 'MIG 1', t.code, 'Marca', 'Modelo', 2024, 100,
                       'rented'
                FROM branches b
                JOIN fleet_vehicle_types t ON t.company_id = b.company_id
                LIMIT 1
            """)
        with pytest.raises(RuntimeError, match="propiedad y costos"):
            command.downgrade(config, "0108")
        with connect(dsn) as connection:
            connection.execute("UPDATE fleet_vehicles SET ownership = 'owned'")
        command.downgrade(config, "0108")
        with connect(dsn) as connection:
            assert connection.execute("SELECT to_regclass('fleet_costs')").fetchone() == (None,)
        command.upgrade(config, "0109")
    finally:
        rebuild_test_database()
