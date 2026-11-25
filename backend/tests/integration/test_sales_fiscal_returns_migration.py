"""0138: eventos de retorno, sus líneas, el envío por correo y la guarda del downgrade."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import connect, errors
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.integration

_RETURN = (
    "INSERT INTO sales_fiscal_returns (id, company_id, document_id, reason, status, "
    "idempotency_key, request_payload, total, created_by_id, generation_code, issued_at) "
    "VALUES (%s, %s, gen_random_uuid(), %s, %s, %s, %s, 10, gen_random_uuid(), %s, %s)"
)
_LINE = (
    "INSERT INTO sales_fiscal_return_lines (company_id, return_id, line_number, "
    "invoice_line_number, nature, description, quantity, amount, vat) "
    "VALUES (%s, %s, 1, 1, %s, 'Harina', 1, 22.60, %s)"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def test_returns_schema_and_downgrade_guard(rebuild_test_database: Callable[..., None]) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        company = uuid.uuid4()
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            assert connection.execute(
                "SELECT count(*) FROM permissions WHERE code = 'sales_invoices:returns'"
            ).fetchone() == (1,)

            def insert(reason: str, status: str, *, issued: bool) -> uuid.UUID:
                return_id = uuid.uuid4()
                connection.execute(
                    _RETURN,
                    (
                        return_id,
                        company,
                        reason,
                        status,
                        f"erp-{return_id}",
                        Jsonb({"items": []}),
                        uuid.uuid4() if issued else None,
                        "2026-11-25T10:00:00-06:00" if issued else None,
                    ),
                )
                return return_id

            for reason, status, issued in (
                ("No", "pending", False),  # motivo muy corto
                ("Cliente devolvió", "simulated", False),  # emitido sin identidad
                ("Cliente devolvió", "annulled", True),  # estado fuera del catálogo
                ("Cliente devolvió", "invalidated", True),  # anulado sin anulación aceptada
            ):
                with pytest.raises(errors.CheckViolation):
                    insert(reason, status, issued=issued)
            return_id = insert("Cliente devolvió dos bolsas", "simulated", issued=True)
            with pytest.raises(errors.CheckViolation):
                connection.execute(_LINE, (company, return_id, "exempt", "1.00"))
            connection.execute(_LINE, (company, return_id, "taxed", "2.60"))
        with pytest.raises(RuntimeError, match="1 eventos de retorno"):
            command.downgrade(config, "0137")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales_fiscal_return_lines")
            connection.execute("DELETE FROM sales_fiscal_returns")
        command.downgrade(config, "0137")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
