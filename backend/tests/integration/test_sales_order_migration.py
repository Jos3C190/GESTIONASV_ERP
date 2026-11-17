"""0125: pedido de venta, sus reglas en la base y la guarda que protege ventas existentes."""

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

_ORDER = (
    "INSERT INTO sales (company_id, branch_id, customer_id, code, subtotal, total, status, "
    "created_by_id, confirmed_by_id, confirmed_at, document_type, prices_include_vat, "
    "promised_date, delivery_mode, delivery_address_id, delivery_address_text, payment_terms, "
    "credit_days) VALUES (%s, %s, %s, %s, 0, 0, %s, %s, %s, %s, '01', true, '2026-11-20', "
    "%s, %s, %s, %s, %s)"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def _order(
    connection: Connection[tuple[object, ...]],
    company: uuid.UUID,
    *,
    status: str = "draft",
    confirmed: bool = False,
    mode: str = "pickup",
    address: bool = False,
    terms: str = "cash",
    days: int = 0,
) -> None:
    user = uuid.uuid4()
    connection.execute(
        _ORDER,
        (
            company,
            uuid.uuid4(),
            uuid.uuid4(),
            f"PED-{uuid.uuid4().hex[:8]}",
            status,
            user,
            user if confirmed else None,
            "2026-11-16T10:00:00-06:00" if confirmed else None,
            mode,
            uuid.uuid4() if address else None,
            "Col. Escalón, San Salvador" if address else None,
            terms,
            days,
        ),
    )


def test_order_rules(rebuild_test_database: Callable[..., None]) -> None:
    _, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        _order(connection, company)
        _order(connection, company, status="pending_authorization")
        _order(connection, company, status="confirmed", confirmed=True)
        _order(connection, company, mode="delivery", address=True, terms="credit", days=30)
        invalid: list[dict[str, object]] = [
            {"status": "issued"},
            {"status": "confirmed"},
            {"status": "draft", "confirmed": True},
            {"mode": "delivery"},
            {"mode": "pickup", "address": True},
            {"mode": "courier"},
            {"terms": "cash", "days": 15},
            {"terms": "credit", "days": 400},
        ]
        for kwargs in invalid:
            with pytest.raises(errors.CheckViolation):
                _order(connection, company, **kwargs)  # type: ignore[arg-type]


def test_migration_refuses_when_sales_exist(rebuild_test_database: Callable[..., None]) -> None:
    config, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            _order(connection, company)
        with pytest.raises(RuntimeError, match="sales: 1"):
            command.downgrade(config, "0124")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales WHERE company_id = %s", (company,))
        command.downgrade(config, "0124")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            connection.execute(
                "INSERT INTO sales (company_id, branch_id, customer_id, quotation_id, code, "
                "subtotal, total, created_by_id) VALUES (%s, %s, %s, %s, 'VTA-OLD', 0, 0, %s)",
                (company, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()),
            )
        with pytest.raises(RuntimeError, match="sales: 1"):
            command.upgrade(config, "head")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales WHERE company_id = %s", (company,))
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
