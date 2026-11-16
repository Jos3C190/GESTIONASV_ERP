"""0120 agrega la clasificación fiscal de productos y el código de Hacienda de las unidades."""

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

_PRODUCT = (
    "INSERT INTO products (company_id, sku, id_category, name, purchase_unit, sale_unit, "
    "tax_treatment, dte_item_type, additional_tax_codes) "
    "VALUES (%s, %s, 1, 'Producto', 1, 1, %s, %s, %s)"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def test_checks_reject_invalid_classifications(rebuild_test_database: Callable[..., None]) -> None:
    _, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        connection.execute(_PRODUCT, (company, "OK-1", "taxed", None, ["D1", "C8"]))
        connection.execute(_PRODUCT, (company, "OK-2", "exempt", "2", []))
        for index, values in enumerate(
            (
                ("zero_rated", None, []),  # tratamiento desconocido
                ("taxed", "4", []),  # tipo 4 no es de producto
                ("exempt", None, ["D1"]),  # tributos solo en gravados
                ("taxed", None, ["20"]),  # el IVA no es tributo adicional
            )
        ):
            with pytest.raises(errors.CheckViolation):
                connection.execute(_PRODUCT, (company, f"BAD-{index}", *values))
        with pytest.raises(errors.CheckViolation):
            connection.execute(
                "INSERT INTO company_units (company_id, unit_id, hacienda_unit_code) "
                "VALUES (%s, 1, 'AB')",
                (company,),
            )


def test_downgrade_refuses_to_lose_classification(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            connection.execute(_PRODUCT, (company, "EX-1", "exempt", None, []))
        with pytest.raises(RuntimeError, match="clasificación fiscal"):
            command.downgrade(config, "0119")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM products WHERE company_id = %s", (company,))
        command.downgrade(config, "0119")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
