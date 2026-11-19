"""0132: clasificación de renta en actividades y documentos, con sus reglas en la base."""

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


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def test_renta_rules_and_downgrade(rebuild_test_database: Callable[..., None]) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")

            def activity(operation: int | None, income: int | None) -> None:
                connection.execute(
                    "INSERT INTO company_economic_activities (id, company_id, activity_code, "
                    "is_primary, renta_operation_type, renta_income_type, created_at, updated_at) "
                    "VALUES (%s, %s, '47211', false, %s, %s, now(), now())",
                    (uuid.uuid4(), uuid.uuid4(), operation, income),
                )

            activity(None, None)
            activity(1, 3)
            activity(12, 12)
            for pair in ((1, None), (5, 3), (1, 11), (12, 3), (1, 13)):
                with pytest.raises(errors.CheckViolation):
                    activity(*pair)
        command.downgrade(config, "0131")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
