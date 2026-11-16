"""0123: márgenes, escalas por volumen sin traslape, topes por rol y guarda del downgrade."""

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

_SCALE = (
    "INSERT INTO sales_volume_discounts (company_id, price_list_id, product_id, variant_id, "
    "unit_id, min_quantity, discount_percent, valid_from, valid_to) "
    "VALUES (%s, %s, 1, NULL, 1, %s, %s, %s, %s)"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def test_checks_and_overlapping_scales(rebuild_test_database: Callable[..., None]) -> None:
    _, dsn = _config()
    rebuild_test_database()
    company, price_list = uuid.uuid4(), uuid.uuid4()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        connection.execute(_SCALE, (company, price_list, 10, 3, "2026-01-01", None))
        connection.execute(_SCALE, (company, price_list, 50, 6, "2026-01-01", None))
        with pytest.raises(errors.ExclusionViolation):
            connection.execute(_SCALE, (company, price_list, 10, 4, "2026-06-01", None))
        for quantity, percent in ((0, 3), (5, 0), (5, 101)):
            with pytest.raises(errors.CheckViolation):
                connection.execute(
                    _SCALE, (company, price_list, quantity, percent, "2026-01-01", None)
                )
        with pytest.raises(errors.CheckViolation):
            connection.execute(
                "INSERT INTO sales_discount_policies (company_id, role_id, max_line_discount_percent) "
                "VALUES (%s, %s, 120)",
                (company, uuid.uuid4()),
            )
        with pytest.raises(errors.CheckViolation):
            connection.execute(
                "INSERT INTO sales_price_lists (company_id, code, name, prices_include_vat, "
                "target_margin_percent) VALUES (%s, 'X', 'Lista', true, 96)",
                (company,),
            )


def test_downgrade_refuses_to_drop_discount_data(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            connection.execute(
                "INSERT INTO sales_discount_policies (company_id, role_id, max_line_discount_percent) "
                "VALUES (%s, %s, 5)",
                (company, uuid.uuid4()),
            )
        with pytest.raises(RuntimeError, match="márgenes, escalas"):
            command.downgrade(config, "0122")
        with connect(dsn, autocommit=True) as connection:
            connection.execute(
                "DELETE FROM sales_discount_policies WHERE company_id = %s", (company,)
            )
        command.downgrade(config, "0122")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
