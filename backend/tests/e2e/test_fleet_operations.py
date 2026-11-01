"""Fleet operations: odometer, maintenance, fuel and alerts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.e2e.test_fleet_vehicles import _admin, _branch_manager, _branches, _vehicle

pytestmark = pytest.mark.e2e


async def _new_vehicle(e2e_client: Any, headers: dict[str, str], branch: str) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:5].upper()
    created = await e2e_client.post(
        "/api/v1/fleet/vehicles",
        headers=headers,
        json=_vehicle(branch, f"OP-{suffix}", f"P {suffix}"),
    )
    assert created.status_code == 201, created.text
    return created.json()


async def test_odometer_is_monotonic(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    vehicle = await _new_vehicle(e2e_client, admin, branch)
    base = f"/api/v1/fleet/vehicles/{vehicle['id']}/odometer"

    backwards = await e2e_client.post(base, headers=admin, json={"reading_km": "1000"})
    assert backwards.status_code == 409
    assert backwards.json()["code"] == "odometer_out_of_order"

    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert (
        await e2e_client.post(base, headers=admin, json={"reading_km": "2000", "read_at": future})
    ).status_code == 422

    ok = await e2e_client.post(base, headers=admin, json={"reading_km": "1500"})
    assert ok.status_code == 201, ok.text
    detail = await e2e_client.get(f"/api/v1/fleet/vehicles/{vehicle['id']}", headers=admin)
    assert detail.json()["odometer_km"] == "1500.0"

    readings = (await e2e_client.get(base, headers=admin)).json()
    assert [item["reading_km"] for item in readings][:2] == ["1500.0", "1250.5"]


async def test_maintenance_order_lifecycle(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    vehicle = await _new_vehicle(e2e_client, admin, branch)
    base = f"/api/v1/fleet/vehicles/{vehicle['id']}"

    no_interval = await e2e_client.post(
        f"{base}/maintenance-plans", headers=admin, json={"name": "Aceite"}
    )
    assert no_interval.status_code == 422
    plan = await e2e_client.post(
        f"{base}/maintenance-plans",
        headers=admin,
        json={"name": "Cambio de aceite", "interval_km": 5000, "last_service_km": "1000"},
    )
    assert plan.status_code == 201, plan.text
    assert float(plan.json()["due_km"]) == 6000.0

    order = await e2e_client.post(
        f"{base}/maintenance-orders",
        headers=admin,
        json={"kind": "preventive", "title": "Servicio 5000", "plan_id": plan.json()["id"]},
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]

    early = await e2e_client.post(
        f"{base}/maintenance-orders/{order_id}/complete",
        headers=admin,
        json={"odometer_km": "1300", "cost": "45.50"},
    )
    assert early.status_code == 409

    started = await e2e_client.post(f"{base}/maintenance-orders/{order_id}/start", headers=admin)
    assert started.status_code == 200, started.text
    assert (await e2e_client.get(base, headers=admin)).json()["status"] == "maintenance"

    done = await e2e_client.post(
        f"{base}/maintenance-orders/{order_id}/complete",
        headers=admin,
        json={"odometer_km": "1300", "cost": "45.50", "workshop": "Taller Central"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"
    refreshed = (await e2e_client.get(base, headers=admin)).json()
    assert refreshed["status"] == "active"
    assert float(refreshed["odometer_km"]) == 1300.0
    plans = (await e2e_client.get(f"{base}/maintenance-plans", headers=admin)).json()
    assert float(plans[0]["last_service_km"]) == 1300.0
    assert float(plans[0]["due_km"]) == 6300.0

    second = await e2e_client.post(
        f"{base}/maintenance-orders", headers=admin, json={"kind": "corrective", "title": "Frenos"}
    )
    second_id = second.json()["id"]
    await e2e_client.post(f"{base}/maintenance-orders/{second_id}/start", headers=admin)
    cancelled = await e2e_client.post(
        f"{base}/maintenance-orders/{second_id}/cancel",
        headers=admin,
        json={"reason": "Repuesto no disponible"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert (await e2e_client.get(base, headers=admin)).json()["status"] == "active"


async def test_fuel_efficiency_and_scope(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branches = await _branches(e2e_client, admin)
    vehicle = await _new_vehicle(e2e_client, admin, branches[0]["id"])
    base = f"/api/v1/fleet/vehicles/{vehicle['id']}/fuel-logs"
    now = datetime.now(UTC)

    for offset, liters, amount, km in (
        (3, "40", "160", "1300"),
        (2, "20", "80", "1500"),
        (1, "30", "120", "1700"),
    ):
        response = await e2e_client.post(
            base,
            headers=admin,
            json={
                "filled_at": (now + timedelta(seconds=30 - offset * 10)).isoformat(),
                "liters": liters,
                "total_amount": amount,
                "odometer_km": km,
                "station": "Puma",
            },
        )
        assert response.status_code == 201, response.text

    listing = (await e2e_client.get(base, headers=admin)).json()
    assert [item["km_per_liter"] for item in listing["items"]] == ["6.67", "10.00", None]
    assert listing["stats"]["liters"] == "90.000"
    assert listing["stats"]["average_km_per_liter"] == "8.34"

    backdated = await e2e_client.post(
        base,
        headers=admin,
        json={
            "filled_at": (now - timedelta(days=4)).isoformat(),
            "liters": "10",
            "total_amount": "40",
            "odometer_km": "1600",
        },
    )
    assert backdated.status_code == 409

    # Un gerente de otra sucursal no ve ni registra nada en este vehículo.
    manager = await _branch_manager(e2e_client, admin, branches[1]["id"])
    assert (await e2e_client.get(base, headers=manager)).status_code == 404
    alerts = await e2e_client.get("/api/v1/fleet/alerts", headers=manager)
    assert alerts.status_code == 200, alerts.text
    assert all(alert["vehicle_id"] != vehicle["id"] for alert in alerts.json())

    own = (await e2e_client.get("/api/v1/fleet/alerts", headers=admin)).json()
    mine = [alert for alert in own if alert["vehicle_id"] == vehicle["id"]]
    assert mine
    assert mine[0]["severity"] == "blocking"
