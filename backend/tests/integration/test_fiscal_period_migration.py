"""0144: cierres de período, un cierre vigente por mes y la guarda del downgrade."""

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

_CLOSE = (
    "INSERT INTO fiscal_period_closes (company_id, period, status, reopen_reason, reopened_by_id, "
    "reopened_at, closed_by_id) VALUES (%s, %s, %s, %s, %s, %s, gen_random_uuid())"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def test_period_close_rules_and_downgrade_guard(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        company, actor = uuid.uuid4(), uuid.uuid4()
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            with pytest.raises(errors.CheckViolation):  # no es el primer día del mes
                connection.execute(_CLOSE, (company, "2026-10-05", "closed", None, None, None))
            with pytest.raises(errors.CheckViolation):  # reabierto sin motivo
                connection.execute(_CLOSE, (company, "2026-10-01", "reopened", None, actor, "now"))
            connection.execute(_CLOSE, (company, "2026-10-01", "closed", None, None, None))
            with pytest.raises(errors.UniqueViolation):  # dos cierres vigentes del mismo mes
                connection.execute(_CLOSE, (company, "2026-10-01", "closed", None, None, None))
            connection.execute(
                _CLOSE,
                (company, "2026-10-01", "reopened", "Cobro registrado tarde", actor, "now"),
            )
            permission = connection.execute(
                "SELECT count(*) FROM permissions WHERE code = 'fiscal_periods:manage'"
            ).fetchone()
            assert permission == (1,)
        with pytest.raises(RuntimeError, match="2 cierres de período"):
            command.downgrade(config, "0143")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM fiscal_period_closes")
        command.downgrade(config, "0143")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
