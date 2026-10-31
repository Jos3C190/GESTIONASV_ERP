"""Validation coverage for the enterprise branch editor payload."""

import uuid

import pytest
from app.api.v1.schemas.organization import BranchIn
from pydantic import ValidationError


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


def test_accepts_minimal_administrative_headquarters_without_physical_coordinates() -> None:
    company_id = uuid.uuid4()
    headquarters = BranchIn.model_validate(
        {
            "company_id": company_id,
            "is_headquarters": True,
            "name": "Casa matriz",
        }
    )

    assert headquarters.company_id == company_id
    assert headquarters.code is None
    assert headquarters.latitude is None
    assert headquarters.longitude is None


def test_headquarters_coordinates_must_be_both_present_or_both_empty() -> None:
    with pytest.raises(ValidationError, match="ambas coordenadas"):
        BranchIn.model_validate(
            {
                "company_id": uuid.uuid4(),
                "is_headquarters": True,
                "name": "Casa matriz",
                "latitude": 13.7,
            }
        )


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
