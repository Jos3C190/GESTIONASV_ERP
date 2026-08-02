"""Validation coverage for the enterprise branch editor payload."""

import uuid

import pytest
from pydantic import ValidationError

from app.api.v1.schemas.organization import BranchIn


def _branch_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "company_id": uuid.uuid4(),
        "code": "SAL-01",
        "name": "Sucursal Centro",
        "address": "Centro de San Salvador",
        "department_id": uuid.uuid4(),
        "municipality_id": uuid.uuid4(),
        "district_id": uuid.uuid4(),
        "latitude": 13.6989,
        "longitude": -89.1914,
    }
    payload.update(overrides)
    return payload


def test_accepts_decimal_coordinates_and_enterprise_profile() -> None:
    branch = BranchIn.model_validate(
        _branch_payload(
            area=1_000.50,
            area_built=700.25,
            area_unbuilt=300.25,
            electrical_capacity_kva=225.5,
            appraised_value=950_000.75,
            internet_provider="Proveedor empresarial",
            schedule=[{"day": "Lunes", "open": "08:00", "close": "17:00"}],
        )
    )

    assert branch.latitude == 13.6989
    assert branch.longitude == -89.1914
    assert branch.electrical_capacity_kva == 225.5


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"area": 100, "area_built": 101}, "área construida"),
        (
            {"schedule": [{"day": "Lunes", "open": "17:00", "close": "08:00"}]},
            "apertura",
        ),
        (
            {
                "schedule": [
                    {"day": "Lunes", "open": "08:00", "close": "17:00"},
                    {"day": "Lunes", "open": "09:00", "close": "18:00"},
                ]
            },
            "repetir días",
        ),
    ],
)
def test_rejects_inconsistent_enterprise_data(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        BranchIn.model_validate(_branch_payload(**overrides))
