from collections import Counter
from dataclasses import replace
from decimal import Decimal

import pytest
from app.api.v1.schemas.fleet import normalize_plate
from app.application.fleet.compliance import license_issue
from seed import grupo_lorena_operations_data as data
from seed.grupo_lorena_operations_data import (
    CENTRAL_BLOCKS,
    CONSOLIDATIONS,
    EXTRA_FLEET,
    HQ_STAFF,
    LICENSE_CLASSES,
    PRODUCTS,
    STORE_STAFF,
    TRANSFERS,
    ZONE_LIMITS,
    demand,
    marker,
    pallet_measures,
    pallets,
    plate_problem,
    received_quantities,
    validate_operations_seed,
)
from seed.seed_grupo_lorena import BRANCHES, EMPLOYEES
from seed.seed_grupo_lorena_fleet import FLEET, PLATE_2011, PLATE_ALPHANUMERIC

EXTRA_VEHICLES = [vehicle for item in EXTRA_FLEET for vehicle in item.vehicles]


def test_the_operations_seed_is_consistent() -> None:
    validate_operations_seed()


def test_people_are_unique_and_do_not_clash_with_the_base_seeds() -> None:
    people = (*HQ_STAFF, *STORE_STAFF)
    codes = [person.code for person in people]
    names = [f"{person.first} {person.last}" for person in people]
    base_codes = {str(e["code"]) for e in EMPLOYEES} | {
        driver.code for item in FLEET for driver in item.drivers
    }
    assert len(codes) == len(set(codes))
    assert len(names) == len(set(names))
    assert not base_codes & set(codes)


def test_every_store_has_a_sensible_team() -> None:
    team: Counter[str] = Counter()
    for employee in EMPLOYEES:
        if not employee.get("all_branches"):
            team[str(employee["branch"])] += 1
    for item in FLEET:
        team[item.branch] += len(item.drivers)
    for person in STORE_STAFF:
        team[person.branch] += 1
    for branch in BRANCHES:
        assert 7 <= team[branch.code] <= 10, branch.code
        positions = {p.position for p in STORE_STAFF if p.branch == branch.code}
        assert {"Cajera", "Panadero", "Auxiliar de Bodega"} <= positions


def test_only_repartidores_with_a_vehicle_are_drivers() -> None:
    drivers = {driver.code for item in EXTRA_FLEET for driver in item.drivers}
    repartidores = {p.code for p in STORE_STAFF if p.position == data.DRIVER_POSITION}
    assert drivers == repartidores


def test_new_plates_follow_the_salvadoran_rules() -> None:
    assert all(normalize_plate(vehicle.plate) == vehicle.plate for vehicle in EXTRA_VEHICLES)
    assert all(plate_problem(vehicle) is None for vehicle in EXTRA_VEHICLES)
    for vehicle in EXTRA_VEHICLES:
        pattern = PLATE_ALPHANUMERIC if vehicle.year >= 2025 else PLATE_2011
        assert pattern.match(vehicle.plate)
    motorcycles = [vehicle for vehicle in EXTRA_VEHICLES if vehicle.kind == "motorcycle"]
    assert motorcycles
    assert all(vehicle.plate.startswith("M ") for vehicle in motorcycles)
    plates = [v.plate for item in (*FLEET, *EXTRA_FLEET) for v in item.vehicles]
    assert len(plates) == len(set(plates))


@pytest.mark.parametrize(
    ("plate", "kind", "year"),
    [
        ("C 2A4-B17", "motorcycle", 2025),  # clase de carga en una moto
        ("M 412-068", "motorcycle", 2025),  # formato de 2011 en serie nueva
        ("M 2A4-B17", "motorcycle", 2023),  # serie nueva antes de 2025
        ("M 318-275", "pickup", 2022),  # pickup con placa de moto
    ],
)
def test_incoherent_plates_are_rejected(plate: str, kind: str, year: int) -> None:
    vehicle = replace(EXTRA_VEHICLES[0], plate=plate, kind=kind, year=year)
    assert plate_problem(vehicle) is not None


def test_drivers_hold_a_license_for_their_vehicle() -> None:
    for item in EXTRA_FLEET:
        kinds = {vehicle.code: vehicle.kind for vehicle in item.vehicles}
        for driver in item.drivers:
            assert (
                license_issue(driver.license_class, kinds[driver.vehicle], LICENSE_CLASSES) is None
            )
    assert license_issue("liviana", "motorcycle", LICENSE_CLASSES) is not None


def test_pallets_fit_their_storage_positions_and_add_up() -> None:
    zone_positions = {block.key: block.size for block in CENTRAL_BLOCKS}
    used: Counter[str] = Counter()
    for sku, quantity in received_quantities().items():
        portions = pallets(sku, quantity)
        assert sum(portions) == quantity
        limits = ZONE_LIMITS[PRODUCTS[sku].zone]
        for portion in portions:
            weight, volume = pallet_measures(sku, portion)
            assert weight <= limits.operational_weight, sku
            assert volume <= limits.operational_volume, sku
            used[PRODUCTS[sku].zone] += 1
    assert all(count <= zone_positions[zone] for zone, count in used.items())


def test_capacity_check_rejects_an_oversized_pallet(monkeypatch: pytest.MonkeyPatch) -> None:
    oversized = replace(PRODUCTS["PRD-MAR-008"], unit_weight_kg=Decimal("25"))
    monkeypatch.setattr(data, "PRODUCTS", {**PRODUCTS, "PRD-MAR-008": oversized})
    with pytest.raises(ValueError, match="excede la capacidad"):
        data._validate_capacity()


def test_awards_cover_closed_consolidations_with_quoted_offers() -> None:
    for seed in CONSOLIDATIONS:
        quoted = {(quote.supplier, sku) for quote in seed.quotes for sku in quote.prices}
        assert all((supplier, sku) in quoted for sku, supplier in seed.awards.items())
        if seed.close:
            assert set(seed.awards) == set(demand(seed))
    keys = [marker(request.key) for seed in CONSOLIDATIONS for request in seed.requests]
    assert len(keys) == len(set(keys))


def test_the_import_carries_dai_on_the_cif_value() -> None:
    imported = next(seed for seed in CONSOLIDATIONS if seed.key == "C")
    order = next(order for order in imported.orders if order.supplier == "PROV-IMP-001")
    quote = next(quote for quote in imported.quotes if quote.supplier == "PROV-IMP-001")
    assert order.receipt is not None
    retaceo = order.receipt.retaceo
    fob = quote.prices["PRD-CHO-006"] * demand(imported)["PRD-CHO-006"]
    assert retaceo.dai == ((fob + retaceo.freight) * Decimal("0.15")).quantize(Decimal("0.01"))
    assert quote.tax_rate == 0
    assert order.actual


def test_transfers_move_whole_received_pallets() -> None:
    received = received_quantities()
    for transfer in TRANSFERS:
        for sku, quantity in transfer.lines:
            sizes = {p * PRODUCTS[sku].per_purchase_unit for p in pallets(sku, received[sku])}
            assert quantity in sizes
    assert {transfer.state for transfer in TRANSFERS} == {"received", "preparation"}
