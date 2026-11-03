"""Vehicle types managed by each company, units without a plate and couplings."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.e2e.test_fleet_vehicles import _admin, _branch_manager, _branches, _vehicle

pytestmark = pytest.mark.e2e

TYPES = "/api/v1/fleet/vehicle-types"
VEHICLES = "/api/v1/fleet/vehicles"


def _suffix() -> str:
    return uuid.uuid4().hex[:5].upper()


async def _create(client: Any, headers: dict[str, str], branch: str, **fields: Any) -> Any:
    suffix = _suffix()
    payload = _vehicle(branch, f"VT-{suffix}", f"T {suffix}")
    payload.update(fields)
    return await client.post(VEHICLES, headers=headers, json=payload)


async def test_company_starts_with_the_base_catalogue(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)

    response = await e2e_client.get(TYPES, headers=admin)

    assert response.status_code == 200, response.text
    types = {item["code"]: item for item in response.json()}
    assert {"cargo_van", "motorcycle", "forklift", "tractor", "trailer"} <= set(types)
    assert types["motorcycle"]["license_classes"] == ["motocicleta"]
    assert types["forklift"]["requires_plate"] is False
    assert types["forklift"]["meter_unit"] == "hours"
    assert types["cargo_van"]["is_system"] is True


async def test_custom_type_works_end_to_end_with_its_rules(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    name = f"Grúa {_suffix()}"

    created = await e2e_client.post(
        TYPES,
        headers=admin,
        json={"name": name, "plural": "Grúas", "license_classes": ["pesada"]},
    )
    assert created.status_code == 201, created.text
    code = created.json()["code"]
    assert created.json()["is_system"] is False

    duplicate = await e2e_client.post(TYPES, headers=admin, json={"name": name.upper()})
    assert duplicate.status_code == 409

    vehicle = await _create(e2e_client, admin, branch, kind=code)
    assert vehicle.status_code == 201, vehicle.text
    assert vehicle.json()["type"]["name"] == name

    listing = await e2e_client.get(f"{VEHICLES}?kind={code}", headers=admin)
    assert [item["id"] for item in listing.json()["items"]] == [vehicle.json()["id"]]

    usage = {item["code"]: item for item in (await e2e_client.get(TYPES, headers=admin)).json()}
    assert usage[code]["usage_count"] == 1


async def test_inactive_type_keeps_its_vehicles_but_takes_no_new_ones(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    created = (
        await e2e_client.post(TYPES, headers=admin, json={"name": f"Temporal {_suffix()}"})
    ).json()
    vehicle = (await _create(e2e_client, admin, branch, kind=created["code"])).json()

    off = await e2e_client.patch(
        f"{TYPES}/{created['id']}",
        headers=admin,
        json={"name": created["name"], "is_active": False},
    )
    assert off.status_code == 200, off.text

    refused = await _create(e2e_client, admin, branch, kind=created["code"])
    assert refused.status_code == 422
    assert refused.json()["code"] == "vehicle_type_inactive"

    edited = await e2e_client.patch(
        f"{VEHICLES}/{vehicle['id']}", headers=admin, json={"color": "Rojo"}
    )
    assert edited.status_code == 200, edited.text

    active = (await e2e_client.get(TYPES, headers=admin)).json()
    assert created["code"] not in {item["code"] for item in active}
    everything = (await e2e_client.get(f"{TYPES}?include_inactive=true", headers=admin)).json()
    assert created["code"] in {item["code"] for item in everything}


async def test_unknown_type_is_refused(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]

    response = await _create(e2e_client, admin, branch, kind="no_existe")

    assert response.status_code == 422
    assert response.json()["code"] == "vehicle_type_not_found"


async def test_forklift_needs_no_plate_capacity_or_road_documents(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]

    created = await _create(e2e_client, admin, branch, kind="forklift", plate="", capacity_kg=None)

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["plate"] is None
    assert body["capacity_kg"] is None
    assert body["type"]["meter_unit"] == "hours"
    codes = {issue["code"] for issue in body["compliance"]["issues"]}
    assert "document_missing" not in codes

    second = await _create(e2e_client, admin, branch, kind="forklift", plate="", capacity_kg=None)
    assert second.status_code == 201, second.text


async def test_type_demands_what_it_needs(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]

    no_plate = await _create(e2e_client, admin, branch, kind="cargo_van", plate="")
    assert no_plate.status_code == 422
    assert no_plate.json()["code"] == "vehicle_plate_required"

    no_capacity = await _create(e2e_client, admin, branch, kind="cargo_van", capacity_kg=None)
    assert no_capacity.status_code == 422
    assert no_capacity.json()["code"] == "vehicle_capacity_required"

    no_fuel = await _create(e2e_client, admin, branch, kind="cargo_van", fuel_type="none")
    assert no_fuel.status_code == 422
    assert no_fuel.json()["code"] == "vehicle_fuel_required"

    trailer = await _create(e2e_client, admin, branch, kind="trailer", fuel_type="diesel")
    assert trailer.status_code == 201, trailer.text
    assert trailer.json()["fuel_type"] == "none"


async def test_used_type_refuses_changes_that_would_break_its_vehicles(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    created = (
        await e2e_client.post(
            TYPES,
            headers=admin,
            json={"name": f"Sin placa {_suffix()}", "requires_plate": False},
        )
    ).json()
    await _create(e2e_client, admin, branch, kind=created["code"], plate="")
    url = f"{TYPES}/{created['id']}"
    keep = {"name": created["name"], "requires_plate": False}

    meter = await e2e_client.patch(url, headers=admin, json={**keep, "meter_unit": "hours"})
    assert meter.status_code == 409

    plate = await e2e_client.patch(url, headers=admin, json={**keep, "requires_plate": True})
    assert plate.status_code == 409


async def test_managing_types_needs_its_own_permission(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    manager = await _branch_manager(e2e_client, admin, branch)

    assert (await e2e_client.get(TYPES, headers=manager)).status_code == 200
    refused = await e2e_client.post(TYPES, headers=manager, json={"name": "Sin permiso"})
    assert refused.status_code == 403


async def test_trailer_hitches_to_a_tractor_and_cannot_leave_alone(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    tractor = (await _create(e2e_client, admin, branch, kind="tractor", capacity_kg=None)).json()
    trailer = (await _create(e2e_client, admin, branch, kind="trailer")).json()
    van = (await _create(e2e_client, admin, branch, kind="cargo_van")).json()

    wrong = await e2e_client.put(
        f"{VEHICLES}/{van['id']}/coupling", headers=admin, json={"trailer_id": trailer["id"]}
    )
    assert wrong.status_code == 409
    assert wrong.json()["code"] == "vehicle_cannot_tow"

    url = f"{VEHICLES}/{tractor['id']}/coupling"
    coupled = await e2e_client.put(url, headers=admin, json={"trailer_id": trailer["id"]})
    assert coupled.status_code == 200, coupled.text
    assert coupled.json()["coupling"]["role"] == "tractor"
    assert coupled.json()["coupling"]["vehicle_id"] == trailer["id"]
    seen = (await e2e_client.get(f"{VEHICLES}/{trailer['id']}", headers=admin)).json()
    assert seen["coupling"]["role"] == "trailer"

    retire = await e2e_client.post(
        f"{VEHICLES}/{trailer['id']}/status",
        headers=admin,
        json={"status": "retired", "reason": "Venta del remolque"},
    )
    assert retire.status_code == 409
    assert retire.json()["code"] == "vehicle_is_coupled"

    released = await e2e_client.delete(f"{VEHICLES}/{trailer['id']}/coupling", headers=admin)
    assert released.status_code == 200, released.text
    assert released.json()["coupling"] is None
    assert (await e2e_client.delete(url, headers=admin)).status_code == 404


async def test_a_trailer_takes_no_driver(e2e_client: Any) -> None:
    admin = await _admin(e2e_client)
    branch = (await _branches(e2e_client, admin))[0]["id"]
    trailer = (await _create(e2e_client, admin, branch, kind="trailer")).json()

    response = await e2e_client.post(
        f"{VEHICLES}/{trailer['id']}/assignment",
        headers=admin,
        json={"driver_id": str(uuid.uuid4())},
    )

    assert response.status_code in {404, 409}, response.text
