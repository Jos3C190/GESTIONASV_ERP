"""What happened to a vehicle, and the checks that decide whether it may leave."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.application.fleet.costs import business_today
from app.application.fleet.dispatch import HARD_BLOCKS

from tests.e2e.test_fleet_operations import _new_vehicle
from tests.e2e.test_fleet_vehicles import _admin, _branch_manager, _branches

pytestmark = pytest.mark.e2e

FLEET = "/api/v1/fleet"


async def _setup(client: Any) -> tuple[dict[str, str], str, str]:
    admin = await _admin(client)
    branch = (await _branches(client, admin))[0]["id"]
    vehicle = await _new_vehicle(client, admin, branch)
    return admin, branch, f"{FLEET}/vehicles/{vehicle['id']}"


def _incident(**overrides: Any) -> dict[str, Any]:
    return {
        "kind": "accident",
        "severity": "moderate",
        "occurred_at": datetime.now(UTC).isoformat(),
        "description": "Golpe en la puerta al estacionar",
        **overrides,
    }


async def _items(client: Any, headers: dict[str, str]) -> list[dict[str, Any]]:
    response = await client.get(f"{FLEET}/inspection-items", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _answers(items: list[dict[str, Any]], *, failing: str | None = None) -> list[dict[str, Any]]:
    return [
        {
            "item_id": item["id"],
            "passed": item["name"] != failing,
            "notes": "No frena bien" if item["name"] == failing else None,
        }
        for item in items
    ]


async def test_incident_follows_its_cycle_and_closing_needs_a_resolution(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    created = await e2e_client.post(
        f"{base}/incidents",
        headers=admin,
        json=_incident(location=" Km 12 ", cost="250.00", responsible="third_party"),
    )
    assert created.status_code == 201, created.text
    incident = created.json()
    assert incident["status"] == "open"
    assert incident["location"] == "Km 12"
    assert incident["reported_by_name"]
    url = f"{base}/incidents/{incident['id']}"

    review = await e2e_client.patch(
        url, headers=admin, json={"status": "in_review", "insurance_claim": "RC-77"}
    )
    assert review.status_code == 200, review.text
    assert review.json()["insurance_claim"] == "RC-77"

    bare = await e2e_client.patch(url, headers=admin, json={"status": "closed"})
    assert bare.status_code == 422
    assert bare.json()["code"] == "incident_resolution_required"

    closed = await e2e_client.patch(
        url, headers=admin, json={"status": "closed", "resolution": "Pagó la aseguradora"}
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["closed_at"]
    assert closed.json()["closed_by_name"]

    reopened = await e2e_client.patch(url, headers=admin, json={"status": "open"})
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["closed_at"] is None
    assert reopened.json()["resolution"] is None


async def test_incident_cannot_be_dated_in_the_future(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    tomorrow = datetime.now(UTC) + timedelta(days=1)
    response = await e2e_client.post(
        f"{base}/incidents", headers=admin, json=_incident(occurred_at=tomorrow.isoformat())
    )
    assert response.status_code == 422
    assert response.json()["code"] == "incident_future"


async def test_serious_incident_can_take_the_vehicle_out_of_service(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    created = await e2e_client.post(
        f"{base}/incidents",
        headers=admin,
        json=_incident(kind="theft", severity="severe", take_out_of_service=True),
    )
    assert created.status_code == 201, created.text
    vehicle = (await e2e_client.get(base, headers=admin)).json()
    assert vehicle["status"] == "out_of_service"

    # Solo se ofrece: si no se pide, el vehículo sigue como estaba.
    other_admin, _, other = await _setup(e2e_client)
    await e2e_client.post(
        f"{other}/incidents", headers=other_admin, json=_incident(severity="severe")
    )
    assert (await e2e_client.get(other, headers=other_admin)).json()["status"] == "active"


async def test_incident_on_the_road_is_recorded_without_stopping_the_vehicle(
    e2e_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.v1.routers import fleet_incidents

    admin, _, base = await _setup(e2e_client)

    async def on_trip(*_: Any) -> bool:
        return True

    monkeypatch.setattr(fleet_incidents, "_on_road", on_trip)
    created = await e2e_client.post(
        f"{base}/incidents",
        headers=admin,
        json=_incident(kind="theft", severity="severe", take_out_of_service=True),
    )
    assert created.status_code == 201, created.text
    assert created.json()["vehicle_taken_out"] is False
    assert (await e2e_client.get(base, headers=admin)).json()["status"] == "active"


async def test_editing_a_closed_incident_keeps_who_closed_it(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    incident = (await e2e_client.post(f"{base}/incidents", headers=admin, json=_incident())).json()
    url = f"{base}/incidents/{incident['id']}"
    closed = await e2e_client.patch(
        url, headers=admin, json={"status": "closed", "resolution": "Pagó el seguro"}
    )
    assert closed.status_code == 200, closed.text
    edited = await e2e_client.patch(url, headers=admin, json={"status": "closed", "cost": "40.00"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["cost"] == "40.00"
    assert edited.json()["closed_at"] == closed.json()["closed_at"]
    assert edited.json()["resolution"] == "Pagó el seguro"


async def test_incident_cost_enters_the_report(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    await e2e_client.post(f"{base}/incidents", headers=admin, json=_incident(cost="250.00"))
    today = str(business_today())
    report = await e2e_client.get(
        f"{FLEET}/cost-report",
        headers=admin,
        params={"date_from": today, "date_to": today, "vehicle_id": base.rsplit("/", 1)[-1]},
    )
    assert report.status_code == 200, report.text
    assert report.json()["rows"][0]["incidents"] == "250.00"
    assert report.json()["totals"]["total"] == "250.00"


async def test_checklist_starts_with_defaults_and_can_be_managed(e2e_client: Any) -> None:
    admin, _, _ = await _setup(e2e_client)
    items = await _items(e2e_client, admin)
    assert {"name": "Frenos", "is_critical": True}.items() <= next(
        item for item in items if item["name"] == "Frenos"
    ).items()

    created = await e2e_client.post(
        f"{FLEET}/inspection-items", headers=admin, json={"name": "Rampa", "is_critical": True}
    )
    assert created.status_code == 201, created.text
    duplicate = await e2e_client.post(
        f"{FLEET}/inspection-items", headers=admin, json={"name": "rampa"}
    )
    assert duplicate.status_code == 409
    off = await e2e_client.patch(
        f"{FLEET}/inspection-items/{created.json()['id']}",
        headers=admin,
        json={"name": "Rampa", "is_critical": True, "is_active": False},
    )
    assert off.status_code == 200, off.text
    assert all(item["name"] != "Rampa" for item in await _items(e2e_client, admin))


async def test_every_point_must_be_answered_and_critical_failures_explained(
    e2e_client: Any,
) -> None:
    admin, _, base = await _setup(e2e_client)
    items = await _items(e2e_client, admin)
    partial = await e2e_client.post(
        f"{base}/inspections", headers=admin, json={"results": _answers(items)[:-1]}
    )
    assert partial.status_code == 422
    assert partial.json()["code"] == "inspection_incomplete"

    answers = _answers(items, failing="Frenos")
    for answer in answers:
        answer["notes"] = None
    silent = await e2e_client.post(f"{base}/inspections", headers=admin, json={"results": answers})
    assert silent.status_code == 422
    assert silent.json()["code"] == "inspection_failure_notes_required"


async def test_critical_failure_blocks_until_it_is_resolved(e2e_client: Any) -> None:
    assert "inspection_critical_failure" not in HARD_BLOCKS
    admin, _, base = await _setup(e2e_client)
    items = await _items(e2e_client, admin)

    clean = await e2e_client.post(
        f"{base}/inspections", headers=admin, json={"results": _answers(items)}
    )
    assert clean.status_code == 201, clean.text
    assert clean.json()["passed"] is True

    failed = await e2e_client.post(
        f"{base}/inspections", headers=admin, json={"results": _answers(items, failing="Frenos")}
    )
    assert failed.status_code == 201, failed.text
    assert failed.json()["passed"] is False
    result = next(item for item in failed.json()["results"] if not item["passed"])
    assert result["item_name"] == "Frenos"

    vehicle = (await e2e_client.get(base, headers=admin)).json()
    codes = {issue["code"]: issue for issue in vehicle["compliance"]["issues"]}
    assert codes["inspection_critical_failure"]["severity"] == "blocking"
    assert "Frenos" in codes["inspection_critical_failure"]["message"]

    # Pasar otra inspección no borra la falla: alguien debe decir cómo se resolvió.
    again = await e2e_client.post(
        f"{base}/inspections", headers=admin, json={"results": _answers(items)}
    )
    assert again.status_code == 201
    still = (await e2e_client.get(base, headers=admin)).json()
    assert "inspection_critical_failure" in {i["code"] for i in still["compliance"]["issues"]}

    resolved = await e2e_client.post(
        f"{base}/inspection-results/{result['id']}/resolve",
        headers=admin,
        json={"reason": "Se cambiaron las pastillas"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["resolution"] == "Se cambiaron las pastillas"
    after = (await e2e_client.get(base, headers=admin)).json()
    assert "inspection_critical_failure" not in {i["code"] for i in after["compliance"]["issues"]}

    twice = await e2e_client.post(
        f"{base}/inspection-results/{result['id']}/resolve",
        headers=admin,
        json={"reason": "Otra vez"},
    )
    assert twice.status_code == 409


async def test_the_same_failure_seen_twice_is_resolved_once(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    items = await _items(e2e_client, admin)
    for _ in range(2):
        failed = await e2e_client.post(
            f"{base}/inspections",
            headers=admin,
            json={"results": _answers(items, failing="Frenos")},
        )
        assert failed.status_code == 201, failed.text
    result = next(item for item in failed.json()["results"] if not item["passed"])
    resolved = await e2e_client.post(
        f"{base}/inspection-results/{result['id']}/resolve",
        headers=admin,
        json={"reason": "Se cambiaron las pastillas"},
    )
    assert resolved.status_code == 200, resolved.text
    vehicle = (await e2e_client.get(base, headers=admin)).json()
    assert "inspection_critical_failure" not in {
        issue["code"] for issue in vehicle["compliance"]["issues"]
    }


async def test_minor_failure_is_recorded_without_blocking(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    items = await _items(e2e_client, admin)
    answers = _answers(items, failing="Espejos y limpiaparabrisas")
    created = await e2e_client.post(f"{base}/inspections", headers=admin, json={"results": answers})
    assert created.status_code == 201, created.text
    assert created.json()["passed"] is True
    vehicle = (await e2e_client.get(base, headers=admin)).json()
    assert "inspection_critical_failure" not in {
        issue["code"] for issue in vehicle["compliance"]["issues"]
    }


async def test_renaming_a_point_does_not_rewrite_past_inspections(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    items = await _items(e2e_client, admin)
    await e2e_client.post(f"{base}/inspections", headers=admin, json={"results": _answers(items)})
    brakes = next(item for item in items if item["name"] == "Frenos")
    await e2e_client.patch(
        f"{FLEET}/inspection-items/{brakes['id']}",
        headers=admin,
        json={"name": "Sistema de frenos", "is_critical": True, "is_active": True},
    )
    history = (await e2e_client.get(f"{base}/inspections", headers=admin)).json()
    assert "Frenos" in {result["item_name"] for result in history[0]["results"]}


async def test_permissions_and_branch_scope(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branches = await _branches(e2e_client, admin)
    own = await _new_vehicle(e2e_client, admin, branches[0]["id"])
    other = await _new_vehicle(e2e_client, admin, branches[1]["id"])
    manager = await _branch_manager(e2e_client, admin, branches[0]["id"])

    denied = await e2e_client.post(
        f"{FLEET}/vehicles/{own['id']}/incidents", headers=manager, json=_incident()
    )
    assert denied.status_code == 403
    assert (
        await e2e_client.post(
            f"{FLEET}/vehicles/{own['id']}/inspections", headers=manager, json={"results": []}
        )
    ).status_code == 403
    readable = await e2e_client.get(f"{FLEET}/vehicles/{own['id']}/incidents", headers=manager)
    assert readable.status_code == 200
    hidden = await e2e_client.get(f"{FLEET}/vehicles/{other['id']}/incidents", headers=manager)
    assert hidden.status_code == 404


async def test_invalid_photo_is_rejected(e2e_client: Any) -> None:
    admin, _, base = await _setup(e2e_client)
    items = await _items(e2e_client, admin)
    answers = _answers(items)
    answers[0]["photo_url"] = "https://example.com/ajena.jpg"
    response = await e2e_client.post(
        f"{base}/inspections", headers=admin, json={"results": answers}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "inspection_photo_invalid"
