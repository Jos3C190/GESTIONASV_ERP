"""0139: datos fiscales de la compra, renta de compras por empresa y la guarda del downgrade."""

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

_PURCHASE = (
    "INSERT INTO purchases (id, company_id, code, purchase_order_id, supplier_id, warehouse_id, "
    "created_by_id, currency) VALUES (%s, %s, %s, gen_random_uuid(), 1, gen_random_uuid(), "
    "gen_random_uuid(), 'USD')"
)
_FISCAL = (
    "UPDATE purchases SET fiscal_document_class = %s, fiscal_document_type = %s, "
    "fiscal_document_number = %s, fiscal_control_number = %s, fiscal_seal = %s, "
    "renta_operation_type = 1, renta_classification = 1, renta_sector = %s, "
    "renta_cost_type = 5, fiscal_recorded_by_id = gen_random_uuid(), fiscal_recorded_at = now() "
    "WHERE id = %s"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def test_fiscal_books_schema_and_downgrade_guard(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        company = uuid.uuid4()
        purchase = uuid.uuid4()
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            assert connection.execute(
                "SELECT count(*) FROM permissions WHERE code LIKE 'fiscal_books:%'"
            ).fetchone() == (2,)
            connection.execute(_PURCHASE, (purchase, company, "CMP-1"))
            for values in (
                (2, "03", "145501", None, None, 2),  # clase fuera del catálogo
                (1, "01", "145501", None, None, 2),  # una factura no da crédito fiscal
                (1, "03", "  ", None, None, 2),  # sin número
                (1, "03", "145501", None, None, 5),  # sector fuera del catálogo
                (4, "03", "ABC", None, None, 2),  # DTE sin número de control ni sello
            ):
                with pytest.raises(errors.CheckViolation):
                    connection.execute(_FISCAL, (*values, purchase))
            connection.execute(
                _FISCAL,
                (
                    4,
                    "03",
                    "6C7EF177-8C52-41EF-B073-B2968DA0652C",
                    "DTE-03-M001P001-000000000000003",
                    "2026A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8",
                    2,
                    purchase,
                ),
            )
            connection.execute(
                "INSERT INTO fiscal_book_settings (company_id) VALUES (%s)", (company,)
            )
            with pytest.raises(errors.CheckViolation):
                connection.execute(
                    "UPDATE fiscal_book_settings SET purchase_cost_type = 10 WHERE company_id = %s",
                    (company,),
                )
        with pytest.raises(RuntimeError, match="1 compras con datos fiscales"):
            command.downgrade(config, "0138")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            connection.execute("DELETE FROM purchases WHERE id = %s", (purchase,))
        command.downgrade(config, "0138")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
