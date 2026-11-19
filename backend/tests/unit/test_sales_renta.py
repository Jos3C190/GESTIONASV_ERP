"""Clasificación de renta de una venta (anexos del F-07)."""

from __future__ import annotations

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_renta import RentaClassification, validate_renta


def test_valid_pairs() -> None:
    assert validate_renta(1, 3) == RentaClassification(1, 3)
    assert validate_renta(4, 2) == RentaClassification(4, 2)
    assert validate_renta(12, 12) == RentaClassification(12, 12)


@pytest.mark.parametrize(
    ("operation", "income"),
    [(None, 3), (1, None), (5, 3), (1, 11), (12, 3), (1, 13), (13, 12)],
)
def test_invalid_pairs(operation: int | None, income: int | None) -> None:
    with pytest.raises(BusinessRuleError) as raised:
        validate_renta(operation, income)
    assert raised.value.code == "sales_renta_invalid"
