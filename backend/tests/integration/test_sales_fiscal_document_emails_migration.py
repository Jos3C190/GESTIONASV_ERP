"""0127: envíos por correo del documento fiscal, sus reglas en la base y la guarda del downgrade."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import Connection, connect, errors

pytestmark = pytest.mark.integration

_EMAIL = (
    "INSERT INTO sales_fiscal_document_emails (company_id, document_id, recipients, origin, "
    "status, requested_by_id, sent_at, message_id, attempts) VALUES (%s, %s, %s, %s, %s, %s, "
    "%s, %s, %s)"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def _email(
    connection: Connection[tuple[object, ...]],
    company: uuid.UUID,
    document: uuid.UUID,
    *,
    recipients: list[str] | None = None,
    origin: str = "manual",
    status: str = "pending",
    requester: bool = True,
    sent: bool = False,
    attempts: int = 0,
) -> None:
    connection.execute(
        _EMAIL,
        (
            company,
            document,
            ["cliente@example.com"] if recipients is None else recipients,
            origin,
            status,
            uuid.uuid4() if requester else None,
            "2026-11-17T10:00:00-06:00" if sent else None,
            "<abc@erp.local>" if sent else None,
            attempts,
        ),
    )


def test_email_rules(rebuild_test_database: Callable[..., None]) -> None:
    _, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        document = uuid.uuid4()
        _email(connection, company, document, origin="auto", requester=False)
        _email(connection, company, document)
        _email(connection, company, document, status="sent", sent=True)
        _email(connection, company, document, status="failed", attempts=3)
        # Un solo envío automático por documento.
        with pytest.raises(errors.UniqueViolation):
            _email(connection, company, document, origin="auto", requester=False)
        invalid: list[dict[str, object]] = [
            {"recipients": []},
            {"recipients": [f"c{i}@example.com" for i in range(6)]},
            {"origin": "bulk"},
            {"origin": "auto"},
            {"requester": False},
            {"status": "queued"},
            {"status": "sent"},
            {"sent": True},
            {"attempts": -1},
        ]
        for kwargs in invalid:
            with pytest.raises(errors.CheckViolation):
                _email(connection, company, uuid.uuid4(), **kwargs)  # type: ignore[arg-type]


def test_downgrade_refuses_when_emails_exist(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            _email(connection, company, uuid.uuid4())
        with pytest.raises(RuntimeError, match="1 envíos"):
            command.downgrade(config, "0126")
        with connect(dsn, autocommit=True) as connection:
            connection.execute(
                "DELETE FROM sales_fiscal_document_emails WHERE company_id = %s", (company,)
            )
        command.downgrade(config, "0126")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
