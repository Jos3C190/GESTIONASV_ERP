"""Reglas de validación del contrato de almacenes."""

import uuid
from datetime import date

import pytest
from app.api.v1.schemas.organization import WarehouseCategoryIn, WarehouseIn
from pydantic import ValidationError


def warehouse_payload(**overrides):
    payload = {
        "branch_id": uuid.uuid4(),
        "warehouse_category_id": uuid.uuid4(),
        "code": "ALM-01",
        "name": "Almacén principal",
    }
    payload.update(overrides)
    return payload


def test_warehouse_category_requires_company_boundary():
    company_id = uuid.uuid4()
    category = WarehouseCategoryIn.model_validate(
        {"company_id": company_id, "name": "Producto terminado"}
    )

    assert category.company_id == company_id

    with pytest.raises(ValidationError):
        WarehouseCategoryIn.model_validate({"name": "Sin empresa"})


def test_accepts_complete_operational_data():
    warehouse = WarehouseIn.model_validate(
        warehouse_payload(
            warehouse_type="cold_storage",
            is_central=True,
            shifts=["mañana", "noche"],
            access_control="biometrico",
            cooling="refrigeracion",
            last_maintenance=date(2026, 1, 10),
            next_maintenance=date(2026, 6, 10),
            sanitary_permit="PS-2026-01",
            sanitary_permit_expiry=date(2027, 1, 10),
        )
    )

    assert warehouse.shifts == ["mañana", "noche"]
    assert warehouse.is_central is True


def test_warehouse_defaults_to_not_central():
    warehouse = WarehouseIn.model_validate(warehouse_payload())

    assert warehouse.is_central is False


def test_accepts_central_warehouse_assigned_to_a_branch():
    warehouse = WarehouseIn.model_validate(
        warehouse_payload(is_central=True, manager_employee_id=None)
    )

    assert warehouse.branch_id is not None
    assert warehouse.is_central is True


def test_requires_branch_for_every_warehouse():
    with pytest.raises(ValidationError, match="Todo almacén debe pertenecer a una sucursal"):
        WarehouseIn.model_validate(warehouse_payload(branch_id=None))


def test_central_flag_does_not_remove_warehouse_branch_assignment():
    branch_id = uuid.uuid4()
    warehouse = WarehouseIn.model_validate(
        warehouse_payload(branch_id=branch_id, is_central=True)
    )

    assert warehouse.branch_id == branch_id


@pytest.mark.parametrize("shifts", [["mañana", "mañana"], ["madrugada"]])
def test_rejects_invalid_or_repeated_shifts(shifts):
    with pytest.raises(ValidationError):
        WarehouseIn.model_validate(warehouse_payload(shifts=shifts))


def test_rejects_maintenance_date_inversion():
    with pytest.raises(ValidationError):
        WarehouseIn.model_validate(
            warehouse_payload(
                last_maintenance=date(2026, 8, 1),
                next_maintenance=date(2026, 7, 1),
            )
        )


def test_requires_permit_when_expiry_is_present():
    with pytest.raises(ValidationError):
        WarehouseIn.model_validate(warehouse_payload(sanitary_permit_expiry=date(2027, 1, 1)))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("warehouse_type", "unknown"),
        ("access_control", "retina_experimental"),
        ("cooling", "unknown"),
    ],
)
def test_rejects_unknown_catalog_values(field, value):
    with pytest.raises(ValidationError):
        WarehouseIn.model_validate(warehouse_payload(**{field: value}))
