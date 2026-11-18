"""0130: documentos en contingencia, sus reglas en la base y la guarda del downgrade."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import Connection, connect, errors
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.integration

_ROW = (
    "INSERT INTO sales_fiscal_documents (company_id, branch_id, sale_id, establishment_id, "
    "point_of_sale_id, document_type, mode, status, idempotency_key, total, issuer_snapshot, "
    "request_payload, created_by_id, generation_code, control_number, issued_at, "
    "contingency_type, contingency_reason, contingency_at) "
    "VALUES (%s, %s, %s, %s, %s, '01', 'hacienda-test', %s, %s, 10, %s, %s, %s, %s, %s, %s, "
    "%s, %s, %s)"
)
_AT = "2026-11-17T10:00:00-06:00"


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def _row(
    connection: Connection[tuple[object, ...]],
    *,
    status: str = "contingency",
    control: str | None = "DTE-01-M001P001-000000000000001",
    kind: int | None = 1,
    at: str | None = _AT,
) -> None:
    connection.execute(
        _ROW,
        (
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
            status,
            f"clave-{uuid.uuid4()}",
            Jsonb({}),
            Jsonb({}),
            uuid.uuid4(),
            uuid.uuid4() if control else None,
            control,
            _AT if control else None,
            kind,
            "Corte de energía" if kind == 5 else None,
            at,
        ),
    )


def test_contingency_rules(rebuild_test_database: Callable[..., None]) -> None:
    _, dsn = _config()
    rebuild_test_database()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        _row(connection)
        _row(connection, kind=5)
        _row(connection, status="pending", control=None, kind=None, at=None)
        for kwargs in (
            {"at": None},
            {"kind": None},
            {"kind": 6},
            {"control": None},
        ):
            with pytest.raises(errors.CheckViolation):
                _row(connection, **kwargs)  # type: ignore[arg-type]
        assert connection.execute(
            "SELECT count(*) FROM permissions WHERE code = 'sales_invoices:contingency'"
        ).fetchone() == (1,)


def test_downgrade_refuses_when_contingency_documents_exist(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            _row(connection)
        with pytest.raises(RuntimeError, match="1 documentos fiscales generados en contingencia"):
            command.downgrade(config, "0129")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales_fiscal_documents")
        command.downgrade(config, "0129")
        with connect(dsn, autocommit=True) as connection:
            assert connection.execute(
                "SELECT count(*) FROM permissions WHERE code = 'sales_invoices:contingency'"
            ).fetchone() == (0,)
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
