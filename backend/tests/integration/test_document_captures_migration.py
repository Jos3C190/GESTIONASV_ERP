"""The capture migration reaches every company and never rolls back over real data."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import connect

pytestmark = pytest.mark.integration


def test_backfills_each_company_and_refuses_to_roll_back_over_captures(
    rebuild_test_database: Callable[..., None],
) -> None:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    rebuild_test_database()
    try:
        command.downgrade(config, "0104")
        with connect(dsn) as connection:
            assert connection.execute("SELECT to_regclass('document_captures')").fetchone() == (
                None,
            )
            assert connection.execute(
                "SELECT count(*) FROM document_categories WHERE code = 'driver_license_back'"
            ).fetchone() == (0,)
            assert connection.execute(
                "SELECT count(*) FROM permissions WHERE code = 'drivers:license_override'"
            ).fetchone() == (0,)

        command.upgrade(config, "0105")
        with connect(dsn) as connection:
            companies = connection.execute("SELECT count(*) FROM companies").fetchone()[0]
            assert companies > 0
            assert connection.execute(
                "SELECT count(*), bool_or(requires_expiry), bool_or(compliance_required) "
                "FROM document_categories WHERE code = 'driver_license_back'"
            ).fetchone() == (companies, False, False)
            assert connection.execute(
                "SELECT count(*) FROM role_permissions rp "
                "JOIN permissions p ON p.id = rp.permission_id "
                "JOIN roles r ON r.id = rp.role_id "
                "WHERE p.code = 'drivers:license_override' AND r.name = 'SUPER_ADMIN'"
            ).fetchone() == (1,)
            company_id = connection.execute("SELECT id FROM companies LIMIT 1").fetchone()[0]
            connection.execute(
                "INSERT INTO document_captures (company_id, kind, owner_type, owner_id, expires_at) "
                "VALUES (%s, 'driver_license', 'driver', gen_random_uuid(), now())",
                (company_id,),
            )

        with pytest.raises(RuntimeError, match="no se revierte"):
            command.downgrade(config, "0104")

        with connect(dsn) as connection:
            assert connection.execute("SELECT count(*) FROM document_captures").fetchone() == (1,)
    finally:
        # Subsequent integration tests expect the canonical seeded test database.
        rebuild_test_database()
