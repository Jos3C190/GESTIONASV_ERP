"""0121 crea los registros de protección de datos y protege la bitácora legal al revertir."""

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

_REQUEST = (
    "INSERT INTO data_subject_requests (company_id, code, requester_name, response_channel, "
    "right_type, description, received_on, due_on, status, resolution, closed_at) "
    "VALUES (%s, %s, 'Ana López', 'ana@example.test', %s, 'Quiero mis datos', "
    "'2026-11-16', %s, %s, %s, %s)"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def test_checks_enforce_states_and_closures(rebuild_test_database: Callable[..., None]) -> None:
    _, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        connection.execute(
            _REQUEST, (company, "SOL-1", "access", "2026-12-14", "received", None, None)
        )
        for index, values in enumerate(
            (
                ("forgetting", "2026-12-14", "received", None, None),  # derecho inválido
                ("access", "2026-11-01", "received", None, None),  # plazo antes de recibir
                ("access", "2026-12-14", "resolved", None, None),  # cerrada sin respuesta
                (
                    "access",
                    "2026-12-14",
                    "received",
                    "Atendida",
                    "2026-11-20",
                ),  # abierta con cierre
            )
        ):
            with pytest.raises(errors.CheckViolation):
                connection.execute(_REQUEST, (company, f"BAD-{index}", *values))
        with pytest.raises(errors.CheckViolation):
            connection.execute(
                "INSERT INTO personal_data_incidents (company_id, code, discovered_at, "
                "description, data_categories, status, closed_at) VALUES "
                "(%s, 'INC-1', now(), 'Acceso indebido', 'Correos', 'closed', now())",
                (company,),
            )


def test_downgrade_refuses_to_drop_legal_records(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            connection.execute(
                _REQUEST, (company, "SOL-9", "access", "2026-12-14", "received", None, None)
            )
        with pytest.raises(RuntimeError, match="protección de datos"):
            command.downgrade(config, "0120")
        with connect(dsn, autocommit=True) as connection:
            connection.execute(
                "DELETE FROM data_subject_requests WHERE company_id = %s", (company,)
            )
        command.downgrade(config, "0120")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
