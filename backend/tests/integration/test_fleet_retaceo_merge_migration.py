"""Both migration branches converge without replaying existing tables."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import connect

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("source_revision", ["0098", "0103"])
def test_merge_upgrades_each_branch_and_preserves_existing_roles(
    rebuild_test_database: Callable[..., None], source_revision: str
) -> None:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert len(script.get_heads()) == 1

    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    rebuild_test_database(revision=source_revision, seed=False)
    try:
        with connect(dsn) as connection:
            role_id = connection.execute(
                "SELECT id FROM roles WHERE name = 'SUPER_ADMIN'"
            ).fetchone()[0]
            assert connection.execute("SELECT to_regclass('fleet_vehicles')").fetchone()[0] == (
                "fleet_vehicles" if source_revision == "0103" else None
            )

        command.upgrade(config, "0104")

        with connect(dsn) as connection:
            assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
                ("0104",)
            ]
            assert connection.execute(
                "SELECT id FROM roles WHERE name = 'SUPER_ADMIN'"
            ).fetchone() == (role_id,)
            assert connection.execute("SELECT to_regclass('fleet_vehicles')").fetchone() == (
                "fleet_vehicles",
            )
            columns = connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'retaceos' "
                "AND column_name IN ('calculation_mode', 'dai_rate', 'vat_rate')"
            ).fetchall()
            assert {row[0] for row in columns} == {"calculation_mode", "dai_rate", "vat_rate"}
    finally:
        # Subsequent integration tests expect the canonical seeded test database.
        rebuild_test_database()
