"""0141: bloqueo de crédito, días de gracia, notas de cobro y la guarda del downgrade."""

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

_NOTE = (
    "INSERT INTO sales_collection_notes (company_id, customer_id, note, created_by_id) "
    "VALUES (gen_random_uuid(), gen_random_uuid(), %s, gen_random_uuid())"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def test_credit_control_schema_and_downgrade_guard(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            assert connection.execute(
                "SELECT count(*) FROM permissions WHERE code = 'sales_credit:authorize'"
            ).fetchone() == (1,)
            customer = connection.execute("SELECT id FROM sales_customers LIMIT 1").fetchone()
            if customer is not None:
                with pytest.raises(errors.CheckViolation):
                    connection.execute(
                        "UPDATE sales_customers SET credit_blocked = true WHERE id = %s",
                        (customer[0],),
                    )
            company = uuid.uuid4()
            connection.execute("INSERT INTO sales_settings (company_id) VALUES (%s)", (company,))
            with pytest.raises(errors.CheckViolation):
                connection.execute(
                    "UPDATE sales_settings SET credit_overdue_grace_days = 400 WHERE company_id = %s",
                    (company,),
                )
            with pytest.raises(errors.CheckViolation):
                connection.execute(_NOTE, ("hey",))
            connection.execute(_NOTE, ("Llamó y paga el viernes",))
        with pytest.raises(RuntimeError, match="1 notas de cobro"):
            command.downgrade(config, "0140")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales_collection_notes")
            connection.execute("DELETE FROM sales_settings WHERE company_id = %s", (company,))
        command.downgrade(config, "0140")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
