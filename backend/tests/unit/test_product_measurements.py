from decimal import Decimal

import pytest
from app.api.v1.schemas.catalog import ProductCreate
from app.domain.product_measurements import (
    DIMENSION_UNITS,
    WEIGHT_UNITS,
    calculate_volume,
    format_dimension_summary,
    validate_measurements,
)
from pydantic import ValidationError


def test_fixed_units_are_independent_and_volume_is_normalized_to_cubic_metres() -> None:
    assert tuple(DIMENSION_UNITS) == ("mm", "cm", "m", "in", "ft")
    assert tuple(WEIGHT_UNITS) == ("mg", "g", "kg", "t", "oz", "lb")
    assert calculate_volume(Decimal("20"), Decimal("30"), Decimal("10"), "cm") == Decimal("0.006")
    assert calculate_volume(Decimal("1"), Decimal("1"), Decimal("1"), "m") == Decimal("1")
    assert calculate_volume(Decimal("1"), Decimal("1"), Decimal("1"), "mm") == Decimal("0.000000001")


def test_incomplete_dimensions_are_valid_but_volume_is_not_calculable() -> None:
    values = validate_measurements(dimension_length="20", dimension_unit="cm")
    assert values[:3] == (Decimal("20"), None, None)
    assert calculate_volume(*values[:3], "cm") is None
    assert format_dimension_summary(*values[:3], "cm") == "20 × — × — cm"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"dimension_length": "-1"}, "no negativo"),
        ({"dimension_length": "1.2345"}, "tres decimales"),
        ({"dimension_length": "20"}, "unidad de dimensión"),
        ({"dimension_unit": "yard"}, "sin medidas"),
        ({"weight": "2"}, "unidad de peso"),
        ({"weight_unit": "kg"}, "sin peso"),
    ],
)
def test_measurement_validation_rejects_invalid_pairs(kwargs: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_measurements(**kwargs)


def test_product_write_schema_rejects_legacy_free_text_dimensions() -> None:
    with pytest.raises(ValidationError, match="dimensions"):
        ProductCreate(
            id_category=1,
            sku="SKU-1",
            name="Producto",
            purchase_unit=1,
            sale_unit=1,
            dimensions="20 x 30 cm",
        )
