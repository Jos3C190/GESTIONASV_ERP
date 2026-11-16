"""0118 carga los catálogos de Hacienda, codifica la geografía y crea la base del emisor."""

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


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def _scalar(connection, sql: str, params: tuple[object, ...] = ()) -> object:
    row = connection.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


def test_upgrade_loads_catalogs_codes_geography_and_enforces_codes(
    rebuild_test_database: Callable[..., None],
) -> None:
    _, dsn = _config()
    rebuild_test_database()
    with connect(dsn, autocommit=True) as connection:
        assert _scalar(connection, "SELECT count(*) FROM hacienda_catalog_items") == 1681
        assert (
            _scalar(
                connection,
                "SELECT count(*) FROM hacienda_catalog_items WHERE catalog_code = 'CAT-019'",
            )
            == 774
        )
        for table, total in (
            ("geographic_departments", 14),
            ("municipalities", 44),
            ("districts", 262),
        ):
            assert _scalar(connection, f"SELECT count(hacienda_code) FROM {table}") == total
        assert (
            _scalar(
                connection,
                "SELECT x.hacienda_code FROM districts x "
                "JOIN municipalities m ON m.id = x.municipality_id "
                "WHERE m.name = 'La Unión Norte' AND x.name = 'San José La Fuente'",
            )
            == "15"
        )

        company, branch = uuid.uuid4(), uuid.uuid4()
        connection.execute("SET session_replication_role = replica")
        with pytest.raises(errors.CheckViolation):
            connection.execute(
                "INSERT INTO fiscal_establishments (company_id, branch_id, establishment_type, "
                "code) VALUES (%s, %s, '01', 'M001')",
                (company, branch),
            )
        with pytest.raises(errors.CheckViolation):
            connection.execute(
                "INSERT INTO company_dte_document_types (company_id, document_type, "
                "certification_status) VALUES (%s, '01', 'approved')",
                (company,),
            )
        with pytest.raises(errors.CheckViolation):
            connection.execute(
                "INSERT INTO company_dte_document_types (company_id, document_type) "
                "VALUES (%s, '02')",
                (company,),
            )


def test_downgrade_refuses_when_an_issuer_is_configured(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            connection.execute(
                "INSERT INTO company_fiscal_profiles (company_id) VALUES (%s)", (company,)
            )
        with pytest.raises(RuntimeError, match="configuración fiscal"):
            command.downgrade(config, "0117")
        with connect(dsn, autocommit=True) as connection:
            connection.execute(
                "DELETE FROM company_fiscal_profiles WHERE company_id = %s", (company,)
            )
        command.downgrade(config, "0117")
        with connect(dsn) as connection:
            assert (
                _scalar(
                    connection,
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_name = 'hacienda_catalog_items'",
                )
                == 0
            )
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
