"""0126: documento fiscal del pedido, sus reglas en la base y la guarda del downgrade."""

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

_DOCUMENT = (
    "INSERT INTO sales_fiscal_documents (company_id, branch_id, sale_id, establishment_id, "
    "point_of_sale_id, document_type, mode, status, idempotency_key, generation_code, "
    "control_number, total, issuer_snapshot, request_payload, seal, issued_at, attempts, "
    "created_by_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '{}', '{}', %s, "
    "%s, %s, %s)"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def _document(
    connection: Connection[tuple[object, ...]],
    company: uuid.UUID,
    sale: uuid.UUID,
    *,
    document: str = "01",
    mode: str = "simulated",
    status: str = "pending",
    identity: bool = False,
    seal: bool = False,
    total: str = "113.00",
    attempts: int = 0,
    key: str | None = None,
) -> None:
    connection.execute(
        _DOCUMENT,
        (
            company,
            uuid.uuid4(),
            sale,
            uuid.uuid4(),
            uuid.uuid4(),
            document,
            mode,
            status,
            key or uuid.uuid4().hex,
            uuid.uuid4() if identity else None,
            f"DTE-01-M001P001-{uuid.uuid4().int % 10**15:015d}" if identity else None,
            total,
            "A" * 40 if seal else None,
            "2026-11-17T10:00:00-06:00" if identity else None,
            attempts,
            uuid.uuid4(),
        ),
    )


def test_fiscal_document_rules(rebuild_test_database: Callable[..., None]) -> None:
    _, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        _document(connection, company, uuid.uuid4())
        _document(connection, company, uuid.uuid4(), status="simulated", identity=True)
        _document(
            connection,
            company,
            uuid.uuid4(),
            document="03",
            mode="hacienda-test",
            status="issued",
            identity=True,
            seal=True,
        )
        # Un pedido admite varios intentos fallidos o rechazados (desde 0131 un rechazado ya no
        # bloquea volver a facturar) y a lo sumo un documento vigente.
        sale = uuid.uuid4()
        _document(connection, company, sale, status="failed")
        _document(connection, company, sale, status="failed")
        _document(connection, company, sale, status="rejected")
        _document(connection, company, sale)
        with pytest.raises(errors.UniqueViolation):
            _document(connection, company, sale)
        _document(connection, company, uuid.uuid4(), key="clave-1")
        with pytest.raises(errors.UniqueViolation):
            _document(connection, company, uuid.uuid4(), key="clave-1")
        invalid: list[dict[str, object]] = [
            {"document": "05"},
            {"mode": "live"},
            {"status": "sent"},
            {"status": "simulated"},
            {"status": "issued", "identity": True},
            {"total": "-1.00"},
            {"attempts": -1},
        ]
        for kwargs in invalid:
            with pytest.raises(errors.CheckViolation):
                _document(connection, company, uuid.uuid4(), **kwargs)  # type: ignore[arg-type]


def test_downgrade_refuses_when_documents_exist(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            _document(connection, company, uuid.uuid4())
        with pytest.raises(RuntimeError, match="1 documentos fiscales"):
            command.downgrade(config, "0125")
        with connect(dsn, autocommit=True) as connection:
            connection.execute(
                "DELETE FROM sales_fiscal_documents WHERE company_id = %s", (company,)
            )
        command.downgrade(config, "0125")
        with connect(dsn, autocommit=True) as connection:
            gone = connection.execute(
                "SELECT count(*) FROM permissions WHERE code LIKE 'sales_invoices:%'"
            ).fetchone()
        assert gone == (0,)
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
