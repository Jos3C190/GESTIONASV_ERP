from dataclasses import replace
from datetime import date, timedelta

import pytest
from app.api.v1.schemas.fleet import normalize_plate
from app.application.documents.service import inspect_document
from app.application.fleet.compliance import license_issue
from seed.grupo_lorena_documents import (
    driver_documents,
    render_demo_document,
    vehicle_documents,
)
from seed.seed_grupo_lorena import (
    CENTRAL_WAREHOUSE_MANAGER_CODE,
    EMPLOYEES,
    HEADQUARTERS,
)
from seed.seed_grupo_lorena_fleet import (
    DEFAULT_LICENSE_CLASSES,
    FLEET,
    HEADQUARTERS_FLEET,
    PLATE_2011,
    PLATE_ALPHANUMERIC,
    plate_problem,
    validate_fleet_seed,
)

VEHICLES = [vehicle for item in FLEET for vehicle in item.vehicles]
TODAY = date(2026, 11, 14)


def test_fleet_seed_is_consistent_with_the_default_vehicle_types() -> None:
    validate_fleet_seed()
    assert len(VEHICLES) == 17
    assert sum(len(item.drivers) for item in FLEET) == 17


def test_every_seeded_plate_is_normalized_unique_and_of_its_class() -> None:
    plates = [normalize_plate(vehicle.plate) for vehicle in VEHICLES]
    assert plates == [vehicle.plate for vehicle in VEHICLES]
    assert len(set(plates)) == len(plates)
    assert all(plate_problem(vehicle) is None for vehicle in VEHICLES)
    assert all(vehicle.plate.startswith("C ") for vehicle in VEHICLES)


def test_store_vehicles_keep_2011_plates_and_headquarters_uses_the_new_series() -> None:
    stores = [
        vehicle for item in FLEET if item is not HEADQUARTERS_FLEET for vehicle in item.vehicles
    ]
    assert all(PLATE_2011.match(vehicle.plate) for vehicle in stores)
    assert all(vehicle.year < 2025 for vehicle in stores)
    central = HEADQUARTERS_FLEET.vehicles
    assert all(PLATE_ALPHANUMERIC.match(vehicle.plate) for vehicle in central)
    assert all(not PLATE_2011.match(vehicle.plate) for vehicle in central)


@pytest.mark.parametrize(
    ("plate", "kind", "year"),
    [
        ("P 118-402", "refrigerated", 2022),  # carga con placa particular
        ("C 3A8-1F4", "refrigerated", 2022),  # serie nueva en un vehículo anterior
        ("C 118-402", "refrigerated", 2025),  # vehículo nuevo con placa de 2011
        ("C 3G8-1F4", "cargo_van", 2025),  # la serie nueva solo usa A-F
        ("C 318-104", "cargo_van", 2025),  # sin letras no es la serie nueva
        ("C 118-402", "pickup", 2021),  # un pickup particular lleva P
        ("c 118-402", "refrigerated", 2022),  # sin normalizar
    ],
)
def test_incoherent_plates_are_rejected(plate: str, kind: str, year: int) -> None:
    vehicle = replace(VEHICLES[0], plate=plate, kind=kind, year=year)
    assert plate_problem(vehicle) is not None


def test_headquarters_fleet_moves_stock_to_the_stores() -> None:
    assert HEADQUARTERS_FLEET.branch == HEADQUARTERS
    assert HEADQUARTERS_FLEET.documents is True
    kinds = sorted(vehicle.kind for vehicle in HEADQUARTERS_FLEET.vehicles)
    assert kinds == ["cargo_van", "refrigerated", "refrigerated"]
    assert {vehicle.year for vehicle in HEADQUARTERS_FLEET.vehicles} == {2025}
    assert [vehicle.code for vehicle in HEADQUARTERS_FLEET.vehicles] == [
        "VEH-HQ-01",
        "VEH-HQ-02",
        "VEH-HQ-03",
    ]
    kind_by_code = {vehicle.code: vehicle.kind for vehicle in HEADQUARTERS_FLEET.vehicles}
    assert sorted(driver.vehicle for driver in HEADQUARTERS_FLEET.drivers) == sorted(kind_by_code)
    for driver in HEADQUARTERS_FLEET.drivers:
        kind = kind_by_code[driver.vehicle]
        assert license_issue(driver.license_class, kind, DEFAULT_LICENSE_CLASSES) is None


def test_store_vehicles_keep_their_compliance_override() -> None:
    assert [item.documents for item in FLEET].count(True) == 1


def test_seed_refuses_licenses_the_company_catalogue_forbids() -> None:
    stricter = {**DEFAULT_LICENSE_CLASSES, "cargo_van": frozenset({"pesada"})}
    with pytest.raises(ValueError, match="no permite conducir"):
        validate_fleet_seed(stricter)
    without_vans = {
        kind: classes for kind, classes in DEFAULT_LICENSE_CLASSES.items() if kind != "cargo_van"
    }
    with pytest.raises(ValueError, match="No existe el tipo"):
        validate_fleet_seed(without_vans)


def test_central_warehouse_team_lives_at_headquarters() -> None:
    team = [employee for employee in EMPLOYEES if employee["branch"] == HEADQUARTERS]
    positions = sorted(str(employee["position"]) for employee in team)
    assert positions == ["Auxiliar de Bodega"] * 3 + ["Jefe de Bodega Central"]
    (manager,) = [employee for employee in team if "role" in employee]
    assert manager["code"] == CENTRAL_WAREHOUSE_MANAGER_CODE
    assert manager["role"] == "JEFE DE ALMACÉN"
    assert all(employee["department"] == "Logística y Distribución" for employee in team)


def test_demo_documents_cover_compliance_beyond_the_warning_window() -> None:
    vehicle = HEADQUARTERS_FLEET.vehicles[0]
    documents = vehicle_documents(vehicle.code, vehicle.plate, vehicle.brand, vehicle.model, TODAY)
    driver = HEADQUARTERS_FLEET.drivers[0]
    documents += driver_documents(driver.code, "Nombre", driver.license_class, TODAY)
    by_code = {document.category_code: document for document in documents}
    for code in ("circulation_card", "insurance_policy", "technical_inspection", "driver_license"):
        issued_on, expires_on = by_code[code].issued_on, by_code[code].expires_on
        assert expires_on is not None
        assert expires_on > TODAY + timedelta(days=30)
        assert issued_on is not None
        assert issued_on <= TODAY
    assert by_code["circulation_card"].reference_code == vehicle.plate


def test_demo_documents_are_accepted_as_png(tmp_path) -> None:
    document = vehicle_documents("VEH-HQ-01", "C 3A8-1F4", "Isuzu", "NQR", TODAY)[0]
    payload = render_demo_document(document)
    assert payload == render_demo_document(document)
    path = tmp_path / "card.png"
    path.write_bytes(payload)
    detected, _checksum = inspect_document(path, ".png")
    assert detected == "image/png"
