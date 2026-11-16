"""0122 crea las listas de precios: vigencias sin traslape y una sola predeterminada."""

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

_LIST = (
    "INSERT INTO sales_price_lists (id, company_id, code, name, prices_include_vat, is_default) "
    "VALUES (%s, %s, %s, %s, true, %s)"
)
_ITEM = (
    "INSERT INTO sales_price_list_items (company_id, price_list_id, product_id, variant_id, "
    "unit_id, branch_id, price, valid_from, valid_to) VALUES (%s, %s, 1, %s, 1, %s, %s, %s, %s)"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def test_validity_never_overlaps_and_one_default(
    rebuild_test_database: Callable[..., None],
) -> None:
    _, dsn = _config()
    rebuild_test_database()
    company, price_list, branch = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        connection.execute(_LIST, (price_list, company, "MOSTRADOR", "Mostrador", True))
        with pytest.raises(errors.UniqueViolation):
            connection.execute(_LIST, (uuid.uuid4(), company, "MAYOREO", "Mayoreo", True))
        with pytest.raises(errors.CheckViolation):
            connection.execute(_LIST, (uuid.uuid4(), company, "mayoreo", "Mayoreo", False))

        connection.execute(_ITEM, (company, price_list, None, None, 1, "2026-01-01", "2026-06-30"))
        connection.execute(_ITEM, (company, price_list, None, None, 2, "2026-07-01", None))
        with pytest.raises(errors.ExclusionViolation):  # traslapa con la vigencia abierta
            connection.execute(_ITEM, (company, price_list, None, None, 3, "2026-12-01", None))
        # otra sucursal u otra variante son claves distintas
        connection.execute(_ITEM, (company, price_list, None, branch, 4, "2026-12-01", None))
        connection.execute(_ITEM, (company, price_list, uuid.uuid4(), None, 5, "2026-12-01", None))
        with pytest.raises(errors.ExclusionViolation):
            connection.execute(_ITEM, (company, price_list, None, branch, 6, "2027-01-01", None))
        with pytest.raises(errors.CheckViolation):
            connection.execute(
                _ITEM, (company, price_list, None, None, -1, "2025-01-01", "2025-01-31")
            )
        with pytest.raises(errors.CheckViolation):
            connection.execute(
                _ITEM, (company, price_list, None, None, 1, "2025-02-01", "2025-01-31")
            )


def test_downgrade_refuses_to_drop_price_lists(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            connection.execute(_LIST, (uuid.uuid4(), company, "MOSTRADOR", "Mostrador", True))
        with pytest.raises(RuntimeError, match="listas de precios"):
            command.downgrade(config, "0121")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales_price_lists WHERE company_id = %s", (company,))
        command.downgrade(config, "0121")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
