from decimal import Decimal

import pytest
from app.domain.entities.inventory_preparation import placement_value


def test_partial_placement_allocates_the_exact_accepted_cost():
    first = placement_value(
        total_quantity=Decimal("50"),
        total_value=Decimal("108.123457"),
        posted_quantity=Decimal("0"),
        posted_value=Decimal("0"),
        quantity=Decimal("30"),
    )
    last = placement_value(
        total_quantity=Decimal("50"),
        total_value=Decimal("108.123457"),
        posted_quantity=Decimal("30"),
        posted_value=first,
        quantity=Decimal("20"),
    )
    assert first == Decimal("64.874074")
    assert first + last == Decimal("108.123457")


@pytest.mark.parametrize("quantity", ["0", "-1", "21", "NaN", "Infinity"])
def test_placement_rejects_invalid_or_excessive_quantities(quantity):
    with pytest.raises(ValueError, match="cantidad|costo"):
        placement_value(
            total_quantity=Decimal("50"),
            total_value=Decimal("100"),
            posted_quantity=Decimal("30"),
            posted_value=Decimal("60"),
            quantity=Decimal(quantity),
        )
