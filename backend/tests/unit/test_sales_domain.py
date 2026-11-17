from decimal import Decimal

import pytest
from app.domain.entities.sales import (
    line_amount,
    normalize_price,
    normalize_quantity,
    quantity_in_base,
)
from app.infrastructure.repositories.sales_line_identity import unit_label as _unit_label


def test_unit_label_does_not_repeat_a_symbol_already_in_the_name() -> None:
    assert _unit_label("Unidad (u)", "u") == "Unidad (u)"
    assert _unit_label("Unidad", "u") == "Unidad (u)"
    assert _unit_label("u", "u") == "u"
    assert _unit_label("Caja (cj)", "cj") == "Caja (cj)"


def test_quantity_and_price_require_finite_values_at_supported_precision() -> None:
    assert normalize_quantity(Decimal("2.500000")) == Decimal("2.500000")
    assert normalize_price(Decimal("0")) == Decimal("0.000000")
    with pytest.raises(ValueError, match="mayor que cero"):
        normalize_quantity(Decimal("0"))
    with pytest.raises(ValueError, match="seis decimales"):
        normalize_quantity(Decimal("1.0000001"))
    with pytest.raises(ValueError, match="número finito"):
        normalize_price(Decimal("NaN"))


def test_base_quantity_uses_the_explicit_conversion_factor() -> None:
    assert quantity_in_base(Decimal("2.5"), Decimal("12")) == Decimal("30.000000")
    with pytest.raises(ValueError, match="más de seis decimales"):
        quantity_in_base(Decimal("0.333333"), Decimal("0.333333"))


def test_each_commercial_line_rounds_half_up_to_cents() -> None:
    assert line_amount(Decimal("3"), Decimal("1.255")) == Decimal("3.77")
