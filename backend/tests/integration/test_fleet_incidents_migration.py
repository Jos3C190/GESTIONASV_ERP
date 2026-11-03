"""Companies get a checklist, and rolling back never loses incidents silently."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import connect

pytestmark = pytest.mark.integration


def test_seeds_the_checklist_and_refuses_to_lose_custom_points(
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
            missing = connection.execute("""
                SELECT count(*) FROM companies c
                WHERE NOT EXISTS (
                    SELECT 1 FROM fleet_inspection_items i
                    WHERE i.company_id = c.id AND i.name = 'Frenos' AND i.is_critical
                )
            """).fetchone()
            assert missing == (0,)
            connection.execute("""
                INSERT INTO fleet_inspection_items (company_id, name)
                SELECT id, 'Punto propio' FROM companies LIMIT 1
            """)
        with pytest.raises(RuntimeError, match="incidentes e inspecciones"):
            command.downgrade(config, "0109")
        with connect(dsn) as connection:
            connection.execute("DELETE FROM fleet_inspection_items WHERE name = 'Punto propio'")
        command.downgrade(config, "0109")
        with connect(dsn) as connection:
            assert connection.execute("SELECT to_regclass('fleet_incidents')").fetchone() == (None,)
        command.upgrade(config, "0110")
    finally:
        rebuild_test_database()
