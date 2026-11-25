"""0140: recibos de cobro, formas de pago, aplicaciones, retenciones y la guarda del downgrade."""

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

_RECEIPT = (
    "INSERT INTO sales_receipts (id, company_id, branch_id, customer_id, number, received_on, "
    "total, status, idempotency_key, created_by_id, annul_reason, annulled_by_id, annulled_at) "
    "VALUES (%s, %s, gen_random_uuid(), gen_random_uuid(), %s, '2026-11-25', %s, %s, %s, "
    "gen_random_uuid(), %s, %s, %s)"
)
_PAYMENT = (
    "INSERT INTO sales_receipt_payments (company_id, receipt_id, line_number, method, amount, "
    "reference) VALUES (%s, %s, %s, %s, 10, %s)"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def test_receivables_schema_and_downgrade_guard(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        company = uuid.uuid4()
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            assert connection.execute(
                "SELECT count(*) FROM permissions WHERE code LIKE 'sales_receivables:%'"
            ).fetchone() == (2,)

            def receipt(number: int, total: str, status: str, reason: str | None) -> uuid.UUID:
                receipt_id = uuid.uuid4()
                annulled = status == "annulled" and reason is not None
                connection.execute(
                    _RECEIPT,
                    (
                        receipt_id,
                        company,
                        number,
                        total,
                        status,
                        f"key-{receipt_id}",
                        reason,
                        uuid.uuid4() if annulled else None,
                        "2026-11-25T10:00:00-06:00" if annulled else None,
                    ),
                )
                return receipt_id

            for number, total, status, reason in (
                (1, "0", "issued", None),  # total en cero
                (1, "10", "annulled", None),  # anulado sin motivo
                (1, "10", "issued", "Cheque rechazado"),  # vigente con datos de anulación
                (1, "10", "paid", None),  # estado fuera del catálogo
            ):
                with pytest.raises(errors.CheckViolation):
                    receipt(number, total, status, reason)
            receipt_id = receipt(1, "10", "issued", None)
            receipt(2, "5", "annulled", "Cheque rechazado")
            with pytest.raises(errors.UniqueViolation):
                receipt(1, "10", "issued", None)
            with pytest.raises(errors.CheckViolation):
                connection.execute(_PAYMENT, (company, receipt_id, 1, "card", None))
            with pytest.raises(errors.CheckViolation):
                connection.execute(_PAYMENT, (company, receipt_id, 1, "bitcoin", "x"))
            connection.execute(_PAYMENT, (company, receipt_id, 1, "cash", None))
        with pytest.raises(RuntimeError, match="2 recibos de cobro"):
            command.downgrade(config, "0139")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            connection.execute("DELETE FROM sales_receipt_payments")
            connection.execute("DELETE FROM sales_receipts")
        command.downgrade(config, "0139")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
