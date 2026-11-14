"""0117 removes import VAT and the automatic mode from retaceos, keeping uploaded files."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import connect

pytestmark = pytest.mark.integration

REMOVED_COLUMNS = {"import_vat", "vat_rate", "dai_rate", "calculation_mode"}


def _columns(connection) -> set[str]:
    rows = connection.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'retaceos'"
    ).fetchall()
    return {row[0] for row in rows}


def _check(connection, name: str) -> str | None:
    row = connection.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = %s", (name,)
    ).fetchone()
    return row[0] if row else None


def test_upgrade_deletes_vat_costs_keeps_documents_and_downgrade_restores_columns(
    rebuild_test_database: Callable[..., None],
) -> None:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    rebuild_test_database()
    try:
        command.downgrade(config, "0116")
        company, retaceo, vat_cost, freight_cost, asset = (uuid.uuid4() for _ in range(5))
        with connect(dsn) as connection:
            assert _columns(connection) >= REMOVED_COLUMNS
            assert "import_vat" in (_check(connection, "ck_retaceo_costs_classification") or "")
            # Seed rows without their parents: FK triggers are skipped in this session only, so
            # the migration itself (another session) still runs with cascades enabled.
            connection.execute("SET session_replication_role = replica")
            connection.execute(
                "INSERT INTO retaceos (id, company_id, code, purchase_id, branch_id, "
                "created_by_id, currency, total_fob, total_freight, total_expenses, total_dai, "
                "import_vat, total_cost, status, calculation_mode, dai_rate, vat_rate) "
                "VALUES (%s, %s, 'MIG-0117', %s, %s, %s, 'USD', 100, 10, 0, 5, 13, 115, 'draft', "
                "'automatic', 5, 13)",
                (retaceo, company, uuid.uuid4(), uuid.uuid4(), uuid.uuid4()),
            )
            for cost_id, kind, amount in (
                (vat_cost, "import_vat", 13),
                (freight_cost, "freight", 10),
            ):
                connection.execute(
                    "INSERT INTO retaceo_costs (id, company_id, retaceo_id, classification, "
                    "title, amount) VALUES (%s, %s, %s, %s, %s, %s)",
                    (cost_id, company, retaceo, kind, f"Costo {kind}", amount),
                )
            connection.execute(
                "INSERT INTO retaceo_cost_allocations (company_id, retaceo_cost_id, "
                "purchase_detail_id, amount) VALUES (%s, %s, %s, 10)",
                (company, freight_cost, uuid.uuid4()),
            )
            connection.execute(
                "INSERT INTO document_assets (id, company_id, original_filename, extension, "
                "declared_content_type, size_bytes, checksum_sha256, bucket, object_key, status, "
                "upload_expires_at) VALUES (%s, %s, 'iva.pdf', 'pdf', 'application/pdf', 10, %s, "
                "'test', %s, 'active', now())",
                (asset, company, "a" * 64, f"retaceo/{asset}.pdf"),
            )
            connection.execute(
                "INSERT INTO retaceo_cost_documents (company_id, retaceo_cost_id, document_id, "
                "file_name, file_type) VALUES (%s, %s, %s, 'iva.pdf', 'application/pdf')",
                (company, vat_cost, asset),
            )

        command.upgrade(config, "0117")

        with connect(dsn) as connection:
            assert not REMOVED_COLUMNS & _columns(connection)
            remaining = connection.execute(
                "SELECT classification FROM retaceo_costs WHERE retaceo_id = %s", (retaceo,)
            ).fetchall()
            assert remaining == [("freight",)]
            assert (
                connection.execute(
                    "SELECT count(*) FROM retaceo_costs WHERE classification = 'import_vat'"
                ).fetchone()[0]
                == 0
            )
            # Links of the deleted cost go away; the other cost keeps its distribution.
            assert connection.execute("SELECT count(*) FROM retaceo_cost_documents").fetchone() == (
                0,
            )
            assert connection.execute(
                "SELECT count(*) FROM retaceo_cost_allocations WHERE retaceo_cost_id = %s",
                (freight_cost,),
            ).fetchone() == (1,)
            # The uploaded file is not deleted, only unlinked.
            assert connection.execute(
                "SELECT count(*) FROM document_assets WHERE id = %s", (asset,)
            ).fetchone() == (1,)
            classification = _check(connection, "ck_retaceo_costs_classification") or ""
            assert "import_vat" not in classification
            assert all(kind in classification for kind in ("freight", "expense", "dai"))
            assert "import_vat" not in (_check(connection, "ck_retaceos_amounts_nonnegative") or "")
            assert _check(connection, "ck_retaceos_calculation_mode") is None
            assert _check(connection, "ck_retaceos_calculation_rates") is None
            assert "total_fob" in (_check(connection, "ck_retaceos_total_cost") or "")
            assert connection.execute(
                "SELECT total_cost FROM retaceos WHERE id = %s", (retaceo,)
            ).fetchone() == (115,)

        command.downgrade(config, "0116")

        with connect(dsn) as connection:
            assert _columns(connection) >= REMOVED_COLUMNS
            row = connection.execute(
                "SELECT calculation_mode, dai_rate, vat_rate, import_vat FROM retaceos "
                "WHERE id = %s",
                (retaceo,),
            ).fetchone()
            assert row == ("manual", None, None, 0)
            assert "import_vat" in (_check(connection, "ck_retaceo_costs_classification") or "")
            assert _check(connection, "ck_retaceos_calculation_mode") is not None
            assert _check(connection, "ck_retaceos_calculation_rates") is not None
        command.upgrade(config, "head")
    finally:
        # Subsequent integration tests expect the canonical seeded test database.
        rebuild_test_database()
