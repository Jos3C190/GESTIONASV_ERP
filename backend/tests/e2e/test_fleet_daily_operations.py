"""Company rules, covers, loans and reservations; with nothing turned on, dispatch is unchanged."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.application.fleet.costs import business_today

from tests.e2e.test_fleet_operations import _new_vehicle
from tests.e2e.test_fleet_vehicles import _admin, _branch_manager, _branches
from tests.e2e.test_inventory_transfers import (
    _committed_transfer_context,
    _create_preparation,
    _dispatch,
)

pytestmark = pytest.mark.e2e

FLEET = "/api/v1/fleet"
DEFAULTS = {
    "block_overdue_maintenance": False,
    "require_inspection": False,
    "block_overweight": False,
    "inspection_valid_hours": 24,
    "document_warning_days": 30,
    "maintenance_warning_km": 500,
    "maintenance_warning_days": 7,
}


async def _setup(client: Any) -> tuple[dict[str, str], list[dict[str, Any]], str]:
    admin = await _admin(client)
    branches = await _branches(client, admin)
    vehicle = await _new_vehicle(client, admin, branches[0]["id"])
    return admin, branches, f"{FLEET}/vehicles/{vehicle['id']}"


async def _dispatch_context(client: Any) -> tuple[Any, dict[str, str], str, str]:
    """A transfer ready to leave, its check URL and the fleet id of its vehicle."""
    suffix = uuid.uuid4().hex
    values, headers = await _committed_transfer_context(client, suffix)
    transfer = await _create_preparation(client, values, headers, f"ops-{suffix[:12]}")
    base = f"/api/v1/inventory/transfers/{transfer['id']}"
    options = (await client.get(f"{base}/dispatch-options", headers=headers)).json()
    option = next(
        item
        for item in options["vehicles"]
        if item["inventory_vehicle_id"] == str(values.vehicle_id)
    )
    return values, headers, base, option["fleet_vehicle_id"]


async def _check(client: Any, headers: dict[str, str], base: str, values: Any) -> dict[str, Any]:
    response = await client.post(
        f"{base}/dispatch-check", headers=headers, json={"vehicle_id": str(values.vehicle_id)}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _codes(preview: dict[str, Any]) -> dict[str, str]:
    return {
        issue["code"]: issue["severity"]
        for issue in [*preview["vehicle_issues"], *preview["driver_issues"]]
    }


async def test_settings_start_off_and_only_their_permission_changes_them(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    assert (await e2e_client.get(f"{FLEET}/settings", headers=admin)).json() == DEFAULTS

    changed = {**DEFAULTS, "require_inspection": True, "inspection_valid_hours": 12}
    saved = await e2e_client.put(f"{FLEET}/settings", headers=admin, json=changed)
    assert saved.status_code == 200, saved.text
    assert (await e2e_client.get(f"{FLEET}/settings", headers=admin)).json() == changed

    invalid = await e2e_client.put(
        f"{FLEET}/settings", headers=admin, json={**DEFAULTS, "inspection_valid_hours": 0}
    )
    assert invalid.status_code == 422

    manager = await _branch_manager(e2e_client, admin, branch)
    denied = await e2e_client.put(f"{FLEET}/settings", headers=manager, json=DEFAULTS)
    assert denied.status_code == 403


async def test_warning_windows_follow_the_settings(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    # Lectura inicial 1250.5: al próximo servicio le faltan 600 km.
    created = await e2e_client.post(
        f"{base}/maintenance-plans",
        headers=admin,
        json={"name": "Aceite", "interval_km": 1000, "last_service_km": "850.5"},
    )
    assert created.status_code == 201, created.text
    plans = (await e2e_client.get(f"{base}/maintenance-plans", headers=admin)).json()
    assert plans[0]["state"] == "ok"

    await e2e_client.put(
        f"{FLEET}/settings", headers=admin, json={**DEFAULTS, "maintenance_warning_km": 700}
    )
    plans = (await e2e_client.get(f"{base}/maintenance-plans", headers=admin)).json()
    assert plans[0]["state"] == "soon"


async def test_overdue_maintenance_only_blocks_when_turned_on(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    await e2e_client.post(
        f"{base}/maintenance-plans",
        headers=admin,
        json={"name": "Aceite", "interval_km": 100, "last_service_km": "100.0"},
    )

    async def severity() -> str:
        vehicle = (await e2e_client.get(base, headers=admin)).json()
        return next(
            issue["severity"]
            for issue in vehicle["compliance"]["issues"]
            if issue["code"] == "maintenance_overdue"
        )

    assert await severity() == "warning"
    await e2e_client.put(
        f"{FLEET}/settings", headers=admin, json={**DEFAULTS, "block_overdue_maintenance": True}
    )
    assert await severity() == "blocking"


async def test_inspection_is_required_only_when_turned_on(e2e_client: Any) -> None:
    values, headers, base, vehicle_id = await _dispatch_context(e2e_client)
    assert "inspection_required" not in _codes(await _check(e2e_client, headers, base, values))

    await e2e_client.put(
        f"{FLEET}/settings", headers=headers, json={**DEFAULTS, "require_inspection": True}
    )
    preview = await _check(e2e_client, headers, base, values)
    assert _codes(preview)["inspection_required"] == "blocking"
    assert preview["hard_blocked"] is False

    items = (await e2e_client.get(f"{FLEET}/inspection-items", headers=headers)).json()
    inspected = await e2e_client.post(
        f"{FLEET}/vehicles/{vehicle_id}/inspections",
        headers=headers,
        json={"results": [{"item_id": item["id"], "passed": True} for item in items]},
    )
    assert inspected.status_code == 201, inspected.text
    assert "inspection_required" not in _codes(await _check(e2e_client, headers, base, values))


async def test_load_weight_only_matters_when_the_company_turns_the_rule_on(
    e2e_client: Any,
) -> None:
    values, headers, base, _ = await _dispatch_context(e2e_client)
    assert "load_weight_unknown" not in _codes(await _check(e2e_client, headers, base, values))

    await e2e_client.put(
        f"{FLEET}/settings", headers=headers, json={**DEFAULTS, "block_overweight": True}
    )
    codes = _codes(await _check(e2e_client, headers, base, values))
    assert codes.get("load_weight_unknown") == "warning"
    assert "vehicle_overweight" not in codes


def test_overweight_rule() -> None:
    from decimal import Decimal

    from app.application.fleet.dispatch import HARD_BLOCKS, weight_issues
    from app.application.fleet.settings import to_kilograms

    assert weight_issues(Decimal("100"), 0, Decimal("100"), block=True) == []
    over = weight_issues(Decimal("101"), 0, Decimal("100"), block=True)
    assert [(i.code, i.severity) for i in over] == [("vehicle_overweight", "blocking")]
    # Apagada la regla, avisa pero no frena.
    off = weight_issues(Decimal("101"), 3, Decimal("100"), block=False)
    assert [(i.code, i.severity) for i in off] == [("vehicle_overweight", "warning")]
    assert "vehicle_overweight" not in HARD_BLOCKS
    assert weight_issues(Decimal("500"), 0, None, block=True) == []
    assert [i.code for i in weight_issues(Decimal("0"), 2, Decimal("100"), block=True)] == [
        "load_weight_unknown"
    ]
    assert to_kilograms(Decimal("2"), "t") == Decimal("2000")
    assert to_kilograms(Decimal("500"), "g") == Decimal("0.500")
    assert to_kilograms(Decimal("1"), "piedra") is None


async def test_driver_cannot_take_a_second_trip_or_be_suspended_on_the_road(
    e2e_client: Any,
) -> None:
    suffix = uuid.uuid4().hex
    values, headers = await _committed_transfer_context(e2e_client, suffix)
    first = await _create_preparation(e2e_client, values, headers, f"one-{suffix[:12]}")
    second = await _create_preparation(e2e_client, values, headers, f"two-{suffix[:12]}")
    options = await e2e_client.get(
        f"/api/v1/inventory/transfers/{second['id']}/dispatch-options", headers=headers
    )
    origin_branch = options.json()["origin_branch_id"]
    dispatched = await _dispatch(e2e_client, first, headers, f"one-{suffix}", values.vehicle_id)
    assert dispatched.status_code == 200, dispatched.text

    other_inventory = await e2e_client.post(
        f"{FLEET}/vehicles",
        headers=headers,
        json={
            "branch_id": origin_branch,
            "code": f"DOS-{suffix[:6]}".upper(),
            "plate": f"D {suffix[:6]}".upper(),
            "kind": "pickup",
            "brand": "Toyota",
            "model": "Hilux",
            "year": 2024,
            "capacity_kg": "900",
            "fuel_type": "diesel",
        },
    )
    assert other_inventory.status_code == 201, other_inventory.text
    check = await e2e_client.post(
        f"/api/v1/inventory/transfers/{second['id']}/dispatch-check",
        headers=headers,
        json={
            "vehicle_id": other_inventory.json()["inventory_vehicle_id"],
            "driver_id": str(values.driver_id),
        },
    )
    assert check.status_code == 200, check.text
    assert _codes(check.json())["driver_on_road"] == "blocking"
    assert check.json()["hard_blocked"] is True

    suspended = await e2e_client.post(
        f"{FLEET}/drivers/{values.driver_id}/status".replace("/fleet/drivers", "/drivers"),
        headers=headers,
        json={"status": "suspended", "reason": "Licencia en revisión"},
    )
    assert suspended.status_code == 409, suspended.text
    assert suspended.json()["code"] == "driver_on_road"


async def test_a_reservation_refuses_overlaps_and_warns_at_dispatch(e2e_client: Any) -> None:
    values, headers, base, vehicle_id = await _dispatch_context(e2e_client)
    url = f"{FLEET}/vehicles/{vehicle_id}/reservations"
    now = datetime.now(UTC)
    window = {
        "starts_at": (now - timedelta(hours=1)).isoformat(),
        "ends_at": (now + timedelta(hours=4)).isoformat(),
        "reason": "Visita a clientes",
    }
    created = await e2e_client.post(url, headers=headers, json=window)
    assert created.status_code == 201, created.text
    assert created.json()["reserved_by_name"]

    overlap = await e2e_client.post(
        url,
        headers=headers,
        json={
            **window,
            "starts_at": (now + timedelta(hours=3)).isoformat(),
            "ends_at": (now + timedelta(hours=8)).isoformat(),
        },
    )
    assert overlap.status_code == 409, overlap.text
    assert overlap.json()["code"] == "reservation_overlap"

    assert _codes(await _check(e2e_client, headers, base, values))["vehicle_reserved"] == "warning"

    cancelled = await e2e_client.post(
        f"{url}/{created.json()['id']}/cancel", headers=headers, json={"reason": "Ya no se usará"}
    )
    assert cancelled.status_code == 200, cancelled.text
    assert "vehicle_reserved" not in _codes(await _check(e2e_client, headers, base, values))
    # Cancelada, esas fechas vuelven a estar libres.
    assert (await e2e_client.post(url, headers=headers, json=window)).status_code == 201


async def test_reservation_dates_are_checked(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    now = datetime.now(UTC)
    backwards = await e2e_client.post(
        f"{base}/reservations",
        headers=admin,
        json={
            "starts_at": (now + timedelta(hours=2)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
            "reason": "Al revés",
        },
    )
    assert backwards.status_code == 422
    assert backwards.json()["code"] == "reservation_dates"


async def test_a_loan_moves_where_the_vehicle_can_be_dispatched_but_not_its_home(
    e2e_client: Any,
) -> None:
    values, headers, base, vehicle_id = await _dispatch_context(e2e_client)
    url = f"{FLEET}/vehicles/{vehicle_id}"
    branches = await _branches(e2e_client, headers)
    home = (await e2e_client.get(url, headers=headers)).json()["branch_id"]
    other = next(branch["id"] for branch in branches if branch["id"] != home)
    returning = str(business_today() + timedelta(days=5))

    same = await e2e_client.post(
        f"{url}/loans",
        headers=headers,
        json={"to_branch_id": home, "expected_return_on": returning, "reason": "Apoyo"},
    )
    assert same.status_code == 422

    lent = await e2e_client.post(
        f"{url}/loans",
        headers=headers,
        json={"to_branch_id": other, "expected_return_on": returning, "reason": "Apoyo temporada"},
    )
    assert lent.status_code == 201, lent.text
    vehicle = (await e2e_client.get(url, headers=headers)).json()
    assert vehicle["branch_id"] == home
    assert vehicle["loan"]["to_branch_id"] == other

    twice = await e2e_client.post(
        f"{url}/loans",
        headers=headers,
        json={"to_branch_id": other, "expected_return_on": returning, "reason": "Otra vez"},
    )
    assert twice.status_code == 409

    # Prestado, ya no sale de su sucursal: ni se ofrece ni pasa la revisión.
    options = (await e2e_client.get(f"{base}/dispatch-options", headers=headers)).json()
    assert str(values.vehicle_id) not in {v["inventory_vehicle_id"] for v in options["vehicles"]}
    assert (
        _codes(await _check(e2e_client, headers, base, values))["vehicle_branch_mismatch"]
        == "blocking"
    )

    returned = await e2e_client.post(f"{url}/loans/{lent.json()['id']}/return", headers=headers)
    assert returned.status_code == 200, returned.text
    assert returned.json()["returned_at"]
    assert (await e2e_client.get(url, headers=headers)).json()["loan"] is None
    assert "vehicle_branch_mismatch" not in _codes(await _check(e2e_client, headers, base, values))


async def test_a_lent_vehicle_keeps_its_branch_until_it_comes_back(e2e_client: Any) -> None:
    admin, branches, base = await _setup(e2e_client)
    lent = await e2e_client.post(
        f"{base}/loans",
        headers=admin,
        json={
            "to_branch_id": branches[1]["id"],
            "expected_return_on": str(business_today()),
            "reason": "Apoyo",
        },
    )
    assert lent.status_code == 201, lent.text

    moved = await e2e_client.post(
        f"{base}/branch",
        headers=admin,
        json={"branch_id": branches[2 % len(branches)]["id"], "reason": "Mudanza"},
    )
    assert moved.status_code == 409
    assert moved.json()["code"] == "vehicle_on_loan"
    retired = await e2e_client.post(
        f"{base}/status", headers=admin, json={"status": "retired", "reason": "Vendido"}
    )
    assert retired.status_code == 409
    assert retired.json()["code"] == "vehicle_on_loan"


async def test_the_borrowing_branch_can_operate_but_not_administer_the_vehicle(
    e2e_client: Any,
) -> None:
    admin, branches, base = await _setup(e2e_client)
    borrower = await _branch_manager(e2e_client, admin, branches[1]["id"])
    assert (await e2e_client.get(base, headers=borrower)).status_code == 404

    lent = await e2e_client.post(
        f"{base}/loans",
        headers=admin,
        json={
            "to_branch_id": branches[1]["id"],
            "expected_return_on": str(business_today()),
            "reason": "Apoyo",
        },
    )
    assert lent.status_code == 201, lent.text
    assert (await e2e_client.get(base, headers=borrower)).status_code == 200
    listed = await e2e_client.get(f"{FLEET}/vehicles", headers=borrower)
    assert base.rsplit("/", 1)[-1] in {item["id"] for item in listed.json()["items"]}
    assert (await e2e_client.get(f"{base}/inspections", headers=borrower)).status_code == 200
    # Puede operarlo, no administrarlo: eso sigue en su sucursal.
    edited = await e2e_client.patch(base, headers=borrower, json={"color": "Rojo"})
    assert edited.status_code == 404

    await e2e_client.post(f"{base}/loans/{lent.json()['id']}/return", headers=admin)
    assert (await e2e_client.get(base, headers=borrower)).status_code == 404


async def test_a_reservation_warns_shortly_before_it_starts_in_local_time(e2e_client: Any) -> None:
    from app.application.fleet.costs import BUSINESS_TZ

    values, headers, base, vehicle_id = await _dispatch_context(e2e_client)
    start = datetime.now(UTC) + timedelta(hours=2)
    created = await e2e_client.post(
        f"{FLEET}/vehicles/{vehicle_id}/reservations",
        headers=headers,
        json={
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=1)).isoformat(),
            "reason": "Visita",
        },
    )
    assert created.status_code == 201, created.text
    preview = await _check(e2e_client, headers, base, values)
    issue = next(item for item in preview["vehicle_issues"] if item["code"] == "vehicle_reserved")
    assert start.astimezone(BUSINESS_TZ).strftime("%d/%m/%Y %H:%M") in issue["message"]


async def test_temporary_assignment_ending_today_is_accepted_in_local_time(e2e_client: Any) -> None:
    values, headers, _, vehicle_id = await _dispatch_context(e2e_client)
    await e2e_client.post(
        f"{FLEET}/vehicles/{vehicle_id}/assignment/end",
        headers=headers,
        json={"reason": "Para cubrirlo"},
    )
    assigned = await e2e_client.post(
        f"{FLEET}/vehicles/{vehicle_id}/assignment",
        headers=headers,
        json={
            "driver_id": str(values.driver_id),
            "override_reason": "Prueba de cobertura",
            "expected_end_on": str(business_today()),
        },
    )
    assert assigned.status_code == 201, assigned.text
    vehicle = (await e2e_client.get(f"{FLEET}/vehicles/{vehicle_id}", headers=headers)).json()
    assert vehicle["driver"]["expected_end_on"] == str(business_today())
    assert "assignment_overdue" not in {issue["code"] for issue in vehicle["compliance"]["issues"]}


async def test_temporary_assignment_warns_when_it_runs_out(e2e_client: Any) -> None:
    values, headers, _, vehicle_id = await _dispatch_context(e2e_client)
    from app.infrastructure.db.session import async_session_factory
    from app.infrastructure.models.fleet import VehicleDriverAssignmentModel
    from sqlalchemy import update

    async with async_session_factory() as session:
        await session.execute(
            update(VehicleDriverAssignmentModel)
            .where(
                VehicleDriverAssignmentModel.vehicle_id == uuid.UUID(vehicle_id),
                VehicleDriverAssignmentModel.ends_at.is_(None),
            )
            .values(expected_end_on=business_today() - timedelta(days=1))
        )
        await session.commit()
    vehicle = (await e2e_client.get(f"{FLEET}/vehicles/{vehicle_id}", headers=headers)).json()
    assert vehicle["driver"]["expected_end_on"] == str(business_today() - timedelta(days=1))
    assert "assignment_overdue" in {issue["code"] for issue in vehicle["compliance"]["issues"]}


async def test_loans_and_reservations_need_their_permission(e2e_client: Any) -> None:
    admin, branches, base = await _setup(e2e_client)
    manager = await _branch_manager(e2e_client, admin, branches[0]["id"])
    loan = await e2e_client.post(
        f"{base}/loans",
        headers=manager,
        json={
            "to_branch_id": branches[1]["id"],
            "expected_return_on": str(business_today()),
            "reason": "Apoyo",
        },
    )
    assert loan.status_code == 403
    now = datetime.now(UTC)
    reservation = await e2e_client.post(
        f"{base}/reservations",
        headers=manager,
        json={
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
            "reason": "Visita",
        },
    )
    assert reservation.status_code == 403
