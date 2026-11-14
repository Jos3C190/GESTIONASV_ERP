"""A rerun of the Grupo Lorena seed must not revert what operators configured."""

import uuid

from app.infrastructure.models.organization import Location, UserCompany, Warehouse
from seed.seed_grupo_lorena import (
    BRANCHES,
    STORE_LOCATIONS,
    _fill_empty,
    _reconcile_store_location,
    _reconcile_store_warehouse,
    _store_location_configuration,
    _store_warehouse_configuration,
)

OPERATOR_WAREHOUSE = {
    "warehouse_type": "cold_storage",
    "operational_status": "maintenance",
    "area": 120,
    "height": 6.5,
    "shelves_total": 4,
    "certified_max_weight_kg": 40_000,
    "operational_max_weight_kg": 32_000,
    "certified_usable_volume_m3": 300,
    "operational_usable_volume_m3": 250,
    "capacity_profile": "cold",
    "capacity_enforcement_mode": "disabled",
    "storage_eligible": False,
    "shifts": ["noche"],
    "cameras": 6,
    "access_control": "biometrico",
    "has_alarm": False,
    "fire_system": [],
    "temperature_range": "2 °C a 6 °C",
    "humidity_range": "80 % a 90 %",
    "cooling": "camara_fria",
    "has_ventilation": False,
    "physical_location": "Nave 2",
    "description": "Configurada por operaciones.",
}

OPERATOR_LOCATION = {
    "aisle": "A01",
    "rack": "R03",
    "level": "N02",
    "position": "P04",
    "location_type": "reserve",
    "certified_max_weight_kg": 2_500,
    "operational_max_weight_kg": 2_000,
    "certified_usable_volume_m3": 12,
    "operational_usable_volume_m3": 10,
    "capacity_profile": "general_mixed",
    "capacity_enforcement_mode": "enforce",
    "storage_eligible": True,
    "usable_length_m": 2.4,
    "usable_width_m": 1.2,
    "usable_height_m": 1.8,
    "notes": "Rack de reserva.",
}


def _warehouse(**values: object) -> Warehouse:
    warehouse = Warehouse(code="BOD-SM-01", name="Bodega")
    for field, value in values.items():
        setattr(warehouse, field, value)
    return warehouse


def test_rerun_keeps_the_capacity_setup_of_an_existing_warehouse() -> None:
    manager_id = uuid.uuid4()
    original_manager = uuid.uuid4()
    warehouse = _warehouse(**OPERATOR_WAREHOUSE, manager_employee_id=original_manager)
    _reconcile_store_warehouse(
        warehouse, created=False, index=1, branch_seed=BRANCHES[0], manager_id=manager_id
    )
    for field, value in OPERATOR_WAREHOUSE.items():
        assert getattr(warehouse, field) == value, field
    assert warehouse.manager_employee_id == original_manager
    assert warehouse.name == "Bodega de tienda San Miguel"
    assert warehouse.is_active is True


def test_rerun_only_fills_empty_descriptive_fields_of_a_warehouse() -> None:
    manager_id = uuid.uuid4()
    warehouse = _warehouse(capacity_profile="rack")
    _reconcile_store_warehouse(
        warehouse, created=False, index=1, branch_seed=BRANCHES[0], manager_id=manager_id
    )
    assert warehouse.manager_employee_id == manager_id
    assert warehouse.physical_location == "Área posterior de la sucursal"
    assert warehouse.description
    assert warehouse.capacity_profile == "rack"
    assert warehouse.certified_max_weight_kg is None


def test_new_warehouse_gets_the_canonical_setup() -> None:
    warehouse = _warehouse()
    _reconcile_store_warehouse(
        warehouse, created=True, index=2, branch_seed=BRANCHES[1], manager_id=uuid.uuid4()
    )
    for field, value in _store_warehouse_configuration(2).items():
        assert getattr(warehouse, field) == value, field
    assert warehouse.code == "BOD-USU-01"


def test_rerun_keeps_the_type_and_capacity_of_an_existing_location() -> None:
    location = Location(code="REC-01")
    for field, value in OPERATOR_LOCATION.items():
        setattr(location, field, value)
    _reconcile_store_location(location, created=False, position=1, seed_location=STORE_LOCATIONS[0])
    for field, value in OPERATOR_LOCATION.items():
        assert getattr(location, field) == value, field
    assert location.is_active is True


def test_new_location_gets_the_canonical_setup() -> None:
    for position, seed_location in enumerate(STORE_LOCATIONS, start=1):
        location = Location(code=f"{seed_location.aisle}-{position:02d}")
        _reconcile_store_location(
            location, created=True, position=position, seed_location=seed_location
        )
        for field, value in _store_location_configuration(position, seed_location).items():
            assert getattr(location, field) == value, field
        assert location.notes


def test_default_branch_is_filled_but_never_overridden() -> None:
    headquarters, chosen = uuid.uuid4(), uuid.uuid4()
    empty = UserCompany(user_id=uuid.uuid4(), company_id=uuid.uuid4(), last_branch_id=None)
    _fill_empty(empty, {"last_branch_id": headquarters})
    assert empty.last_branch_id == headquarters
    chosen_membership = UserCompany(
        user_id=uuid.uuid4(), company_id=uuid.uuid4(), last_branch_id=chosen
    )
    _fill_empty(chosen_membership, {"last_branch_id": headquarters})
    assert chosen_membership.last_branch_id == chosen
