"""Correcting what was captured wrong: voided, never deleted, and always explained."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.e2e.test_fleet_operations import _new_vehicle
from tests.e2e.test_fleet_vehicles import _admin, _branch_manager, _branches

pytestmark = pytest.mark.e2e

REASON = {"reason": "Error de digitación"}


async def _setup(client: Any) -> tuple[dict[str, str], str, str]:
    admin = await _admin(client)
    branch = (await _branches(client, admin))[0]["id"]
    vehicle = await _new_vehicle(client, admin, branch)
    return admin, branch, f"/api/v1/fleet/vehicles/{vehicle['id']}"


def _fuel(odometer: str, *, minutes_ago: int = 0, liters: str = "40.000") -> dict[str, Any]:
    moment = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    return {
        "filled_at": moment.isoformat(),
        "liters": liters,
        "total_amount": "150.00",
        "odometer_km": odometer,
        "full_tank": True,
    }


async def test_a_wrong_reading_can_be_voided_and_stops_blocking(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    await e2e_client.post(f"{base}/odometer", headers=admin, json={"reading_km": "15000.0"})
    wrong = await e2e_client.post(
        f"{base}/odometer", headers=admin, json={"reading_km": "150000.0"}
    )
    assert wrong.status_code == 201, wrong.text

    blocked = await e2e_client.post(
        f"{base}/odometer", headers=admin, json={"reading_km": "15100.0"}
    )
    assert blocked.status_code == 409

    voided = await e2e_client.post(
        f"{base}/odometer/{wrong.json()['id']}/void", headers=admin, json=REASON
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["odometer_km"] == "15000.0"

    fixed = await e2e_client.post(f"{base}/odometer", headers=admin, json={"reading_km": "15100.0"})
    assert fixed.status_code == 201, fixed.text

    history = (await e2e_client.get(f"{base}/odometer", headers=admin)).json()
    gone = next(item for item in history if item["id"] == wrong.json()["id"])
    assert gone["voided_at"] is not None
    assert gone["void_reason"] == REASON["reason"]
    assert gone["voided_by_name"]

    again = await e2e_client.post(
        f"{base}/odometer/{wrong.json()['id']}/void", headers=admin, json=REASON
    )
    assert again.status_code == 409


async def test_voiding_needs_a_reason_and_its_own_permission(e2e_client: Any) -> None:
    admin, branch, base = await _setup(e2e_client)
    reading = (
        await e2e_client.post(f"{base}/odometer", headers=admin, json={"reading_km": "2000.0"})
    ).json()
    url = f"{base}/odometer/{reading['id']}/void"

    assert (await e2e_client.post(url, headers=admin, json={"reason": ""})).status_code == 422
    manager = await _branch_manager(e2e_client, admin, branch)
    assert (await e2e_client.post(url, headers=manager, json=REASON)).status_code == 403


async def test_meter_replacement_restarts_the_count_and_keeps_the_total(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    await e2e_client.post(f"{base}/odometer", headers=admin, json={"reading_km": "50000.0"})
    plan = await e2e_client.post(
        f"{base}/maintenance-plans",
        headers=admin,
        json={"name": "Aceite", "interval_km": 5000, "last_service_km": "48000.0"},
    )
    assert plan.status_code == 201, plan.text

    replaced = await e2e_client.post(
        f"{base}/odometer/replace-meter",
        headers=admin,
        json={"reading_km": "10.0", "reason": "Tablero dañado"},
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["odometer_km"] == "10.0"

    lower = await e2e_client.post(f"{base}/odometer", headers=admin, json={"reading_km": "5.0"})
    assert lower.status_code == 409
    next_reading = await e2e_client.post(
        f"{base}/odometer", headers=admin, json={"reading_km": "1000.0"}
    )
    assert next_reading.status_code == 201, next_reading.text

    total = (await e2e_client.get(f"{base}/odometer/total", headers=admin)).json()
    assert total["replacements"] == 1
    # Desde la lectura inicial de 1250.5 hasta 50000, más los 990 del tablero nuevo.
    assert float(total["total"]) == 49739.5

    plans = (await e2e_client.get(f"{base}/maintenance-plans", headers=admin)).json()
    active = next(item for item in plans if item["name"] == "Aceite")
    # Faltaban 3000 km para el servicio; con el tablero nuevo siguen faltando.
    assert float(active["due_km"]) == 3010

    edited = await e2e_client.put(
        f"{base}/maintenance-plans/{active['id']}",
        headers=admin,
        json={
            "name": "Aceite fino",
            "interval_km": 5000,
            "last_service_km": active["last_service_km"],
        },
    )
    assert edited.status_code == 200, edited.text
    typed = await e2e_client.put(
        f"{base}/maintenance-plans/{active['id']}",
        headers=admin,
        json={"name": "Aceite", "interval_km": 5000, "last_service_km": "-5.0"},
    )
    assert typed.status_code == 422


async def test_undoing_a_meter_replacement_restores_the_plans(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    await e2e_client.post(f"{base}/odometer", headers=admin, json={"reading_km": "50000.0"})
    await e2e_client.post(
        f"{base}/maintenance-plans",
        headers=admin,
        json={"name": "Aceite", "interval_km": 5000, "last_service_km": "48000.0"},
    )
    await e2e_client.post(
        f"{base}/odometer/replace-meter",
        headers=admin,
        json={"reading_km": "10.0", "reason": "Se registró en el vehículo equivocado"},
    )
    history = (await e2e_client.get(f"{base}/odometer", headers=admin)).json()
    replacement = next(item for item in history if item["source"] == "meter_replacement")
    url = f"{base}/odometer/{replacement['id']}/void"

    later = await e2e_client.post(f"{base}/odometer", headers=admin, json={"reading_km": "20.0"})
    assert later.status_code == 201, later.text
    blocked = await e2e_client.post(url, headers=admin, json=REASON)
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "meter_has_later_readings"

    await e2e_client.post(f"{base}/odometer/{later.json()['id']}/void", headers=admin, json=REASON)
    undone = await e2e_client.post(url, headers=admin, json=REASON)
    assert undone.status_code == 200, undone.text
    assert undone.json()["odometer_km"] == "50000.0"

    plans = (await e2e_client.get(f"{base}/maintenance-plans", headers=admin)).json()
    assert float(plans[0]["last_service_km"]) == 48000


async def test_a_fuel_log_is_corrected_keeping_the_original(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    log = await e2e_client.post(f"{base}/fuel-logs", headers=admin, json=_fuel("90000.0"))
    assert log.status_code == 201, log.text
    assert (await e2e_client.get(base, headers=admin)).json()["odometer_km"] == "90000.0"

    corrected = await e2e_client.put(
        f"{base}/fuel-logs/{log.json()['id']}",
        headers=admin,
        json={**_fuel("9000.0", liters="42.000"), **REASON},
    )
    assert corrected.status_code == 200, corrected.text
    assert (await e2e_client.get(base, headers=admin)).json()["odometer_km"] == "9000.0"

    listing = (await e2e_client.get(f"{base}/fuel-logs", headers=admin)).json()
    assert len(listing["items"]) == 2
    assert listing["stats"]["liters"] == "42.000"
    old = next(item for item in listing["items"] if item["id"] == log.json()["id"])
    assert old["voided_at"] is not None
    assert old["void_reason"] == REASON["reason"]


async def test_voiding_a_fuel_log_also_voids_its_reading(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    log = (await e2e_client.post(f"{base}/fuel-logs", headers=admin, json=_fuel("80000.0"))).json()
    history = (await e2e_client.get(f"{base}/odometer", headers=admin)).json()
    from_fuel = next(item for item in history if item["source"] == "fuel")

    direct = await e2e_client.post(
        f"{base}/odometer/{from_fuel['id']}/void", headers=admin, json=REASON
    )
    assert direct.status_code == 409
    assert direct.json()["code"] == "odometer_from_fuel"

    voided = await e2e_client.post(f"{base}/fuel-logs/{log['id']}/void", headers=admin, json=REASON)
    assert voided.status_code == 200, voided.text
    assert voided.json()["odometer_km"] == "1250.5"

    listing = (await e2e_client.get(f"{base}/fuel-logs", headers=admin)).json()
    assert listing["stats"]["liters"] == "0.000"


async def test_tank_size_is_stored_with_the_vehicle(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)

    updated = await e2e_client.patch(base, headers=admin, json={"tank_liters": "120.00"})

    assert updated.status_code == 200, updated.text
    assert updated.json()["tank_liters"] == "120.00"
