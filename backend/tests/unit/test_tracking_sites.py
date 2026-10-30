import uuid
from types import SimpleNamespace

from app.application.tracking.sites import (
    build_sites,
    effective_location,
    plan_site_geofences,
    site_geofence_body,
)

COMPANY = uuid.uuid4()


def _branch(name: str, lat: float | None = 13.48, **extra: object) -> SimpleNamespace:
    values = {
        "id": uuid.uuid4(),
        "name": name,
        "code": name[:3].upper(),
        "address": f"Calle {name}",
        "latitude": lat,
        "longitude": None if lat is None else -88.18,
        "geofence_radius_m": 150,
        "operational_status": "active",
        "is_active": True,
        "deleted_at": None,
    }
    values.update(extra)
    return SimpleNamespace(**values)


def _warehouse(branch: SimpleNamespace, name: str, **extra: object) -> SimpleNamespace:
    values = {
        "id": uuid.uuid4(),
        "branch_id": branch.id,
        "name": name,
        "code": None,
        "is_central": False,
        "is_transit": False,
        "location_mode": "branch",
        "latitude": None,
        "longitude": None,
        "geofence_radius_m": None,
        "physical_location": None,
        "operational_status": "active",
        "is_active": True,
        "deleted_at": None,
    }
    values.update(extra)
    return SimpleNamespace(**values)


def test_effective_location_prefers_the_warehouse_building() -> None:
    branch = _branch("Roosevelt")
    inside = _warehouse(branch, "Bodega")
    outside = _warehouse(
        branch,
        "Externa",
        location_mode="own",
        latitude=13.7,
        longitude=-89.1,
        geofence_radius_m=400,
    )
    assert effective_location(inside, branch) == (13.48, -88.18, 150)
    assert effective_location(outside, branch) == (13.7, -89.1, 400)
    assert effective_location(inside, _branch("Sin mapa", lat=None)) is None


def test_build_sites_groups_and_reports_missing_places() -> None:
    main = _branch("Roosevelt")
    unmapped = _branch("Matriz", lat=None)
    closed = _branch("Cerrada", operational_status="inactive")
    inside = _warehouse(main, "Bodega central", is_central=True)
    other = _warehouse(main, "Abarrotes")
    outside = _warehouse(
        main,
        "Externa",
        location_mode="own",
        latitude=13.7,
        longitude=-89.1,
        physical_location="Km 12",
    )
    transit = _warehouse(main, "VEH-001", is_transit=True)
    stranded = _warehouse(unmapped, "Bodega matriz")
    hidden = _warehouse(closed, "Bodega cerrada")
    paused = _warehouse(main, "Inactiva", operational_status="inactive")

    sites, missing = build_sites(
        [main, unmapped, closed], [other, inside, outside, transit, stranded, hidden, paused]
    )
    assert [(site.kind, site.name) for site in sites] == [
        ("branch", "Roosevelt"),
        ("warehouse", "Externa"),
    ]
    assert [item["name"] for item in sites[0].warehouses] == ["Bodega central", "Abarrotes"]
    assert sites[1].address == "Km 12"
    assert {(item["kind"], item["name"]) for item in missing} == {
        ("branch", "Matriz"),
        ("warehouse", "Bodega matriz"),
    }


def test_plan_creates_updates_and_deletes_site_geofences() -> None:
    kept, moved, new = _branch("A"), _branch("B"), _branch("C")
    sites, _ = build_sites([kept, moved, new], [])
    desired = [site_geofence_body(site, COMPANY) for site in sites]
    by_name = {body["name"]: body for body in desired}
    existing = [
        {"id": 1, **by_name["Sucursal A"]},
        {"id": 2, **by_name["Sucursal B"], "area": "CIRCLE (0 0, 10.0)"},
        {"id": 3, **by_name["Sucursal B"]},  # duplicado
        {"id": 4, "name": "Sucursal vieja", "attributes": {"erpSiteId": str(uuid.uuid4())}},
    ]
    plan = plan_site_geofences(desired, existing)
    assert [body["name"] for body in plan.create] == ["Sucursal C"]
    assert [geofence_id for geofence_id, _ in plan.update] == [2]
    assert plan.update[0][1]["area"] == by_name["Sucursal B"]["area"]
    assert sorted(plan.delete) == [3, 4]
    assert plan_site_geofences(desired, [{"id": i, **b} for i, b in enumerate(desired)]).empty
