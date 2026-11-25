"""0137: la nota de remisión pertenece a un traslado y no a un pedido; guarda del downgrade."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg import connect, errors
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.integration

_DOC = (
    "INSERT INTO sales_fiscal_documents (id, company_id, branch_id, sale_id, transfer_id, "
    "establishment_id, point_of_sale_id, document_type, mode, status, idempotency_key, total, "
    "issuer_snapshot, request_payload, created_by_id) VALUES (%s, %s, gen_random_uuid(), %s, %s, "
    "gen_random_uuid(), gen_random_uuid(), %s, 'simulated', %s, %s, 10, %s, %s, gen_random_uuid())"
)


def _config() -> tuple[Config, str]:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return config, dsn


def test_remission_belongs_to_a_transfer(rebuild_test_database: Callable[..., None]) -> None:
    config, dsn = _config()
    rebuild_test_database()
    try:
        company = uuid.uuid4()
        transfer = uuid.uuid4()
        with connect(dsn, autocommit=True) as connection:
            connection.execute("SET session_replication_role = replica")

            def insert(
                document_type: str,
                *,
                sale: uuid.UUID | None,
                transfer_id: uuid.UUID | None,
                status: str = "pending",
            ) -> None:
                connection.execute(
                    _DOC,
                    (
                        uuid.uuid4(),
                        company,
                        sale,
                        transfer_id,
                        document_type,
                        status,
                        f"erp-{uuid.uuid4()}",
                        Jsonb({}),
                        Jsonb({}),
                    ),
                )

            # La nota va con su traslado y sin pedido; los demás tipos, al revés.
            for document_type, sale, transfer_id in (
                ("04", None, None),
                ("04", uuid.uuid4(), transfer),
                ("01", None, transfer),
                ("01", None, None),
            ):
                with pytest.raises(errors.CheckViolation):
                    insert(document_type, sale=sale, transfer_id=transfer_id)
            insert("04", sale=None, transfer_id=transfer)
            # Una sola nota vigente por traslado; una rechazada no cuenta.
            with pytest.raises(errors.UniqueViolation):
                insert("04", sale=None, transfer_id=transfer)
            insert("04", sale=None, transfer_id=transfer, status="rejected")
        with pytest.raises(RuntimeError, match="2 notas de remisión"):
            command.downgrade(config, "0136")
        with connect(dsn, autocommit=True) as connection:
            connection.execute("DELETE FROM sales_fiscal_documents WHERE document_type = '04'")
        command.downgrade(config, "0136")
        command.upgrade(config, "head")
    finally:
        rebuild_test_database()
