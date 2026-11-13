"""Rolling back the discrepancies revision never discards partial receptions or their records."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import Connection, connect
from psycopg.errors import CheckViolation

pytestmark = pytest.mark.e2e

PREVIOUS_REVISION = "0115"
NEW_COMMANDS = (
    "close_reception",
    "discrepancy_adjust",
    "discrepancy_claim",
    "discrepancy_release",
    "discrepancy_found",
    "discrepancy_dismiss",
    "resolve_discrepancy",
    "origin_count",
)


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    return config


def _dsn() -> str:
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return dsn


def _insert_transfer(connection: Connection, code: str, **columns: str) -> tuple[str, str]:
    """A transfer row; returns its id and its company's id."""
    company_id, origin_id = connection.execute(
        "SELECT company_id, id FROM warehouses WHERE branch_id IS NOT NULL ORDER BY id LIMIT 1"
    ).fetchone()
    destination_id = connection.execute(
        "SELECT id FROM warehouses WHERE company_id = %s AND id <> %s ORDER BY id LIMIT 1",
        (company_id, origin_id),
    ).fetchone()[0]
    user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
    names = ", ".join(columns)
    values = ", ".join(columns.values())
    extra_names = f", {names}" if names else ""
    extra_values = f", {values}" if values else ""
    transfer_id = connection.execute(
        "INSERT INTO inventory_transfers (id, company_id, code, origin_warehouse_id, "
        f"destination_warehouse_id, created_by_id, created_at, updated_at{extra_names}) "
        "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, now(), now()"
        f"{extra_values}) RETURNING id",
        (company_id, code, origin_id, destination_id, user_id),
    ).fetchone()[0]
    return str(transfer_id), str(company_id)


def _insert_detail_and_discrepancy(
    connection: Connection, transfer_id: str, company_id: str
) -> None:
    """A detail with a damage discrepancy. Foreign keys are skipped: only the guard matters."""
    user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
    connection.execute("SET session_replication_role = replica")
    detail_id = connection.execute(
        "INSERT INTO inventory_transfer_details (id, company_id, transfer_id, line_number, "
        "inventory_item_id, source_handling_unit_id, quantity_planned, quantity_dispatched, "
        "quantity_received, quantity_received_damaged, created_at, updated_at) "
        "VALUES (gen_random_uuid(), %s, %s, 1, gen_random_uuid(), gen_random_uuid(), 5, 5, 2, "
        "2, now(), now()) RETURNING id",
        (company_id, transfer_id),
    ).fetchone()[0]
    connection.execute(
        "INSERT INTO inventory_transfer_discrepancies (company_id, transfer_id, "
        "transfer_detail_id, kind, source, quantity, damage_type, notes, location_id, "
        "opened_by_id, opened_at) VALUES (%s, %s, %s, 'damage', 'receipt', 2, 'broken', "
        "'Cajas rotas al descargar', gen_random_uuid(), %s, now())",
        (company_id, transfer_id, detail_id, user_id),
    )
    connection.execute("SET session_replication_role = origin")


@pytest.mark.parametrize(
    "populated",
    ["discrepancy", "substitution", "discrepancy_row"],
)
def test_downgrade_refuses_to_drop_partial_receptions_and_discrepancies(populated: str) -> None:
    config = _alembic_config()
    with connect(_dsn()) as connection:
        if populated == "discrepancy":
            _insert_transfer(connection, f"GUARD-{populated}"[:40], status=f"'{populated}'")
        elif populated == "substitution":
            _insert_transfer(
                connection,
                "GUARD-SUBSTITUTION",
                assignment_substitution_code="'vehicle_unfit'",
                assignment_substitution_reason="'El vehículo aprobado no arranca'",
                assignment_substitution_by_id="(SELECT id FROM users LIMIT 1)",
                assignment_substitution_at="now()",
            )
        else:
            transfer_id, company_id = _insert_transfer(connection, "GUARD-ROW", status="'received'")
            _insert_detail_and_discrepancy(connection, transfer_id, company_id)
        before = connection.execute("SELECT count(*) FROM inventory_transfers").fetchone()

    with pytest.raises(RuntimeError, match="recepción parcial, discrepancias o sustituciones"):
        command.downgrade(config, PREVIOUS_REVISION)

    with connect(_dsn()) as connection:
        assert connection.execute("SELECT count(*) FROM inventory_transfers").fetchone() == before
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            (ScriptDirectory.from_config(config).get_current_head(),)
        ]
        assert connection.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'inventory_transfers' AND column_name = 'closed_at'"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT to_regclass('inventory_transfer_discrepancies')"
        ).fetchone() == ("inventory_transfer_discrepancies",)


