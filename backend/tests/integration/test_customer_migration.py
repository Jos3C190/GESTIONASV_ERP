"""0119 amplía los clientes con identidad fiscal y protege sus datos al revertir."""

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

_INSERT = (
    "INSERT INTO sales_customers (id, company_id, code, name, created_by_id, updated_by_id, "
    "customer_type, taxpayer_category, document_type, document_number, nrc, country_code, "
    "is_generic, branch_id) VALUES (%s, %s, %s, 'Cliente', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def _row(company: uuid.UUID, code: str, **values: object) -> tuple[object, ...]:
    actor = uuid.uuid4()
    return (
        uuid.uuid4(),
        company,
        code,
        actor,
        actor,
        values.get("customer_type", "final_consumer"),
        values.get("taxpayer_category"),
        values.get("document_type"),
        values.get("document_number"),
        values.get("nrc"),
        values.get("country_code"),
        values.get("is_generic", False),
        values.get("branch_id"),
    )


def test_checks_and_unique_indexes(rebuild_test_database: Callable[..., None]) -> None:
    _, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    with connect(dsn, autocommit=True) as connection:
        connection.execute("SET session_replication_role = replica")
        connection.execute(
            _INSERT,
            _row(
                company,
                "CLI-1",
                customer_type="taxpayer",
                taxpayer_category="other",
                document_type="36",
                document_number="06140101011011",
                nrc="1234567",
            ),
        )
        with pytest.raises(errors.UniqueViolation):
            connection.execute(
                _INSERT,
                _row(
                    company,
                    "CLI-2",
                    customer_type="taxpayer",
                    taxpayer_category="other",
                    nrc="1234567",
                ),
            )
        rejected = (
            {"customer_type": "taxpayer"},  # falta la categoría
            {"taxpayer_category": "large"},  # categoría sin ser contribuyente
            {"nrc": "12-3"},
            {"document_type": "36"},  # tipo sin número
            {"customer_type": "foreign"},  # extranjero sin país
            {"is_generic": True},  # genérico sin sucursal
        )
        for index, values in enumerate(rejected):
            with pytest.raises(errors.CheckViolation):
                connection.execute(_INSERT, _row(company, f"BAD-{index}", **values))
        branch = uuid.uuid4()
        connection.execute(_INSERT, _row(company, "CF-1", is_generic=True, branch_id=branch))
        with pytest.raises(errors.UniqueViolation):
            connection.execute(_INSERT, _row(company, "CF-2", is_generic=True, branch_id=branch))


def test_downgrade_refuses_to_lose_fiscal_data(
    rebuild_test_database: Callable[..., None],
) -> None:
    config, dsn = _config()
    rebuild_test_database()
    company = uuid.uuid4()
    try:
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")
            connection.execute(_INSERT, _row(company, "CLI-X", nrc="7654321"))
        with pytest.raises(RuntimeError, match="datos fiscales"):
            command.downgrade(config, "0118")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales_customers WHERE company_id = %s", (company,))
        command.downgrade(config, "0118")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
