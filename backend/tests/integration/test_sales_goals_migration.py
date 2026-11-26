"""0145: metas de venta por sucursal y mes, permisos del análisis y guarda del downgrade."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import connect, errors

pytestmark = pytest.mark.integration

_GOAL = (
    "INSERT INTO sales_branch_goals (company_id, branch_id, period, amount, updated_by_id) "
    "VALUES (%s, %s, %s, %s, gen_random_uuid())"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def test_goals_schema_permissions_and_guard(rebuild_test_database: Callable[..., None]) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        company, branch = uuid.uuid4(), uuid.uuid4()
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            with pytest.raises(errors.CheckViolation):  # no es el primer día del mes
                connection.execute(_GOAL, (company, branch, "2026-11-05", 100))
            with pytest.raises(errors.CheckViolation):  # monto no positivo
                connection.execute(_GOAL, (company, branch, "2026-11-01", 0))
            connection.execute(_GOAL, (company, branch, "2026-11-01", 100))
            with pytest.raises(errors.UniqueViolation):  # una meta por sucursal y mes
                connection.execute(_GOAL, (company, branch, "2026-11-01", 200))
            codes = {
                row[0]
                for row in connection.execute(
                    "SELECT code FROM permissions "
                    "WHERE code IN ('sales_analytics:read', 'sales_goals:manage')"
                ).fetchall()
            }
            assert codes == {"sales_analytics:read", "sales_goals:manage"}
            module = connection.execute(
                "SELECT module FROM permissions WHERE code = 'fiscal_periods:manage'"
            ).fetchone()
            assert module == ("fiscal",)
        with pytest.raises(RuntimeError, match="1 metas de venta"):
            command.downgrade(config, "0144")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales_branch_goals")
        command.downgrade(config, "0144")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
