"""HTTP checks for transport at preparation, partial reception and transfer discrepancies."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from app.api.v1 import transfer_tracking
from app.api.v1.after_commit import wait_for_pending
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.fleet import DriverModel, FleetVehicleModel
from app.infrastructure.models.inventory_adjustment import InventoryAdjustmentDocumentModel
from app.infrastructure.models.inventory_transfer import InventoryTransferDiscrepancyModel
from app.infrastructure.models.organization import Branch, Location, Warehouse
from app.infrastructure.models.user import User
from app.infrastructure.repositories.fleet_repository import FleetRepository
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from sqlalchemy import select, update

from tests.e2e.test_inventory_block4_closure import _branch_profile_headers
from tests.e2e.test_inventory_transfer_routes import (
    BASE,
    _branch_route_context,
    _create_between,
    _key,
    _post,
    _profiles,
    _transfer_policy,
)
from tests.e2e.test_inventory_transfers import (
    DISPATCH_OVERRIDE,
    _committed_transfer_context,
    _create_preparation,
)

pytestmark = pytest.mark.e2e

ADJUSTMENTS = "/api/v1/inventory/adjustments"
DAMAGE = {"damage_type": "broken", "damage_notes": "Cajas rotas al descargar"}


@pytest.fixture(autouse=True)
async def _settle_trip_archiving(e2e_client) -> AsyncIterator[None]:
    """Closing a trip archives it after commit; let that finish inside the test."""
    yield
    await wait_for_pending()


@pytest.fixture
def archived(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    """The trips whose trail was archived (the real archiving needs a GPS server)."""
    calls: list[uuid.UUID] = []

    async def record(company_id: uuid.UUID, transfer_id: uuid.UUID) -> None:
        calls.append(transfer_id)

    monkeypatch.setattr(transfer_tracking, "archive_trip", record)
    return calls


async def _new_driver(values: SimpleNamespace, branch_id: uuid.UUID, tag: str) -> uuid.UUID:
    async with async_session_factory() as session:
        employee = Employee(
            company_id=values.company_id,
            employee_code=f"DR-{tag[:12].upper()}",
            first_name=f"conductor-{tag[:8]}",
            last_name="Prueba",
            status="activo",
        )
        session.add(employee)
        await session.flush()
        driver = DriverModel(
            company_id=values.company_id,
            employee_id=employee.id,
            branch_id=branch_id,
            license_class="liviana",
        )
        session.add(driver)
        await session.commit()
        return driver.id


async def _restock(values: SimpleNamespace, suffix: str, tag: str) -> uuid.UUID:
    """Another unit of stock in the origin warehouse of the committed context."""
    async with async_session_factory() as session:
        location_id = await session.scalar(
            select(Location.id).where(
                Location.warehouse_id == values.origin_id, Location.code == f"IT-S-{suffix[:8]}"
            )
        )
        assert location_id is not None
        receipt = await SqlAlchemyInventoryRepository(session).post_movement(
            company_id=values.company_id,
            idempotency_key=f"disc-restock-{tag}-{suffix}",
            movement_type="receipt",
            source_reference=f"disc-restock:{tag}:{suffix}",
            lines=[
                {
                    "inventory_item_id": values.item_id,
                    "to_location_id": location_id,
                    "to_stock_status": "available",
                    "quantity_base": Decimal("10"),
                    "valuation_value": Decimal("25"),
                    "valuation_currency": "USD",
                    "handling_unit_code": f"DR-{tag}-{suffix[:12]}",
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
        await session.commit()
        unit_id: uuid.UUID = receipt["lines"][0]["handling_unit_id"]
        return unit_id


async def _central_transfer(
    client, values: SimpleNamespace, headers: dict[str, str], suffix: str
) -> dict[str, Any]:
    """A central distribution transfer, prepared and dispatched (with the usual exception)."""
    transfer = await _create_preparation(client, values, headers, suffix)
    dispatched = await client.post(
        f"{BASE}/{transfer['id']}/dispatch",
        headers=headers,
        json={
            "vehicle_id": str(values.vehicle_id),
            "idempotency_key": _key("disc-dispatch"),
            "override_reason": DISPATCH_OVERRIDE,
        },
    )
    assert dispatched.status_code == 200, dispatched.text
    return dispatched.json()


def _receive_body(transfer: dict[str, Any], values: SimpleNamespace, **line: Any) -> dict[str, Any]:
    return {
        "idempotency_key": _key("disc-receive"),
        "lines": [
            {
                "transfer_detail_id": transfer["lines"][0]["id"],
                "destination_location_id": str(values.destination_location_id),
                **line,
            }
        ],
    }


async def _attach_evidence(
    values: SimpleNamespace, adjustment_id: str, tag: str, *, username: str
) -> None:
    now = datetime.now(UTC)
    checksum = "c" * 64
    async with async_session_factory() as session:
        # The person who links the support must belong to the company.
        linker_id = await session.scalar(select(User.id).where(User.username == username))
        assert linker_id is not None
        asset = DocumentAssetModel(
            company_id=values.company_id,
            original_filename=f"support-{tag}.pdf",
            extension="pdf",
            declared_content_type="application/pdf",
            detected_content_type="application/pdf",
            size_bytes=512,
            checksum_sha256=checksum,
            bucket="adjustment-test",
            object_key=f"adjustments/{tag}-{uuid.uuid4().hex}.pdf",
            status="active",
            upload_expires_at=now + timedelta(hours=1),
            scanned_at=now,
            uploaded_by=values.actor_id,
        )
        session.add(asset)
        await session.flush()
        session.add(
            InventoryAdjustmentDocumentModel(
                company_id=values.company_id,
                adjustment_id=uuid.UUID(adjustment_id),
                document_id=asset.id,
                checksum_sha256=checksum,
                original_filename=asset.original_filename,
                linked_by_id=linker_id,
                linked_at=now,
                upload_completed_at=now,
            )
        )
        await session.commit()


def _adjustment_body(**extra: Any) -> dict[str, Any]:
    return {
        "idempotency_key": _key("disc-adjust"),
        "operational_date": "2026-10-19",
        "accounting_date": "2026-10-19",
        "reason": "Regularización de la diferencia del traslado.",
        "document_reference": "ACTA-DIFERENCIA-01",
        **extra,
    }


# --------------------------------------------------------------------------- transport


async def test_transport_is_judged_while_planning_and_a_change_needs_a_reason(e2e_client) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _branch_route_context(e2e_client, suffix)
    people = await _profiles(e2e_client, values, suffix)
    route = values.route
    async with _transfer_policy(e2e_client, admin, allow_branch_to_branch=True):
        options = await e2e_client.get(
            f"{BASE}/assignment-options",
            params={"origin_warehouse_id": str(route.branch_a_id)},
            headers=people.creator,
        )
        assert options.status_code == 200, options.text
        listed = {item["inventory_vehicle_id"]: item for item in options.json()["vehicles"]}
        assert listed[str(values.vehicle_id)]["available"] is True
        assert str(values.driver_id) in {item["id"] for item in options.json()["drivers"]}

        # Nothing is saved yet: the weight comes from the draft's lines.
        check_body = {
            "origin_warehouse_id": str(route.branch_a_id),
            "vehicle_id": str(values.vehicle_id),
            "driver_id": str(values.driver_id),
            "lines": [{"handling_unit_id": str(route.unit_id), "quantity_base": "10"}],
        }
        check = await e2e_client.post(
            f"{BASE}/assignment-check", headers=people.creator, json=check_body
        )
        assert check.status_code == 200, check.text
        body = check.json()
        assert body["planning_blocked"] is False
        assert body["conflicts"] == []
        assert body["load_kg"] is not None
        # The missing documents of the fixture vehicle only warn while planning.
        assert body["warnings"] >= 1
        assert all(
            issue["severity"] == "warning"
            for issue in body["vehicle_issues"] + body["driver_issues"]
        )
        # A load can only be weighed from units that are in the origin warehouse.
        foreign = await e2e_client.post(
            f"{BASE}/assignment-check",
            headers=people.creator,
            json={
                **check_body,
                "lines": [{"handling_unit_id": str(values.handling_unit_id), "quantity_base": "1"}],
            },
        )
        assert foreign.status_code == 422, foreign.text
        assert foreign.json()["detail"]["code"] == "transfer_assignment_units_invalid"
        no_driver = await e2e_client.post(
            f"{BASE}/assignment-check",
            headers=people.creator,
            json={**check_body, "driver_id": None},
        )
        assert no_driver.json()["planning_blocked"] is True
        assert no_driver.json()["driver_issues"][0]["code"] == "driver_required"
        # The branch scope applies: branch B's profile cannot plan from branch A.
        outsider = await e2e_client.post(
            f"{BASE}/assignment-check", headers=people.outsider, json=check_body
        )
        assert outsider.status_code == 403, outsider.text

        created = await _create_between(e2e_client, values, people.creator)
        assert created.status_code == 201, created.text
        transfer_id = created.json()["id"]
        assert created.json()["driver"]["id"] == str(values.driver_id)

        # A vehicle of another branch cannot be planned: sending the request is refused.
        async with async_session_factory() as session:
            await session.execute(
                update(FleetVehicleModel)
                .where(FleetVehicleModel.inventory_vehicle_id == values.vehicle_id)
                .values(branch_id=route.branch_b_branch_id)
            )
            await session.commit()
        unfit = await _post(e2e_client, people.creator, transfer_id, "submit")
        assert unfit.status_code == 409, unfit.text
        assert unfit.json()["detail"]["code"] == "transfer_assignment_unfit"
        saved_check = await e2e_client.get(
            f"{BASE}/{transfer_id}/assignment-check", headers=people.approver
        )
        assert saved_check.status_code == 200, saved_check.text
        assert saved_check.json()["planning_blocked"] is True
        assert "vehicle_branch_mismatch" in {
            issue["code"] for issue in saved_check.json()["vehicle_issues"]
        }
        async with async_session_factory() as session:
            await session.execute(
                update(FleetVehicleModel)
                .where(FleetVehicleModel.inventory_vehicle_id == values.vehicle_id)
                .values(branch_id=route.branch_a_branch_id)
            )
            await session.commit()

        submitted = await _post(e2e_client, people.creator, transfer_id, "submit")
        assert submitted.status_code == 200, submitted.text
        round_ = submitted.json()["approval_round"]

        # The approver sees the transport and whether it is still fit.
        approver_check = await e2e_client.get(
            f"{BASE}/{transfer_id}/assignment-check", headers=people.approver
        )
        assert approver_check.json()["planning_blocked"] is False
        # Another draft planning the same vehicle is warned about the waiting request.
        conflicts = await e2e_client.post(
            f"{BASE}/assignment-check", headers=people.creator, json=check_body
        )
        warned = conflicts.json()["conflicts"]
        assert [item["transfer_id"] for item in warned] == [transfer_id]
        assert warned[0]["same_vehicle"] is True
        assert warned[0]["same_driver"] is True
        assert warned[0]["message"].startswith("El vehículo y el conductor también están asignados")

        approved = await _post(
            e2e_client, people.approver, transfer_id, "approve", expected_round=round_
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["approved_vehicle"]["id"] == str(values.vehicle_id)
        assert approved.json()["approved_driver"]["id"] == str(values.driver_id)
        dispatch_options = await e2e_client.get(
            f"{BASE}/{transfer_id}/dispatch-options", headers=people.creator
        )
        assert dispatch_options.json()["approved_vehicle_id"] == str(values.vehicle_id)
        assert dispatch_options.json()["planned_driver_id"] == str(values.driver_id)

        # Dispatching with another driver is a substitution that must be explained.
        other_driver = await _new_driver(values, route.branch_a_branch_id, suffix[:12])

        swap_key = _key("swap-dispatch")

        async def dispatch(**extra: Any):
            return await e2e_client.post(
                f"{BASE}/{transfer_id}/dispatch",
                headers=admin,
                json={
                    "idempotency_key": swap_key,
                    "vehicle_id": str(values.vehicle_id),
                    "driver_id": str(other_driver),
                    "override_reason": DISPATCH_OVERRIDE,
                    **extra,
                },
            )

        no_reason = await dispatch()
        assert no_reason.status_code == 422, no_reason.text
        assert no_reason.json()["detail"]["code"] == "transfer_substitution_reason_required"
        dispatched = await dispatch(
            substitution_code="driver_unavailable",
            substitution_reason="El conductor aprobado no se presentó.",
        )
        assert dispatched.status_code == 200, dispatched.text
        body = dispatched.json()
        assert body["driver"]["id"] == str(other_driver)
        assert body["approved_driver"]["id"] == str(values.driver_id)
        assert body["assignment_substitution"]["code"] == "driver_unavailable"
        async with async_session_factory() as session:
            actions = set(
                await session.scalars(
                    select(AuditLog.action).where(AuditLog.resource_id == transfer_id)
                )
            )
        assert {"DISPATCH_TRANSFER_OVERRIDE", "DISPATCH_TRANSFER_SUBSTITUTION"} <= actions

        # The client retries with the same key and body once the transfer is in transit.
        replay = await dispatch(
            substitution_code="driver_unavailable",
            substitution_reason="El conductor aprobado no se presentó.",
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["id"] == transfer_id
        assert replay.json()["status"] == "in_transit"
        async with async_session_factory() as session:
            substitutions = list(
                await session.scalars(
                    select(AuditLog.id).where(
                        AuditLog.resource_id == transfer_id,
                        AuditLog.action == "DISPATCH_TRANSFER_SUBSTITUTION",
                    )
                )
            )
        # The change of transport was audited once, not again for the replay.
        assert len(substitutions) == 1
        # The same key with another body is still a conflict.
        changed = await dispatch(
            substitution_code="other", substitution_reason="Otro motivo distinto del anterior."
        )
        assert changed.status_code == 409, changed.text
        assert changed.json()["detail"]["code"] == "transfer_idempotency_conflict"

        # Close the trip so nothing is left on the road.
        received = await e2e_client.post(
            f"{BASE}/{transfer_id}/receive",
            headers=people.receiver,
            json={
                "idempotency_key": _key("swap-receive"),
                "lines": [
                    {
                        "transfer_detail_id": body["lines"][0]["id"],
                        "destination_location_id": str(route.branch_b_location_id),
                        "quantity_base": "10",
                    }
                ],
            },
        )
        assert received.status_code == 200, received.text
        assert received.json()["status"] == "received"


async def test_the_vehicle_is_busy_while_partially_received_and_free_once_closed(
    e2e_client, archived
) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _committed_transfer_context(e2e_client, suffix)

    async def on_the_road() -> bool:
        async with async_session_factory() as session:
            busy = await FleetRepository(session).active_transfers(
                values.company_id, [values.vehicle_id]
            )
        return values.vehicle_id in busy

    async with async_session_factory() as session:
        origin = await session.get(Warehouse, values.origin_id)
        assert origin is not None
    saved_driver = await _new_driver(values, origin.branch_id, suffix[:12])

    async def trips() -> list[str]:
        response = await e2e_client.get(f"/api/v1/drivers/{saved_driver}/trips", headers=admin)
        assert response.status_code == 200, response.text
        return [item["transfer_id"] for item in response.json()]

    draft = await e2e_client.post(
        BASE,
        headers=admin,
        json={
            "idempotency_key": _key("busy-create"),
            "origin_warehouse_id": str(values.origin_id),
            "destination_warehouse_id": str(values.destination_id),
            "vehicle_id": str(values.vehicle_id),
            "driver_id": str(saved_driver),
            "lines": [
                {
                    "handling_unit_id": str(values.handling_unit_id),
                    "quantity_base": "10",
                    "demand_allocations": [],
                    "excess_reason": "Traslado manual de demostración",
                }
            ],
        },
    )
    assert draft.status_code == 201, draft.text
    # A draft is not a trip: the driver's profile lists dispatched transfers only.
    assert await trips() == []
    assert not await on_the_road()
    # The check proposes the same driver as the dispatch: the one saved, not the Fleet one.
    check = await e2e_client.post(
        f"{BASE}/{draft.json()['id']}/dispatch-check",
        headers=admin,
        json={"vehicle_id": str(values.vehicle_id)},
    )
    assert check.status_code == 200, check.text
    assert check.json()["driver_id"] == str(saved_driver)
    explicit = await e2e_client.post(
        f"{BASE}/{draft.json()['id']}/dispatch-check",
        headers=admin,
        json={"vehicle_id": str(values.vehicle_id), "driver_id": str(values.driver_id)},
    )
    assert explicit.json()["driver_id"] == str(values.driver_id)
    dispatched = await e2e_client.post(
        f"{BASE}/{draft.json()['id']}/dispatch",
        headers=admin,
        json={
            "vehicle_id": str(values.vehicle_id),
            "idempotency_key": _key("busy-dispatch"),
            "override_reason": DISPATCH_OVERRIDE,
        },
    )
    assert dispatched.status_code == 200, dispatched.text
    transfer = dispatched.json()
    assert transfer["driver"]["id"] == str(saved_driver)
    assert await trips() == [transfer["id"]]
    assert await on_the_road()

    partial = await e2e_client.post(
        f"{BASE}/{transfer['id']}/receive",
        headers=admin,
        json=_receive_body(transfer, values, quantity_base="6"),
    )
    assert partial.status_code == 200, partial.text
    assert partial.json()["status"] == "partially_received"
    assert await on_the_road()

    closed = await _post(
        e2e_client, admin, transfer["id"], "close-reception", reason="El resto no llegó."
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "discrepancy"
    assert closed.json()["origin_count_pending"] is True
    # With the trip over, the vehicle and the driver are free and the trail is archived.
    assert not await on_the_road()
    await wait_for_pending()
    assert uuid.UUID(transfer["id"]) in archived

    # The missing goods turned up. The trip had ended: the truck and the driver stay free, so
    # another transfer can leave with them while the rest is received.
    shortage = closed.json()["discrepancies"][0]
    found = await _post(
        e2e_client,
        admin,
        transfer["id"],
        f"discrepancies/{shortage['id']}/found",
        notes="Apareció en la bodega de carga.",
    )
    assert found.status_code == 200, found.text
    assert found.json()["status"] == "partially_received"
    assert found.json()["received_at"] is not None
    assert not await on_the_road()
    second_unit = await _restock(values, suffix, "second")
    second_values = SimpleNamespace(**{**vars(values), "handling_unit_id": second_unit})
    second = await _central_transfer(e2e_client, second_values, admin, f"{suffix[:20]}-second")
    assert await on_the_road()

    finished = await e2e_client.post(
        f"{BASE}/{transfer['id']}/receive",
        headers=admin,
        json=_receive_body(transfer, values, quantity_base="4"),
    )
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == "received"
    # The second transfer is still travelling.
    assert await on_the_road()
    done = await e2e_client.post(
        f"{BASE}/{second['id']}/receive",
        headers=admin,
        json=_receive_body(second, values, quantity_base="10"),
    )
    assert done.status_code == 200, done.text
    assert not await on_the_road()


# --------------------------------------------------------------------------- discrepancies


async def test_damage_flow_permissions_and_archiving(e2e_client, archived) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _committed_transfer_context(e2e_client, suffix)
    async with async_session_factory() as session:
        origin = await session.get(Warehouse, values.origin_id)
        assert origin is not None
        origin_branch_id = origin.branch_id

    async def profile(label: str, branch_id: uuid.UUID, *permissions: str) -> dict[str, str]:
        return await _branch_profile_headers(
            e2e_client,
            company_id=values.company_id,
            branch_id=branch_id,
            username=f"disc-{label}-{suffix[:10]}",
            permissions=permissions,
        )

    destination = values.destination_branch_id
    receiver = await profile("receiver", destination, "inventory:read", "inventory:receive")
    adjuster = await profile("adjuster", destination, "inventory:read", "inventory:adjust")
    approver = await profile("approver", destination, "inventory:read", "inventory:adjust_approve")
    origin_counter = await profile("origin", origin_branch_id, "inventory:read", "inventory:adjust")

    transfer = await _central_transfer(e2e_client, values, admin, suffix)
    # Access to the transfer is checked before anything about it is revealed.
    async with async_session_factory() as session:
        third_branch = await session.scalar(
            select(Branch.id).where(
                Branch.company_id == values.company_id,
                Branch.id.not_in([destination, origin_branch_id]),
                Branch.deleted_at.is_(None),
            )
        )
    assert third_branch is not None
    stranger = await profile("stranger", third_branch, "inventory:read", "inventory:adjust")
    unknown = f"{BASE}/{transfer['id']}/discrepancies/{uuid.uuid4()}/adjustment"
    hidden = await e2e_client.post(unknown, headers=stranger, json=_adjustment_body())
    assert hidden.status_code == 403, hidden.text
    missing = await e2e_client.post(unknown, headers=adjuster, json=_adjustment_body())
    assert missing.status_code == 404, missing.text
    received = await e2e_client.post(
        f"{BASE}/{transfer['id']}/receive",
        headers=receiver,
        json=_receive_body(transfer, values, quantity_base="6", damaged_quantity="4", **DAMAGE),
    )
    assert received.status_code == 200, received.text
    body = received.json()
    assert body["status"] == "discrepancy"
    damage = body["discrepancies"][0]
    assert (damage["kind"], damage["status"], damage["quantity"]) == ("damage", "open", "4.000000")
    await wait_for_pending()
    assert uuid.UUID(transfer["id"]) in archived

    base = f"{BASE}/{transfer['id']}/discrepancies/{damage['id']}"

    async def post(headers: dict[str, str], action: str, **payload: Any):
        return await e2e_client.post(
            f"{base}/{action}", headers=headers, json={"idempotency_key": _key(action), **payload}
        )

    # Each command needs its own permission, on the right side of the trip.
    assert (await post(receiver, "adjustment", **_adjustment_body())).status_code == 403
    assert (await post(receiver, "claim", claim_reference="RECLAMO-01")).status_code == 403
    assert (await post(adjuster, "release", notes="Sin daño real.")).status_code == 403
    assert (await post(adjuster, "dismiss", notes="No aplica aquí.")).status_code == 403
    assert (await post(origin_counter, "claim", claim_reference="RECLAMO-02")).status_code == 403
    # A damage is handled at the destination: the origin cannot prepare its adjustment.
    assert (await post(origin_counter, "adjustment", **_adjustment_body())).status_code == 403

    prepared = await post(adjuster, "adjustment", **_adjustment_body())
    assert prepared.status_code == 201, prepared.text
    adjustment = prepared.json()
    assert adjustment["transfer_id"] is None
    assert adjustment["transfer_discrepancy_id"] == damage["id"]
    assert adjustment["transfer_discrepancy_kind"] == "damage"
    assert adjustment["transfer_reference"] == transfer["code"]
    assert adjustment["linked_transfer_id"] == transfer["id"]
    # An adjustment in progress keeps the damage from being claimed.
    busy = await post(approver, "claim", claim_reference="RECLAMO-03")
    assert busy.status_code == 409, busy.text
    assert busy.json()["detail"]["code"] == "transfer_discrepancy_has_adjustment"
    cancelled = await e2e_client.post(
        f"{ADJUSTMENTS}/{adjustment['id']}/cancel",
        headers=adjuster,
        json={"reason": "Mejor se reclama al transportista."},
    )
    assert cancelled.status_code == 200, cancelled.text

    calls_before = archived.count(uuid.UUID(transfer["id"]))
    claim_payload = {"claim_reference": "RECLAMO-TRANSPORTISTA-77"}
    claimed = await post(approver, "claim", **claim_payload)
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["status"] == "closed_with_adjustment"
    assert claimed.json()["discrepancies"][0]["status"] == "in_claim"
    await wait_for_pending()
    assert archived.count(uuid.UUID(transfer["id"])) == calls_before + 1
    released = await post(approver, "release", notes="Tras el reclamo se inspeccionó: está bien.")
    assert released.status_code == 200, released.text
    assert released.json()["discrepancies"][0]["resolution"] == "released"
    assert released.json()["status"] == "closed_with_adjustment"


async def test_a_shortage_is_counted_at_origin_and_written_off_with_an_adjustment(
    e2e_client, archived
) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _committed_transfer_context(e2e_client, suffix)
    async with async_session_factory() as session:
        origin = await session.get(Warehouse, values.origin_id)
        assert origin is not None
        origin_branch_id = origin.branch_id

    async def profile(label: str, branch_id: uuid.UUID, *permissions: str) -> dict[str, str]:
        return await _branch_profile_headers(
            e2e_client,
            company_id=values.company_id,
            branch_id=branch_id,
            username=f"short-{label}-{suffix[:10]}",
            permissions=permissions,
        )

    destination = values.destination_branch_id
    receiver = await profile("receiver", destination, "inventory:read", "inventory:receive")
    adjuster = await profile("adjuster", destination, "inventory:read", "inventory:adjust")
    approver = await profile(
        "approver", destination, "inventory:read", "inventory:adjust_approve", "inventory:valuation"
    )
    origin_counter = await profile("origin", origin_branch_id, "inventory:read", "inventory:adjust")

    transfer = await _central_transfer(e2e_client, values, admin, suffix)
    partial = await e2e_client.post(
        f"{BASE}/{transfer['id']}/receive",
        headers=receiver,
        json=_receive_body(transfer, values, quantity_base="6"),
    )
    assert partial.json()["status"] == "partially_received"
    # Whoever receives can close the reception; the rest becomes a shortage.
    closed = await _post(
        e2e_client,
        receiver,
        transfer["id"],
        "close-reception",
        reason="El resto no llegó en el vehículo.",
        evidence_reference="ACTA-RECEPCION-01",
    )
    assert closed.status_code == 200, closed.text
    shortage = closed.json()["discrepancies"][0]
    assert shortage["kind"] == "shortage"
    assert shortage["quantity"] == "4.000000"
    assert closed.json()["status"] == "discrepancy"
    assert closed.json()["received_at"] is not None
    base = f"{BASE}/{transfer['id']}/discrepancies/{shortage['id']}"

    async def post(headers: dict[str, str], action: str, **payload: Any):
        return await e2e_client.post(
            f"{base}/{action}", headers=headers, json={"idempotency_key": _key(action), **payload}
        )

    wrong_kind = await post(approver, "dismiss", notes="Un faltante no se descarta.")
    assert wrong_kind.status_code == 409, wrong_kind.text
    assert wrong_kind.json()["detail"]["code"] == "transfer_discrepancy_action_invalid"
    # The origin count belongs to the origin side only.
    assert (
        await post(receiver, "origin-count", notes="Intento desde el destino")
    ).status_code == 403
    counted = await post(origin_counter, "origin-count", notes="Se contó el origen: coincide.")
    assert counted.status_code == 200, counted.text
    assert counted.json()["origin_count_pending"] is False
    repeated = await post(origin_counter, "origin-count", notes="Segundo conteo en el origen.")
    assert repeated.status_code == 409, repeated.text
    assert repeated.json()["detail"]["code"] == "transfer_origin_count_already_recorded"

    # The write-off: prepared, evidenced, approved and applied like any adjustment.
    prepared = await post(adjuster, "adjustment", **_adjustment_body())
    assert prepared.status_code == 201, prepared.text
    adjustment = prepared.json()
    assert adjustment["transfer_id"] == transfer["id"]
    assert adjustment["transfer_incident_id"] is None
    assert adjustment["transfer_discrepancy_kind"] == "shortage"
    # The same request again returns the same adjustment.
    again = await post(adjuster, "adjustment", **_adjustment_body())
    assert again.status_code == 201
    assert again.json()["id"] == adjustment["id"]
    # A linked adjustment is never edited.
    edit = await e2e_client.put(
        f"{ADJUSTMENTS}/{adjustment['id']}",
        headers=adjuster,
        json={
            "operational_date": "2026-10-19",
            "accounting_date": "2026-10-19",
            "reason": "Intento de edición",
            "document_reference": "ACTA",
            "lines": [
                {
                    "inventory_item_id": adjustment["lines"][0]["inventory_item_id"],
                    "location_id": adjustment["lines"][0]["location_id"],
                    "direction": "decrease",
                    "quantity_base": "4",
                    "stock_status": "in_transit",
                    "handling_unit_id": adjustment["lines"][0]["handling_unit_id"],
                    "transfer_detail_id": adjustment["lines"][0]["transfer_detail_id"],
                }
            ],
        },
    )
    assert edit.status_code == 409, edit.text
    assert edit.json()["code"] == "adjustment_linked_document_immutable"

    await _attach_evidence(
        values, adjustment["id"], f"short-{suffix[:8]}", username=f"short-adjuster-{suffix[:10]}"
    )
    approved = await e2e_client.post(
        f"{ADJUSTMENTS}/{adjustment['id']}/approve",
        headers=approver,
        json={"expected_version": adjustment["version"]},
    )
    assert approved.status_code == 200, approved.text
    calls_before = archived.count(uuid.UUID(transfer["id"]))
    applied = await e2e_client.post(
        f"{ADJUSTMENTS}/{adjustment['id']}/apply",
        headers=approver,
        json={"idempotency_key": _key("short-apply")},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "applied"
    await wait_for_pending()
    # Closing with a loss archives the trip too.
    assert archived.count(uuid.UUID(transfer["id"])) == calls_before + 1

    current = await e2e_client.get(f"{BASE}/{transfer['id']}", headers=admin)
    assert current.json()["status"] == "closed_with_adjustment"
    assert current.json()["closed_at"] is not None
    row = current.json()["discrepancies"][0]
    assert (row["status"], row["resolution"]) == ("resolved", "written_off")
    assert row["adjustment"]["id"] == adjustment["id"]
    detail = await e2e_client.get(f"{ADJUSTMENTS}/{adjustment['id']}", headers=approver)
    assert detail.json()["transfer_reference"] == transfer["code"]


async def test_a_closed_discrepancy_refuses_a_stale_adjustment_over_http(e2e_client) -> None:
    suffix = uuid.uuid4().hex
    values, admin = await _committed_transfer_context(e2e_client, suffix)
    transfer = await _central_transfer(e2e_client, values, admin, suffix)
    received = await e2e_client.post(
        f"{BASE}/{transfer['id']}/receive",
        headers=admin,
        json=_receive_body(transfer, values, quantity_base="0", damaged_quantity="10", **DAMAGE),
    )
    assert received.status_code == 200, received.text
    damage = received.json()["discrepancies"][0]
    base = f"{BASE}/{transfer['id']}/discrepancies/{damage['id']}"
    prepared = await e2e_client.post(f"{base}/adjustment", headers=admin, json=_adjustment_body())
    assert prepared.status_code == 201, prepared.text
    adjustment = prepared.json()
    await _attach_evidence(
        values, adjustment["id"], f"stale-{suffix[:8]}", username=f"transfer-admin-{suffix[:10]}"
    )
    # While an adjustment is in progress the damage cannot be released.
    blocked = await e2e_client.post(
        f"{base}/release",
        headers=admin,
        json={"idempotency_key": _key("release"), "notes": "Sin daño real tras inspección."},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "transfer_discrepancy_has_adjustment"
    assert adjustment["code"] in blocked.json()["detail"]["message"]
    # Someone else closes it behind the back of the commands (a race): the draft is stale.
    async with async_session_factory() as session:
        await session.execute(
            update(InventoryTransferDiscrepancyModel)
            .where(InventoryTransferDiscrepancyModel.id == uuid.UUID(damage["id"]))
            .values(
                status="resolved",
                resolution="released",
                resolved_by_id=values.actor_id,
                resolved_at=datetime.now(UTC),
            )
        )
        await session.commit()
    stale = await e2e_client.post(
        f"{ADJUSTMENTS}/{adjustment['id']}/approve",
        headers=admin,
        json={"expected_version": adjustment["version"]},
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "adjustment_transfer_discrepancy_closed"

    # The generic adjustment form never links a discrepancy: only the transfer flow does.
    generic = await e2e_client.post(
        ADJUSTMENTS,
        headers=admin,
        json={
            "idempotency_key": _key("generic"),
            "warehouse_id": str(values.destination_id),
            "operational_date": "2026-10-19",
            "accounting_date": "2026-10-19",
            "reason": "Intento de vincular una diferencia",
            "document_reference": "ACTA",
            "transfer_discrepancy_id": damage["id"],
            "lines": [
                {
                    "inventory_item_id": str(values.item_id),
                    "location_id": str(values.destination_location_id),
                    "direction": "increase",
                    "quantity_base": "1",
                    "actual_gross_weight_kg": "1",
                    "actual_volume_m3": "0.01",
                }
            ],
        },
    )
    assert generic.status_code == 422, generic.text
    assert "transfer_discrepancy_id" in generic.text
