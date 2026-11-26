"""0143: vínculo del pedido de cambio con su devolución; ida y vuelta de la migración."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import connect

pytestmark = pytest.mark.integration


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def _exchange_objects(dsn: str) -> tuple[bool, bool, bool]:
    with connect(dsn, autocommit=True) as connection:
        column = connection.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'sales' AND column_name = 'exchange_return_id'"
        ).fetchone()
        constraint = connection.execute(
            "SELECT 1 FROM pg_constraint WHERE conname = 'fk_sales_exchange_return'"
        ).fetchone()
        index = connection.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_sales_exchange_return_active'"
        ).fetchone()
    partial = bool(index) and "status" in index[0] and "UNIQUE" in index[0]
    return column is not None, constraint is not None, partial


def test_exchange_column_round_trip(rebuild_test_database: Callable[..., None]) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        assert _exchange_objects(dsn) == (True, True, True)
        command.downgrade(config, "0142")
        assert _exchange_objects(dsn) == (False, False, False)
        command.upgrade(config, "head")
        assert _exchange_objects(dsn) == (True, True, True)
    finally:
        rebuild_test_database()
