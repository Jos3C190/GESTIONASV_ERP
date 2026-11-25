"""0134 a 0136: sin permiso de vender bajo costo, promociones por sucursal y salida al confirmar."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import connect, errors

pytestmark = pytest.mark.integration


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def _columns(connection, table: str) -> set[str]:  # noqa: ANN001
    rows = connection.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,)
    ).fetchall()
    return {row[0] for row in rows}


def test_schema_and_downgrade_guard(rebuild_test_database: Callable[..., None]) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        with connect(dsn, autocommit=True) as connection:
            assert "can_sell_below_cost" not in _columns(connection, "sales_discount_policies")
            assert "auto_deliver_on_confirm" in _columns(connection, "sales_settings")
            assert connection.execute(
                "SELECT count(*) FROM permissions WHERE code = 'sales_promotions:manage'"
            ).fetchone() == (1,)
            connection.execute("SET session_replication_role = replica")
            company = connection.execute("SELECT gen_random_uuid()").fetchone()[0]
            insert = (
                "INSERT INTO sales_branch_promotions (company_id, branch_id, product_id, "
                "discount_percent, valid_from, valid_to) VALUES (%s, gen_random_uuid(), 1, %s, "
                "'2026-11-24', %s)"
            )
            for percent, valid_to in (("0", None), ("100", None), ("10", "2026-11-23")):
                with pytest.raises(errors.CheckViolation):
                    connection.execute(insert, (company, percent, valid_to))
            connection.execute(insert, (company, "10", None))
        with pytest.raises(RuntimeError, match="1 promociones"):
            command.downgrade(config, "0134")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales_branch_promotions")
        command.downgrade(config, "0133")
        with connect(dsn, autocommit=True) as connection:
            assert "can_sell_below_cost" in _columns(connection, "sales_discount_policies")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
