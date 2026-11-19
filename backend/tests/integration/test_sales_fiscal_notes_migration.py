"""0133: notas de crédito y de débito, sus líneas, el documento activo y la guarda del downgrade."""

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

_AT = "2026-11-18T10:00:00-06:00"
_DOC = (
    "INSERT INTO sales_fiscal_documents (id, company_id, branch_id, sale_id, establishment_id, "
    "point_of_sale_id, document_type, mode, status, idempotency_key, total, issuer_snapshot, "
    "request_payload, created_by_id, generation_code, control_number, issued_at, "
    "related_document_id, note_reason) VALUES (%s, %s, %s, %s, %s, %s, %s, 'simulated', "
    "'simulated', %s, 10, %s, %s, %s, %s, 'DTE-03-M001P001-000000000000001', %s, %s, %s)"
)
_LINE = (
    "INSERT INTO sales_fiscal_note_lines (company_id, note_id, line_number, ccf_line_number, kind, "
    "nature, description, quantity, amount) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
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
    document_type: str = "03",
    *,
    related: uuid.UUID | None = None,
    reason: str | None = None,
) -> uuid.UUID:
    document_id = uuid.uuid4()
    connection.execute(
        _DOC,
        (
            document_id,
            company,
            uuid.uuid4(),
            sale,
            uuid.uuid4(),
            uuid.uuid4(),
            document_type,
            f"clave-{uuid.uuid4()}",
            Jsonb({}),
            Jsonb({}),
            uuid.uuid4(),
            uuid.uuid4(),
            _AT,
            related,
            reason,
        ),
    )
    return document_id


def test_notes_live_beside_the_active_ccf(rebuild_test_database: Callable[..., None]) -> None:
    _, dsn = _config()
    rebuild_test_database()
    company, sale = uuid.uuid4(), uuid.uuid4()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        ccf = _document(connection, company, sale)
        # Las notas del mismo pedido no cuentan como otro documento activo.
        credit = _document(connection, company, sale, "05", related=ccf, reason="Devolución")
        _document(connection, company, sale, "06", related=ccf, reason="Intereses")
        with pytest.raises(errors.UniqueViolation):
            _document(connection, company, sale)
        for document_type, related, reason in (
            ("05", None, "Devolución"),  # nota sin CCF
            ("05", ccf, None),  # nota sin motivo
            ("05", ccf, "abc"),  # motivo corto
            ("03", ccf, None),  # CCF con relacionado
            ("11", None, None),
        ):
            with pytest.raises(errors.CheckViolation):
                _document(
                    connection, company, uuid.uuid4(), document_type, related=related, reason=reason
                )

        connection.execute(_LINE, (company, credit, 1, 1, "return", "taxed", "Camiseta", 1, 28.5))
        connection.execute(_LINE, (company, credit, 2, 2, "discount", "taxed", "Rebaja", None, 5))
        with pytest.raises(errors.UniqueViolation):
            connection.execute(_LINE, (company, credit, 2, 3, "discount", "taxed", "Otra", None, 1))
        for values in (
            (3, None, "return", "taxed", "Sin línea", 1, 1),
            (3, 1, "return", "taxed", "Sin cantidad", None, 1),
            (3, 1, "discount", "taxed", "Con cantidad", 1, 1),
            (3, None, "charge", "taxed", "Sin cantidad", None, 1),
            (3, 1, "discount", "taxed", "Monto cero", None, 0),
            (3, 1, "discount", "vat", "Naturaleza", None, 1),
        ):
            with pytest.raises(errors.CheckViolation):
                connection.execute(_LINE, (company, credit, *values))
        assert connection.execute(
            "SELECT count(*) FROM permissions WHERE code = 'sales_invoices:notes'"
        ).fetchone() == (1,)


def test_downgrade_refuses_while_notes_exist(rebuild_test_database: Callable[..., None]) -> None:
    config, dsn = _config()
    rebuild_test_database()
    company, sale = uuid.uuid4(), uuid.uuid4()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            ccf = _document(connection, company, sale)
            _document(connection, company, sale, "05", related=ccf, reason="Devolución")
        with pytest.raises(RuntimeError, match="1 notas"):
            command.downgrade(config, "0132")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales_fiscal_documents WHERE document_type = '05'")
        command.downgrade(config, "0132")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
