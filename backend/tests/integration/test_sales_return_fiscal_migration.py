"""0142: ajustes fiscales de devoluciones, reintegros y la guarda del downgrade."""

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

_ADJUSTMENT = (
    "INSERT INTO sales_return_fiscal_adjustments (company_id, return_id, document_id, "
    "fiscal_note_id, fiscal_return_id, status, message, lines, resolution_key, created_by_id) "
    "VALUES (%s, gen_random_uuid(), %s, %s, %s, %s, %s, %s, gen_random_uuid()::text, "
    "gen_random_uuid())"
)
_REFUND = (
    "INSERT INTO sales_refunds (company_id, branch_id, customer_id, receipt_id, number, "
    "refunded_on, amount, method, reference, reason, idempotency_key, created_by_id) VALUES "
    "(%s, gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), %s, '2026-11-25', 10, %s, %s, "
    "%s, %s, gen_random_uuid())"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def test_return_fiscal_schema_and_downgrade_guard(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        company = uuid.uuid4()
        doc, note, event = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        lines = Jsonb([{"line_number": 1, "quantity": "1"}])
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            for values in (
                (doc, note, event, "issued", None),  # nota y retorno a la vez
                (doc, None, None, "issued", None),  # emitido sin vínculo
                (None, None, None, "skipped", "no"),  # motivo muy corto
                (doc, note, None, "issued", "texto"),  # emitido con motivo
            ):
                with pytest.raises(errors.CheckViolation):
                    connection.execute(_ADJUSTMENT, (company, *values, lines))
            connection.execute(_ADJUSTMENT, (company, doc, note, None, "issued", None, lines))
            connection.execute(
                _ADJUSTMENT,
                (company, None, None, None, "skipped", "El pedido no está facturado", lines),
            )
            with pytest.raises(errors.CheckViolation):
                connection.execute(
                    _REFUND, (company, 1, "card", None, "Devolución de bolsas", "key-00001")
                )
            connection.execute(
                _REFUND, (company, 1, "cash", None, "Devolución de bolsas", "key-00002")
            )
        with pytest.raises(RuntimeError, match="2 ajustes fiscales de devoluciones y 1 reintegros"):
            command.downgrade(config, "0141")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales_refunds")
            connection.execute("DELETE FROM sales_return_fiscal_adjustments")
        command.downgrade(config, "0141")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
