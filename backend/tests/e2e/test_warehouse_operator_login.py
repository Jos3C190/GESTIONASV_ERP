"""Operator bootstrapping must load the validated profile and restricted workspace."""

from types import SimpleNamespace

import pytest
from app.api.v1.schemas.auth import MeResponse
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.organization import UserWarehouseAccess
from app.infrastructure.models.user import User
from pydantic import ValidationError
from scripts.repair_warehouse_operator_email import repair
from sqlalchemy import func, select

from tests.e2e.test_inventory_preparation import _operator_headers
from tests.e2e.test_purchase_orders import _headers, _reference_ids

pytestmark = pytest.mark.e2e


async def test_legacy_operator_email_repair_restores_login_without_expanding_access(e2e_client):
    client = e2e_client
    company, branch, warehouse, *_ = await _reference_ids()
    await _headers(client, company_id=company, username="operator-repair-admin", is_superuser=True)
    headers = await _operator_headers(client, company, warehouse)
    args = SimpleNamespace(
        company_id=company,
        username="placement-operator",
        email=None,
        actor_username="operator-repair-admin",
        apply=False,
    )
    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.username == args.username))
        user.email = f"{args.username}@gestionasv.invalid"
        await session.commit()
        original_hash = user.password_hash
        original_grants = list(
            await session.scalars(
                select(UserWarehouseAccess.warehouse_id).where(
                    UserWarehouseAccess.user_id == user.id
                )
            )
        )
        with pytest.raises(ValidationError, match="email"):
            MeResponse.model_validate(user, from_attributes=True)
    preview = await repair(args)
    assert preview["changed"] is False
    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.username == args.username))
        assert user.email.endswith(".invalid")
    args.apply = True
    assert (await repair(args))["changed"] is True
    assert (await repair(args))["changed"] is False
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "placement-operator@example.com"
    assert me.json()["is_superuser"] is False
    permissions = await client.get("/api/v1/auth/me/permissions", headers=headers)
    assert permissions.status_code == 200, permissions.text
    assert "inventory:warehouse_receipts" in permissions.json()["permissions"]
    context = await client.get(f"/api/v1/operational-contexts/{company}", headers=headers)
    assert context.status_code == 200, context.text
    assert context.json()["access_all_branches"] is False
    warehouses = await client.get(
        f"/api/v1/warehouses?company_id={company}&branch_id={branch}", headers=headers
    )
    assert warehouses.status_code == 200, warehouses.text
    assert [row["id"] for row in warehouses.json()["items"]] == [str(warehouse)]
    queue = await client.get(
        f"/api/v1/inventory/preparation?warehouse_id={warehouse}", headers=headers
    )
    assert queue.status_code == 200, queue.text
    assert (await client.get("/api/v1/inventory/valuation", headers=headers)).status_code == 403
    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.username == args.username))
        assert user.password_hash == original_hash
        assert user.is_active
        assert not user.is_superuser
        assert (
            list(
                await session.scalars(
                    select(UserWarehouseAccess.warehouse_id).where(
                        UserWarehouseAccess.user_id == user.id
                    )
                )
            )
            == original_grants
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.resource_id == str(user.id),
                    AuditLog.metadata_["source"].astext == "repair_warehouse_operator_email",
                )
            )
            == 1
        )
