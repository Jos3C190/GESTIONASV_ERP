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