def test_downgrade_with_only_ordinary_transfers_drops_and_restores_the_revision() -> None:
    config = _alembic_config()
    head = ScriptDirectory.from_config(config).get_current_head()
    with connect(_dsn()) as connection:
        transfer_id, company_id = _insert_transfer(connection, "GUARD-ORDINARY")
        received_id, _ = _insert_transfer(
            connection,
            "GUARD-RECEIVED",
            status="'received'",
            received_at="now() - interval '1 day'",
        )
        partial_id, _ = _insert_transfer(connection, "GUARD-PARTIAL", status="'partially_received'")
        cancelled_id, _ = _insert_transfer(connection, "GUARD-CANCELLED", status="'cancelled'")
        user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        for index, action in enumerate(NEW_COMMANDS):
            connection.execute(
                "INSERT INTO inventory_transfer_commands (id, company_id, transfer_id, action, "
                "idempotency_key, request_fingerprint, actor_id, created_at) "
                "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, now())",
                (company_id, transfer_id, action, f"guard-key-{index}", "0" * 64, user_id),
            )
        connection.execute(
            "INSERT INTO inventory_transfer_commands (id, company_id, transfer_id, action, "
            "idempotency_key, request_fingerprint, actor_id, created_at) "
            "VALUES (gen_random_uuid(), %s, %s, 'create', 'guard-create', %s, %s, now())",
            (company_id, transfer_id, "0" * 64, user_id),
        )

    command.downgrade(config, PREVIOUS_REVISION)

    with connect(_dsn()) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            (PREVIOUS_REVISION,)
        ]
        assert connection.execute(
            "SELECT to_regclass('inventory_transfer_discrepancies')"
        ).fetchone() == (None,)
        assert connection.execute(
            "SELECT count(*) FROM information_schema.columns WHERE table_name IN "
            "('inventory_transfers', 'inventory_transfer_details', "
            "'inventory_transfer_demand_allocations', 'inventory_transfer_receipts', "
            "'inventory_adjustments') AND column_name IN ('closed_at', 'approved_vehicle_id', "
            "'approved_driver_id', 'assignment_substitution_code', 'quantity_received_damaged', "
            "'quantity_surplus', 'quantity_damaged', 'condition', 'transfer_discrepancy_id')"
        ).fetchone() == (0,)
        # The new commands are gone, the old ones stay, and the transfers survive.
        assert connection.execute(
            "SELECT count(*) FROM inventory_transfer_commands WHERE action = ANY(%s)",
            (list(NEW_COMMANDS),),
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM inventory_transfer_commands WHERE action = 'create' "
            "AND idempotency_key = 'guard-create'"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM inventory_transfers WHERE id = ANY(%s::uuid[])",
            ([transfer_id, received_id],),
        ).fetchone() == (2,)
        # A transfer only partially received goes back to being "in transit".
        assert connection.execute(
            "SELECT status FROM inventory_transfers WHERE id = %s", (partial_id,)
        ).fetchone() == ("in_transit",)
        # Legacy data: an in-transit transfer that already received part of its goods.
        legacy_id, legacy_company = _insert_transfer(
            connection, "GUARD-LEGACY", status="'in_transit'"
        )
        untouched_id, _ = _insert_transfer(connection, "GUARD-UNTOUCHED", status="'in_transit'")
        connection.execute("SET session_replication_role = replica")
        connection.execute(
            "INSERT INTO inventory_transfer_details (id, company_id, transfer_id, line_number, "
            "inventory_item_id, source_handling_unit_id, quantity_planned, quantity_dispatched, "
            "quantity_received, created_at, updated_at) "
            "VALUES (gen_random_uuid(), %s, %s, 1, gen_random_uuid(), gen_random_uuid(), 5, 5, "
            "2, now(), now())",
            (legacy_company, legacy_id),
        )
        connection.execute("SET session_replication_role = origin")
        connection.commit()
        with pytest.raises(CheckViolation, match="ck_inventory_transfers_status"):
            connection.execute(
                "UPDATE inventory_transfers SET status = 'partially_received' WHERE id = %s",
                (transfer_id,),
            )

    command.upgrade(config, "head")

    with connect(_dsn()) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [(head,)]
        # Finished transfers get the time they closed back-filled; the others stay open.
        closed = dict(
            connection.execute(
                "SELECT id::text, closed_at IS NOT NULL FROM inventory_transfers "
                "WHERE id = ANY(%s::uuid[])",
                ([transfer_id, received_id, cancelled_id],),
            ).fetchall()
        )
        assert closed == {transfer_id: False, received_id: True, cancelled_id: True}
        # In-transit transfers that had received something become partially received.
        statuses = dict(
            connection.execute(
                "SELECT id::text, status FROM inventory_transfers WHERE id = ANY(%s::uuid[])",
                ([legacy_id, untouched_id],),
            ).fetchall()
        )
        assert statuses == {legacy_id: "partially_received", untouched_id: "in_transit"}
        assert connection.execute(
            "SELECT to_regclass('inventory_transfer_discrepancies')"
        ).fetchone() == ("inventory_transfer_discrepancies",)
        # The new status and the new commands are accepted again.
        connection.execute(
            "UPDATE inventory_transfers SET status = 'partially_received' WHERE id = %s",
            (transfer_id,),
        )
