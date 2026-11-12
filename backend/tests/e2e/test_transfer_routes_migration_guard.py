"""Rolling back the transfer routes revision never discards transfers that depend on it."""

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

PREVIOUS_REVISION = "0113"
NEW_PERMISSIONS = ("inventory:transfer_approve", "inventory:transfer_settings")


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    return config


def _dsn() -> str:
    dsn = os.environ["DATABASE_URL_SYNC"].replace("postgresql+psycopg://", "postgresql://")
    assert dsn.rsplit("/", 1)[-1].split("?", 1)[0] == "erp_db_test"
    return dsn


def _insert_transfer(connection: Connection, code: str, **columns: str) -> str:
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
    return str(
        connection.execute(
            "INSERT INTO inventory_transfers (id, company_id, code, origin_warehouse_id, "
            f"destination_warehouse_id, created_by_id, created_at, updated_at{extra_names}) "
            "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, now(), now()"
            f"{extra_values}) RETURNING id",
            (company_id, code, origin_id, destination_id, user_id),
        ).fetchone()[0]
    )


def _branch_columns(status: str, route: str = "branch_to_branch") -> dict[str, str]:
    columns = {
        "status": f"'{status}'",
        "route_type": f"'{route}'",
        "requires_approval": "true",
        "approval_round": "1",
        "submitted_by_id": "(SELECT id FROM users LIMIT 1)",
        "submitted_at": "now()",
    }
    if status == "approved":
        columns["approved_by_id"] = "(SELECT id FROM users LIMIT 1)"
        columns["approved_at"] = "now()"
    return columns


@pytest.mark.parametrize(
    "populated",
    ["pending_approval", "approved", "cancelled_branch_to_central", "preparation_branch"],
)
def test_downgrade_refuses_transfers_that_use_branch_routes_or_approval(populated: str) -> None:
    config = _alembic_config()
    with connect(_dsn()) as connection:
        if populated in {"pending_approval", "approved"}:
            columns = _branch_columns(populated)
        elif populated == "cancelled_branch_to_central":
            columns = _branch_columns("cancelled", "branch_to_central")
        else:
            columns = {"route_type": "'branch_to_branch'"}
        _insert_transfer(connection, f"GUARD-{populated}"[:40], **columns)
        before = connection.execute("SELECT count(*) FROM inventory_transfers").fetchone()

    with pytest.raises(RuntimeError, match="rutas entre sucursales o aprobaciones"):
        command.downgrade(config, PREVIOUS_REVISION)

    with connect(_dsn()) as connection:
        assert connection.execute("SELECT count(*) FROM inventory_transfers").fetchone() == before
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            (ScriptDirectory.from_config(config).get_current_head(),)
        ]
        assert connection.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'inventory_transfers' AND column_name = 'route_type'"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT to_regclass('inventory_transfer_settings')"
        ).fetchone() == ("inventory_transfer_settings",)


def test_downgrade_with_only_central_transfers_drops_and_restores_the_revision() -> None:
    config = _alembic_config()
    head = ScriptDirectory.from_config(config).get_current_head()
    with connect(_dsn()) as connection:
        transfer_id = _insert_transfer(connection, "GUARD-CENTRAL")
        company_id = connection.execute("SELECT company_id FROM warehouses LIMIT 1").fetchone()[0]
        user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        connection.execute(
            "INSERT INTO inventory_transfer_settings (company_id, allow_branch_to_branch) "
            "VALUES (%s, true)",
            (company_id,),
        )
        connection.execute(
            "INSERT INTO inventory_transfer_commands (id, company_id, transfer_id, action, "
            "idempotency_key, request_fingerprint, actor_id, created_at) "
            "VALUES (gen_random_uuid(), %s, %s, 'submit', 'guard-submit-key', %s, %s, now())",
            (company_id, transfer_id, "0" * 64, user_id),
        )
        assert connection.execute(
            "SELECT count(*) FROM permissions WHERE code = ANY(%s)", (list(NEW_PERMISSIONS),)
        ).fetchone() == (2,)

    command.downgrade(config, PREVIOUS_REVISION)

    with connect(_dsn()) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            (PREVIOUS_REVISION,)
        ]
        assert connection.execute(
            "SELECT to_regclass('inventory_transfer_settings')"
        ).fetchone() == (None,)
        assert connection.execute(
            "SELECT count(*) FROM information_schema.columns WHERE table_name = "
            "'inventory_transfers' AND column_name IN ('route_type', 'requires_approval', "
            "'approval_round', 'submitted_by_id', 'approved_by_id', 'rejected_by_id', "
            "'rejection_reason')"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM permissions WHERE code = ANY(%s)", (list(NEW_PERMISSIONS),)
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM inventory_transfer_commands WHERE action = 'submit'"
        ).fetchone() == (0,)
        # The transfer itself survives, and the old status list is back.
        assert connection.execute(
            "SELECT count(*) FROM inventory_transfers WHERE id = %s", (transfer_id,)
        ).fetchone() == (1,)
        with pytest.raises(CheckViolation, match="ck_inventory_transfers_status"):
            connection.execute(
                "UPDATE inventory_transfers SET status = 'pending_approval' WHERE id = %s",
                (transfer_id,),
            )

    command.upgrade(config, "head")

    with connect(_dsn()) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [(head,)]
        assert connection.execute(
            "SELECT route_type, requires_approval, approval_round FROM inventory_transfers "
            "WHERE id = %s",
            (transfer_id,),
        ).fetchone() == ("central_distribution", False, 0)
        # Only the system super administrator receives the new permissions.
        granted = connection.execute(
            "SELECT DISTINCT r.name FROM role_permissions rp JOIN roles r ON r.id = rp.role_id "
            "JOIN permissions p ON p.id = rp.permission_id WHERE p.code = ANY(%s)",
            (list(NEW_PERMISSIONS),),
        ).fetchall()
        assert granted == [("SUPER_ADMIN",)]
        assert connection.execute(
            "SELECT count(*) FROM inventory_transfer_settings"
        ).fetchone() == (0,)
