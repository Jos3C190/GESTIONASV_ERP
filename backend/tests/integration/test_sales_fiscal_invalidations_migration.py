"""0131: invalidaciones, reemplazos, el documento activo del pedido y la guarda del downgrade."""

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
    "request_payload, created_by_id, generation_code, control_number, issued_at, seal, "
    "replaces_document_id, superseded_by_id) VALUES (%s, %s, %s, %s, %s, %s, '01', 'simulated', "
    "%s, %s, 10, %s, %s, %s, %s, %s, %s, NULL, %s, %s)"
)
_INVALIDATION = (
    "INSERT INTO sales_fiscal_invalidations (company_id, document_id, kind, reason, "
    "requester_name, requester_document_type, requester_document_number, replacement_document_id, "
    "cancel_order, status, idempotency_key, event_generation_code, error_message, requested_by_id, "
    "resolved_at) VALUES (%s, %s, %s, %s, %s, '13', '01234567-8', %s, %s, %s, %s, %s, %s, %s, %s)"
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
    status: str = "simulated",
    replaces: uuid.UUID | None = None,
    superseded_by: uuid.UUID | None = None,
) -> uuid.UUID:
    document_id = uuid.uuid4()
    sealed = status != "pending"
    connection.execute(
        _DOC,
        (
            document_id,
            company,
            uuid.uuid4(),
            sale,
            uuid.uuid4(),
            uuid.uuid4(),
            status,
            f"clave-{uuid.uuid4()}",
            Jsonb({}),
            Jsonb({}),
            uuid.uuid4(),
            uuid.uuid4() if sealed else None,
            "DTE-01-M001P001-000000000000001" if sealed else None,
            _AT if sealed else None,
            replaces,
            superseded_by,
        ),
    )
    return document_id


def _invalidation(
    connection: Connection[tuple[object, ...]],
    company: uuid.UUID,
    document: uuid.UUID,
    *,
    kind: int = 2,
    replacement: uuid.UUID | None = None,
    cancel_order: bool = False,
    status: str = "pending",
    event: uuid.UUID | None = None,
    error: str | None = None,
    name: str = "María Rivas",
) -> None:
    connection.execute(
        _INVALIDATION,
        (
            company,
            document,
            kind,
            "El cliente desistió",
            name,
            replacement,
            cancel_order,
            status,
            f"inv-{uuid.uuid4()}",
            event,
            error,
            uuid.uuid4(),
            None if status == "pending" else _AT,
        ),
    )


def test_active_document_replacements_and_invalidations(
    rebuild_test_database: Callable[..., None],
) -> None:
    _, dsn = _config()
    rebuild_test_database()
    company, sale = uuid.uuid4(), uuid.uuid4()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        # Un rechazado y un invalidado no bloquean otro documento del mismo pedido.
        _document(connection, company, sale, status="rejected")
        _document(connection, company, sale, status="invalidated")
        original = _document(connection, company, sale)
        with pytest.raises(errors.UniqueViolation):
            _document(connection, company, sale)
        # El reemplazo convive con el original mientras éste espera su invalidación.
        replacement = uuid.uuid4()
        connection.execute(
            "UPDATE sales_fiscal_documents SET superseded_by_id = %s WHERE id = %s",
            (replacement, original),
        )
        connection.execute(
            _DOC,
            (
                replacement,
                company,
                uuid.uuid4(),
                sale,
                uuid.uuid4(),
                uuid.uuid4(),
                "pending",
                "clave-reemplazo",
                Jsonb({}),
                Jsonb({}),
                uuid.uuid4(),
                None,
                None,
                None,
                original,
                None,
            ),
        )
        with pytest.raises(errors.CheckViolation):
            connection.execute(
                "UPDATE sales_fiscal_documents SET replaces_document_id = id WHERE id = %s",
                (original,),
            )

        _invalidation(connection, company, original, kind=1, replacement=replacement)
        with pytest.raises(errors.UniqueViolation):
            _invalidation(connection, company, original)  # una sola pendiente por documento
        other = _document(connection, company, uuid.uuid4())
        _invalidation(connection, company, other, status="accepted", event=uuid.uuid4())
        _invalidation(connection, company, other, status="rejected", error="Fuera de plazo")
        for kwargs in (
            {"kind": 1},  # tipo 1 sin reemplazo
            {"kind": 2, "replacement": replacement},
            {"kind": 1, "replacement": replacement, "cancel_order": True},
            {"kind": 3},
            {"status": "accepted"},  # sin evento
            {"status": "failed"},  # sin error
            {"name": "AB"},
        ):
            with pytest.raises(errors.CheckViolation):
                _invalidation(connection, company, uuid.uuid4(), **kwargs)  # type: ignore[arg-type]
        assert connection.execute(
            "SELECT count(*) FROM permissions WHERE code = 'sales_invoices:invalidate'"
        ).fetchone() == (1,)


def test_downgrade_refuses_while_invalidations_exist(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            document = _document(connection, company, uuid.uuid4())
            _invalidation(connection, company, document)
        with pytest.raises(RuntimeError, match="1 invalidaciones"):
            command.downgrade(config, "0130")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales_fiscal_invalidations")
            connection.execute("DELETE FROM sales_fiscal_documents")
        command.downgrade(config, "0130")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
