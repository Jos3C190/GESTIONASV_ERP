"""V4a: reglas del responsable y de la activación de una contingencia."""

from __future__ import annotations

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.fiscal_contingency import (
    ContingencyResponsible,
    validate_activation,
    validate_responsible,
)


def test_responsible_is_trimmed_and_validated() -> None:
    assert validate_responsible("  Ana Rivas ", "13", " 01234567-8 ") == ContingencyResponsible(
        "Ana Rivas", "13", "01234567-8"
    )
    for args in (
        ("AB", "13", "1"),
        ("Ana Rivas", "99", "1"),
        ("Ana Rivas", "13", " "),
        ("Ana Rivas", "13", "9" * 26),
    ):
        with pytest.raises(BusinessRuleError) as raised:
            validate_responsible(*args)
        assert raised.value.code == "sales_contingency_responsible_invalid"


def test_activation_needs_a_catalogue_type_and_a_reason_for_other() -> None:
    assert validate_activation(4, None) is None
    assert validate_activation(2, "  Sin internet en la tienda  ") == "Sin internet en la tienda"
    assert validate_activation(5, "Inundación en el local") == "Inundación en el local"
    with pytest.raises(BusinessRuleError) as raised:
        validate_activation(6, None)
    assert raised.value.code == "sales_contingency_type_invalid"
    for reason in (None, "  ", "abc"):
        with pytest.raises(BusinessRuleError) as raised:
            validate_activation(5, reason)
        assert raised.value.code == "sales_contingency_reason_required"
    with pytest.raises(BusinessRuleError):
        validate_activation(1, "x" * 501)
