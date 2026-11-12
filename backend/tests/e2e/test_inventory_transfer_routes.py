"""HTTP checks for transfers between branches, returns to headquarters and approval."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from app.api.v1.after_commit import wait_for_pending
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.fleet import DriverModel, FleetVehicleModel
from app.infrastructure.models.organization import Branch, Location, Warehouse
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from sqlalchemy import select, update

from tests.e2e.test_inventory_block4_closure import _branch_profile_headers
from tests.e2e.test_inventory_transfers import (
    DISPATCH_OVERRIDE,
    _committed_transfer_context,
)

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
async def _settle_trip_archiving(e2e_client) -> AsyncIterator[None]:
    """Closing or cancelling a transfer archives its trip after commit; finish it in this test."""
    yield
    await wait_for_pending()


BASE = "/api/v1/inventory/transfers"
FLAGS = ("allow_branch_to_branch", "allow_branch_to_central", "require_approval")


def _key(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


async def _put_settings(client, headers: dict[str, str], **flags: bool):
    body = {
        "allow_branch_to_branch": False,
        "allow_branch_to_central": False,
        "require_approval": True,
        **flags,
    }
    return await client.put(f"{BASE}/settings", headers=headers, json=body)


@asynccontextmanager
async def _transfer_policy(client, headers: dict[str, str], **flags: bool) -> AsyncIterator[None]:
    """Apply the rules for one test and put back what the company had."""
    snapshot = (await client.get(f"{BASE}/settings", headers=headers)).json()
    changed = await _put_settings(client, headers, **flags)
    assert changed.status_code == 200, changed.text
    try:
        yield
    finally:
        await _put_settings(client, headers, **{name: snapshot[name] for name in FLAGS})


async def _branch_route_context(client, suffix: str) -> tuple[SimpleNamespace, dict[str, str]]:
    """Stock in a warehouse of branch A, a warehouse in branch B and a fleet in branch A."""
    values, admin = await _committed_transfer_context(client, suffix)
    async with async_session_factory() as session:
        second_branch_id = await session.scalar(
            select(Branch.id)
            .where(
                Branch.company_id == values.company_id,
                Branch.is_headquarters.is_(False),
                Branch.is_active.is_(True),
                Branch.operational_status == "active",
                Branch.deleted_at.is_(None),
                Branch.id != values.destination_branch_id,
            )
            .order_by(Branch.created_at, Branch.id)
            .limit(1)
        )
        assert second_branch_id is not None
        branch_a = await session.get(Warehouse, values.destination_id)
        assert branch_a is not None
        branch_b = Warehouse(
            company_id=values.company_id,
            branch_id=second_branch_id,
            warehouse_category_id=branch_a.warehouse_category_id,
            name=f"Ruta B {suffix[:8]}",
            code=f"RB-{suffix[:8]}",
            is_central=False,
            storage_eligible=True,
            capacity_enforcement_mode="disabled",
        )
        session.add(branch_b)
        await session.flush()
        location_b = Location(
            warehouse_id=branch_b.id,
            code=f"RB-L-{suffix[:8]}",
            aisle="01",
            rack="01",
            level="01",
            position="01",
            storage_eligible=True,
            capacity_enforcement_mode="disabled",
        )
        session.add(location_b)
        await session.flush()
        receipt = await SqlAlchemyInventoryRepository(session).post_movement(
            company_id=values.company_id,
            idempotency_key=f"route-e2e-seed-{suffix}",
            movement_type="receipt",
            source_reference=f"route-e2e-receipt:{suffix}",
            lines=[
                {
                    "inventory_item_id": values.item_id,
                    "to_location_id": values.destination_location_id,
                    "to_stock_status": "available",
                    "quantity_base": Decimal("10"),
                    "valuation_value": Decimal("25"),
                    "valuation_currency": "USD",
                    "handling_unit_code": f"RT-E2E-{suffix[:12]}",
                    "actual_measures": {
                        "gross_weight_kg": Decimal("10"),
                        "length_m": Decimal("0.5"),
                        "width_m": Decimal("0.5"),
                        "height_m": Decimal("0.4"),
                    },
                }
            ],
            actor_id=values.actor_id,
        )
        # The trip starts in branch A, so the vehicle and its driver belong there.
        await session.execute(
            update(FleetVehicleModel)
            .where(FleetVehicleModel.inventory_vehicle_id == values.vehicle_id)
            .values(branch_id=values.destination_branch_id)
        )
        await session.execute(
            update(DriverModel)
            .where(DriverModel.id == values.driver_id)
            .values(branch_id=values.destination_branch_id)
        )
        route = SimpleNamespace(
            branch_a_id=values.destination_id,
            branch_a_branch_id=values.destination_branch_id,
            branch_b_id=branch_b.id,
            branch_b_branch_id=second_branch_id,
            branch_b_location_id=location_b.id,
            unit_id=receipt["lines"][0]["handling_unit_id"],
            central_id=values.origin_id,
        )
        await session.commit()
    values.route = route
    return values, admin


async def _profiles(client, values: SimpleNamespace, suffix: str) -> SimpleNamespace:
    async def profile(label: str, branch_id: uuid.UUID, *permissions: str) -> dict[str, str]:
        return await _branch_profile_headers(
            client,
            company_id=values.company_id,
            branch_id=branch_id,
            username=f"rt-{label}-{suffix[:10]}",
            permissions=permissions,
        )

    branch_a = values.route.branch_a_branch_id
    branch_b = values.route.branch_b_branch_id
    return SimpleNamespace(
        creator=await profile("creator", branch_a, "inventory:read", "inventory:move"),
        approver=await profile(
            "approver", branch_a, "inventory:read", "inventory:transfer_approve"
        ),
        outsider=await profile(
            "outsider", branch_b, "inventory:read", "inventory:transfer_approve"
        ),
        reader=await profile("reader", branch_a, "inventory:read"),
        receiver=await profile("receiver", branch_b, "inventory:read", "inventory:receive"),
    )


async def _create_between(client, values, headers, *, destination_id=None, key=None):
    return await client.post(
        BASE,
        headers=headers,
        json={
            "idempotency_key": key or _key("rt-create"),
            "origin_warehouse_id": str(values.route.branch_a_id),
            "destination_warehouse_id": str(destination_id or values.route.branch_b_id),
            "vehicle_id": str(values.vehicle_id),
            "notes": "Rebalanceo por quiebre de existencias.",
            "lines": [
                {
                    "handling_unit_id": str(values.route.unit_id),
                    "quantity_base": "10",
                    "demand_allocations": [],
                    "excess_reason": "Reubicación por quiebre de existencias",
                }
            ],
        },
    )


async def _post(client, headers, transfer_id: str, action: str, **body: Any):
    return await client.post(
        f"{BASE}/{transfer_id}/{action}",
        headers=headers,
        json={"idempotency_key": _key(f"rt-{action}"), **body},
    )


async def _dispatch(client, values, headers, transfer_id: str):
    return await client.post(
        f"{BASE}/{transfer_id}/dispatch",
        headers=headers,
        json={
            "vehicle_id": str(values.vehicle_id),
            "idempotency_key": _key("rt-dispatch"),
            "override_reason": DISPATCH_OVERRIDE,
        },
    )


async def _cancel(client, headers, transfer_id: str):
    response = await _post(client, headers, transfer_id, "cancel")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"


async def test_branch_a_prepares_a_transfer_to_branch_b_that_needs_approval(e2e_client) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _branch_route_context(e2e_client, suffix)
    people = await _profiles(e2e_client, values, suffix)

    off = await _create_between(e2e_client, values, people.creator)
    assert off.status_code == 422, off.text
    assert off.json()["detail"]["code"] == "transfer_origin_not_central"

    async with _transfer_policy(e2e_client, admin, allow_branch_to_branch=True):
        created = await _create_between(e2e_client, values, people.creator)
        assert created.status_code == 201, created.text
        transfer = created.json()
        assert transfer["status"] == "preparation"
        assert transfer["route_type"] == "branch_to_branch"
        assert transfer["requires_approval"] is True
        assert transfer["origin_is_central"] is False
        assert transfer["destination_is_central"] is False
        assert transfer["origin_branch_name"] != transfer["destination_branch_name"]
        transfer_id = transfer["id"]

        early = await _dispatch(e2e_client, values, admin, transfer_id)
        assert early.status_code == 409, early.text
        assert early.json()["detail"]["code"] == "transfer_approval_required"
        assert early.json()["detail"]["message"] == (
            "Este traslado necesita aprobación antes de despacharse."
        )

        submitted = await _post(e2e_client, people.creator, transfer_id, "submit")
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["status"] == "pending_approval"
        assert submitted.json()["approval_round"] == 1

        # Quien solo prepara no aprueba; tampoco quien no tiene acceso al origen.
        for headers in (people.creator, people.reader, people.outsider):
            denied = await _post(e2e_client, headers, transfer_id, "approve", expected_round=1)
            assert denied.status_code == 403, denied.text
        stale = await _post(e2e_client, people.approver, transfer_id, "approve", expected_round=2)
        assert stale.status_code == 409, stale.text
        assert stale.json()["detail"]["code"] == "transfer_approval_stale"

        approved = await _post(
            e2e_client, people.approver, transfer_id, "approve", expected_round=1
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"
        assert approved.json()["approved_by_name"] == f"rt-approver-{suffix[:10]}"

        dispatched = await _dispatch(e2e_client, values, admin, transfer_id)
        assert dispatched.status_code == 200, dispatched.text
        assert dispatched.json()["status"] == "in_transit"
        received = await e2e_client.post(
            f"{BASE}/{transfer_id}/receive",
            headers=people.receiver,
            json={
                "idempotency_key": _key("rt-receive"),
                "lines": [
                    {
                        "transfer_detail_id": dispatched.json()["lines"][0]["id"],
                        "destination_location_id": str(values.route.branch_b_location_id),
                        "quantity_base": "10",
                    }
                ],
            },
        )
        assert received.status_code == 200, received.text
        assert received.json()["status"] == "received"
        detail = await e2e_client.get(f"{BASE}/{transfer_id}", headers=admin)
        assert detail.json()["approved_by_id"] == approved.json()["approved_by_id"]


async def test_rejection_is_explained_and_the_request_can_be_corrected_and_sent_again(
    e2e_client,
) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _branch_route_context(e2e_client, suffix)
    people = await _profiles(e2e_client, values, suffix)
    async with _transfer_policy(e2e_client, admin, allow_branch_to_branch=True):
        transfer_id = (await _create_between(e2e_client, values, people.creator)).json()["id"]
        await _post(e2e_client, people.creator, transfer_id, "submit")

        too_short = await _post(
            e2e_client, people.approver, transfer_id, "reject", expected_round=1, reason="no"
        )
        assert too_short.status_code == 422, too_short.text
        spaces = await _post(
            e2e_client, people.approver, transfer_id, "reject", expected_round=1, reason="      "
        )
        assert spaces.status_code == 422, spaces.text
        rejected = await _post(
            e2e_client,
            people.approver,
            transfer_id,
            "reject",
            expected_round=1,
            reason="La cantidad no coincide con el conteo.",
        )
        assert rejected.status_code == 200, rejected.text
        body = rejected.json()
        assert body["status"] == "preparation"
        assert body["rejection_reason"] == "La cantidad no coincide con el conteo."
        assert body["rejected_by_name"] == f"rt-approver-{suffix[:10]}"
        assert body["submitted_by_id"] is None

        again = await _post(e2e_client, people.creator, transfer_id, "submit")
        assert again.status_code == 200, again.text
        assert again.json()["approval_round"] == 2
        assert again.json()["rejection_reason"] is None
        old = await _post(e2e_client, people.approver, transfer_id, "approve", expected_round=1)
        assert old.status_code == 409
        assert old.json()["detail"]["code"] == "transfer_approval_stale"

        withdrawn = await _post(e2e_client, people.creator, transfer_id, "withdraw")
        assert withdrawn.status_code == 200, withdrawn.text
        assert withdrawn.json()["status"] == "preparation"
        gone = await _post(e2e_client, people.approver, transfer_id, "approve", expected_round=2)
        assert gone.status_code == 409
        assert gone.json()["detail"]["code"] == "transfer_not_pending_approval"
        await _cancel(e2e_client, people.creator, transfer_id)


async def test_a_superuser_may_approve_what_they_prepared_but_nobody_else_may(e2e_client) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _branch_route_context(e2e_client, suffix)
    people = await _profiles(e2e_client, values, suffix)
    # A branch profile that prepares and also holds the approval permission.
    both = await _branch_profile_headers(
        e2e_client,
        company_id=values.company_id,
        branch_id=values.route.branch_a_branch_id,
        username=f"rt-both-{suffix[:10]}",
        permissions=("inventory:read", "inventory:move", "inventory:transfer_approve"),
    )
    async with _transfer_policy(e2e_client, admin, allow_branch_to_branch=True):
        transfer_id = (await _create_between(e2e_client, values, both)).json()["id"]
        await _post(e2e_client, both, transfer_id, "submit")
        own = await _post(e2e_client, both, transfer_id, "approve", expected_round=1)
        assert own.status_code == 403, own.text
        assert own.json()["detail"]["code"] == "transfer_approval_self_forbidden"
        own_reject = await _post(
            e2e_client,
            both,
            transfer_id,
            "reject",
            expected_round=1,
            reason="Quiero rechazar el mío",
        )
        assert own_reject.status_code == 403, own_reject.text
        approved = await _post(e2e_client, admin, transfer_id, "approve", expected_round=1)
        assert approved.status_code == 200, approved.text
        await _cancel(e2e_client, people.creator, transfer_id)


async def test_settings_are_readable_by_readers_and_changed_only_with_the_permission(
    e2e_client,
) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _branch_route_context(e2e_client, suffix)
    people = await _profiles(e2e_client, values, suffix)

    # The static path must not be taken for a transfer id.
    default = await e2e_client.get(f"{BASE}/settings", headers=people.reader)
    assert default.status_code == 200, default.text
    assert default.json() == {
        "allow_branch_to_branch": False,
        "allow_branch_to_central": False,
        "require_approval": True,
        "updated_at": None,
        "pending_count": 0,
        "approved_count": 0,
    }
    denied = await _put_settings(e2e_client, people.approver, allow_branch_to_branch=True)
    assert denied.status_code == 403, denied.text
    denied_reader = await _put_settings(e2e_client, people.reader, allow_branch_to_branch=True)
    assert denied_reader.status_code == 403, denied_reader.text

    async with _transfer_policy(e2e_client, admin, allow_branch_to_branch=True):
        saved = await e2e_client.get(f"{BASE}/settings", headers=people.reader)
        assert saved.json()["allow_branch_to_branch"] is True
        assert saved.json()["updated_at"] is not None
        transfer_id = (await _create_between(e2e_client, values, people.creator)).json()["id"]
        await _post(e2e_client, people.creator, transfer_id, "submit")
        counted = await e2e_client.get(f"{BASE}/settings", headers=admin)
        assert counted.json()["pending_count"] == 1
        assert counted.json()["approved_count"] == 0
        await _post(e2e_client, people.approver, transfer_id, "approve", expected_round=1)
        counted = await e2e_client.get(f"{BASE}/settings", headers=admin)
        assert counted.json()["pending_count"] == 0
        assert counted.json()["approved_count"] == 1

        # Turning the route off freezes the approved transfer but never traps it.
        await _put_settings(e2e_client, admin)
        blocked = await _dispatch(e2e_client, values, admin, transfer_id)
        assert blocked.status_code == 409, blocked.text
        assert blocked.json()["detail"]["code"] == "transfer_route_disabled"
        await _cancel(e2e_client, people.creator, transfer_id)

    async with async_session_factory() as session:
        entries = list(
            await session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.company_id == values.company_id,
                    AuditLog.action == "UPDATE_INVENTORY_TRANSFER_SETTINGS",
                )
                .order_by(AuditLog.created_at)
            )
        )
    assert len(entries) >= 3
    first = entries[0]
    assert first.resource_type == "inventory_transfer_settings"
    assert first.before_state == {
        "allow_branch_to_branch": False,
        "allow_branch_to_central": False,
        "require_approval": True,
    }
    assert first.after_state == {
        "allow_branch_to_branch": True,
        "allow_branch_to_central": False,
        "require_approval": True,
    }
    assert all(entry.user_id is not None for entry in entries)


async def test_the_approval_inbox_and_its_count_only_show_what_the_user_can_decide(
    e2e_client,
) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _branch_route_context(e2e_client, suffix)
    people = await _profiles(e2e_client, values, suffix)
    async with _transfer_policy(e2e_client, admin, allow_branch_to_branch=True):
        transfer_id = (await _create_between(e2e_client, values, people.creator)).json()["id"]
        await _post(e2e_client, people.creator, transfer_id, "submit")

        async def inbox(headers: dict[str, str]) -> tuple[list[str], int]:
            listed = await e2e_client.get(
                BASE, headers=headers, params={"awaiting_my_approval": "true"}
            )
            counted = await e2e_client.get(f"{BASE}/pending-approval-count", headers=headers)
            assert listed.status_code == 200, listed.text
            assert counted.status_code == 200, counted.text
            return [row["id"] for row in listed.json()], counted.json()["count"]

        assert await inbox(people.approver) == ([transfer_id], 1)
        assert await inbox(admin) == ([transfer_id], 1)
        # No permission, or no access to the origin branch: nothing to decide.
        assert await inbox(people.creator) == ([], 0)
        assert await inbox(people.reader) == ([], 0)
        assert await inbox(people.outsider) == ([], 0)

        either_side = await e2e_client.get(
            BASE,
            headers=people.receiver,
            params={"branch_id": str(values.route.branch_b_branch_id)},
        )
        assert [row["id"] for row in either_side.json()] == [transfer_id]
        origin_only = await e2e_client.get(
            BASE,
            headers=people.creator,
            params={"branch_id": str(values.route.branch_a_branch_id), "side": "destination"},
        )
        assert origin_only.json() == []
        by_route = await e2e_client.get(
            BASE, headers=admin, params={"route_type": "branch_to_central"}
        )
        assert by_route.json() == []
        pending = await e2e_client.get(BASE, headers=admin, params={"status": "pending_approval"})
        assert [row["id"] for row in pending.json()] == [transfer_id]

        await _post(e2e_client, people.approver, transfer_id, "approve", expected_round=1)
        assert await inbox(people.approver) == ([], 0)
        await _cancel(e2e_client, people.creator, transfer_id)


async def test_changing_the_origin_of_a_draft_needs_access_to_the_new_origin(e2e_client) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _branch_route_context(e2e_client, suffix)
    people = await _profiles(e2e_client, values, suffix)
    async with _transfer_policy(e2e_client, admin, allow_branch_to_branch=True):
        transfer_id = (await _create_between(e2e_client, values, people.creator)).json()["id"]

        async def update(origin_id: uuid.UUID, destination_id: uuid.UUID):
            return await e2e_client.put(
                f"{BASE}/{transfer_id}",
                headers=people.creator,
                json={
                    "idempotency_key": _key("rt-update"),
                    "origin_warehouse_id": str(origin_id),
                    "destination_warehouse_id": str(destination_id),
                    "vehicle_id": None,
                    "notes": None,
                    "lines": [
                        {
                            "handling_unit_id": str(values.route.unit_id),
                            "quantity_base": "10",
                            "demand_allocations": [],
                            "excess_reason": "Reubicación por quiebre de existencias",
                        }
                    ],
                },
            )

        # Headquarters' central warehouse is outside the branch profile's scope.
        hijack = await update(values.route.central_id, values.route.branch_b_id)
        assert hijack.status_code == 403, hijack.text
        kept = await update(values.route.branch_a_id, values.route.branch_b_id)
        assert kept.status_code == 200, kept.text
        assert kept.json()["origin_warehouse_id"] == str(values.route.branch_a_id)
        await _cancel(e2e_client, people.creator, transfer_id)


async def test_approving_and_withdrawing_at_the_same_time_lets_only_one_win(e2e_client) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _branch_route_context(e2e_client, suffix)
    people = await _profiles(e2e_client, values, suffix)
    async with _transfer_policy(e2e_client, admin, allow_branch_to_branch=True):
        transfer_id = (await _create_between(e2e_client, values, people.creator)).json()["id"]
        await _post(e2e_client, people.creator, transfer_id, "submit")
        approve, withdraw = await asyncio.gather(
            _post(e2e_client, people.approver, transfer_id, "approve", expected_round=1),
            _post(e2e_client, people.creator, transfer_id, "withdraw"),
        )
        outcomes = sorted([approve.status_code, withdraw.status_code])
        assert outcomes == [200, 409], [approve.text, withdraw.text]
        loser = approve if approve.status_code == 409 else withdraw
        assert loser.json()["detail"]["code"] == "transfer_not_pending_approval"
        final = (await e2e_client.get(f"{BASE}/{transfer_id}", headers=admin)).json()
        assert final["status"] == ("approved" if approve.status_code == 200 else "preparation")
        await _cancel(e2e_client, people.creator, transfer_id)


async def test_route_options_show_only_what_the_user_may_ship_and_where(e2e_client) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _branch_route_context(e2e_client, suffix)
    people = await _profiles(e2e_client, values, suffix)

    closed = await e2e_client.get(f"{BASE}/route-options", headers=people.creator)
    assert closed.status_code == 200, closed.text
    assert closed.json()["origins"] == []
    assert closed.json()["policy"] == {
        "allow_branch_to_branch": False,
        "allow_branch_to_central": False,
        "require_approval": True,
    }

    async with _transfer_policy(
        e2e_client, admin, allow_branch_to_branch=True, allow_branch_to_central=True
    ):
        opened = await e2e_client.get(f"{BASE}/route-options", headers=people.creator)
        origins = {row["id"]: row for row in opened.json()["origins"]}
        assert str(values.route.branch_a_id) in origins
        assert all(
            row["branch_id"] == str(values.route.branch_a_branch_id) for row in origins.values()
        )
        assert set(origins[str(values.route.branch_a_id)]) == {
            "id",
            "code",
            "name",
            "branch_id",
            "branch_name",
            "is_central",
        }
        reader = await e2e_client.get(f"{BASE}/route-options", headers=people.reader)
        assert reader.json()["origins"] == []

        chosen = await e2e_client.get(
            f"{BASE}/route-options",
            headers=people.creator,
            params={"origin_warehouse_id": str(values.route.branch_a_id)},
        )
        assert chosen.status_code == 200, chosen.text
        routes = {row["id"]: row["route_type"] for row in chosen.json()["destinations"]}
        assert routes[str(values.route.branch_b_id)] == "branch_to_branch"
        assert routes[str(values.route.central_id)] == "branch_to_central"
        assert str(values.route.branch_a_id) not in routes

        elsewhere = await e2e_client.get(
            f"{BASE}/route-options",
            headers=people.creator,
            params={"origin_warehouse_id": str(values.route.branch_b_id)},
        )
        assert elsewhere.status_code == 403, elsewhere.text
        assert elsewhere.json()["detail"]["message"] == "No tienes acceso a esta bodega de origen."
        admin_view = await e2e_client.get(
            f"{BASE}/route-options",
            headers=admin,
            params={"origin_warehouse_id": str(values.route.central_id)},
        )
        assert admin_view.status_code == 200, admin_view.text
        from_central = {row["id"]: row["route_type"] for row in admin_view.json()["destinations"]}
        assert from_central[str(values.route.branch_a_id)] == "central_distribution"


async def test_a_return_to_headquarters_needs_its_own_switch(e2e_client) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _branch_route_context(e2e_client, suffix)
    people = await _profiles(e2e_client, values, suffix)
    async with _transfer_policy(e2e_client, admin, allow_branch_to_branch=True):
        refused = await _create_between(
            e2e_client, values, people.creator, destination_id=values.route.central_id
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"]["code"] == "transfer_route_disabled"
        assert refused.json()["detail"]["message"] == (
            "Los retornos a la bodega central no están habilitados en esta empresa."
        )
    async with _transfer_policy(e2e_client, admin, allow_branch_to_central=True):
        returning = await _create_between(
            e2e_client, values, people.creator, destination_id=values.route.central_id
        )
        assert returning.status_code == 201, returning.text
        assert returning.json()["route_type"] == "branch_to_central"
        assert returning.json()["destination_is_central"] is True
        await _cancel(e2e_client, people.creator, returning.json()["id"])
