"""0124: cotización rediseñada, sus reglas en la base y la guarda que protege cotizaciones."""

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

_QUOTE = (
    "INSERT INTO sales_quotations (id, company_id, branch_id, customer_id, code, "
    "quotation_date, valid_until, created_by_id, document_type, prices_include_vat, status, "
    "issued_at, issued_by_id, customer_response_at, customer_response_by_id, rejection_reason, "
    "global_discount_percent) "
    "VALUES (%s, %s, %s, %s, %s, '2026-11-16', '2026-12-01', %s, %s, true, %s, %s, %s, %s, %s, "
    "%s, %s)"
)
_LINE = (
    "INSERT INTO sales_quotation_lines (company_id, quotation_id, line_number, product_id, "
    "inventory_item_id, unit_id, base_unit_id, unit_factor, quantity, quantity_base, "
    "product_sku, product_name, unit_name, base_unit_name, unit_price, line_total, list_price, "
    "price_overridden, discount_percent, tax_treatment, item_type, document_unit_price) "
    "VALUES (%s, %s, %s, 1, gen_random_uuid(), 1, 1, 1, 1, 1, 'SKU', 'Producto', 'Unidad', "
    "'Unidad', 10, 10, %s, %s, %s, %s, %s, 10)"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def _quote(
    connection: Connection[tuple[object, ...]],
    company: uuid.UUID,
    *,
    status: str = "draft",
    document: str = "01",
    issued: bool = False,
    responded: bool = False,
    rejection: str | None = None,
    discount: str = "0",
) -> uuid.UUID:
    quote, user = uuid.uuid4(), uuid.uuid4()
    connection.execute(
        _QUOTE,
        (
            quote,
            company,
            uuid.uuid4(),
            uuid.uuid4(),
            f"COT-{quote.hex[:8]}",
            user,
            document,
            status,
            "2026-11-16T10:00:00-06:00" if issued else None,
            user if issued else None,
            "2026-11-17T10:00:00-06:00" if responded else None,
            user if responded else None,
            rejection,
            discount,
        ),
    )
    return quote


def test_quotation_rules(rebuild_test_database: Callable[..., None]) -> None:
    _, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        _quote(connection, company, status="pending_authorization")
        _quote(connection, company, status="issued", issued=True)
        _quote(connection, company, status="accepted", issued=True, responded=True)
        quote = _quote(
            connection,
            company,
            status="rejected",
            issued=True,
            responded=True,
            rejection="Precio alto",
        )
        invalid: list[dict[str, object]] = [
            {"status": "confirmed"},
            {"document": "11"},
            {"discount": "101"},
            {"status": "issued"},
            {"status": "draft", "issued": True},
            {"status": "accepted", "issued": True},
            {"status": "rejected", "issued": True, "responded": True},
            {"status": "issued", "issued": True, "responded": True},
        ]
        for kwargs in invalid:
            with pytest.raises(errors.CheckViolation):
                _quote(connection, company, **kwargs)  # type: ignore[arg-type]

        connection.execute(_LINE, (company, quote, 1, "10", False, "5", "taxed", "1"))
        connection.execute(_LINE, (company, quote, 2, None, True, "0", "exempt", "2"))
        bad_lines = [
            (None, False, "0", "taxed", "1"),
            ("10", False, "120", "taxed", "1"),
            ("10", False, "0", "zero", "1"),
            ("10", False, "0", "taxed", "5"),
        ]
        for number, values in enumerate(bad_lines, start=3):
            with pytest.raises(errors.CheckViolation):
                connection.execute(_LINE, (company, quote, number, *values))

        with pytest.raises(errors.CheckViolation):
            connection.execute(
                "INSERT INTO sales_settings (company_id, quotation_validity_days) VALUES (%s, 0)",
                (company,),
            )
        connection.execute("INSERT INTO sales_settings (company_id) VALUES (%s)", (company,))
        days = connection.execute(
            "SELECT quotation_validity_days FROM sales_settings WHERE company_id = %s", (company,)
        ).fetchone()
        assert days == (15,)
        granted = connection.execute(
            "SELECT count(*) FROM role_permissions rp "
            "JOIN permissions p ON p.id = rp.permission_id "
            "JOIN roles r ON r.id = rp.role_id "
            "WHERE r.name = 'SUPER_ADMIN' AND p.code IN "
            "('sales_discounts:authorize', 'sales_prices:override')"
        ).fetchone()
        assert granted == (2,)


def test_migration_refuses_when_quotations_exist(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            _quote(connection, company)
        with pytest.raises(RuntimeError, match="1 cotizaciones guardadas"):
            command.downgrade(config, "0123")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            connection.execute("DELETE FROM sales_quotations WHERE company_id = %s", (company,))
            connection.execute("INSERT INTO sales_settings (company_id) VALUES (%s)", (company,))
        with pytest.raises(RuntimeError, match="configuraciones de ventas"):
            command.downgrade(config, "0123")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales_settings WHERE company_id = %s", (company,))
        command.downgrade(config, "0123")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            connection.execute(
                "INSERT INTO sales_quotations (company_id, branch_id, customer_id, code, "
                "quotation_date, valid_until, created_by_id) "
                "VALUES (%s, %s, %s, 'COT-OLD', '2026-11-16', '2026-12-01', %s)",
                (company, uuid.uuid4(), uuid.uuid4(), uuid.uuid4()),
            )
        with pytest.raises(RuntimeError, match="1 cotizaciones guardadas"):
            command.upgrade(config, "head")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales_quotations WHERE company_id = %s", (company,))
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
