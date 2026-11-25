"""Pedido del ingeniero: promociones por sucursal y salida con unidades completas."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.application.sales.deliveries import SalesDeliveryService
from app.core.exceptions import BusinessRuleError, ConflictError
from app.domain.entities.sales_margin import (
    BranchPromotion,
    require_no_overlap,
    require_promotion,
)

D = Decimal
TODAY = date(2026, 11, 24)


def promo(start: date, end: date | None, *, ended: bool = False) -> BranchPromotion:
    return BranchPromotion(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        product_id=1,
        discount_percent=D("10"),
        valid_from=start,
        valid_to=end,
        ended=ended,
    )


def test_promotion_covers_its_days_until_it_ends() -> None:
    current = promo(date(2026, 11, 20), date(2026, 11, 30))
    assert current.covers(TODAY)
    assert not current.covers(date(2026, 12, 1))
    assert promo(TODAY, None).covers(date(2027, 6, 1))
    assert not promo(date(2026, 11, 20), None, ended=True).covers(TODAY)


@pytest.mark.parametrize(
    ("percent", "start", "end", "code"),
    [
        ("0", TODAY, None, "sales_promotion_percent_invalid"),
        ("100", TODAY, None, "sales_promotion_percent_invalid"),
        ("10", date(2026, 11, 23), None, "sales_promotion_backdated"),
        ("10", TODAY, date(2026, 11, 23), "sales_promotion_validity_invalid"),
    ],
)
def test_promotion_rules(percent: str, start: date, end: date | None, code: str) -> None:
    with pytest.raises(BusinessRuleError) as error:
        require_promotion(D(percent), start, end, TODAY)
    assert error.value.code == code


def test_one_promotion_per_product_and_branch_per_day() -> None:
    existing = [promo(date(2026, 11, 20), date(2026, 11, 30))]
    require_no_overlap(existing, date(2026, 12, 1), None)
    require_no_overlap([promo(date(2026, 11, 20), None, ended=True)], TODAY, None)
    with pytest.raises(ConflictError) as error:
        require_no_overlap(existing, date(2026, 11, 25), date(2026, 12, 5))
    assert error.value.code == "sales_promotion_overlap"
    with pytest.raises(ConflictError):
        require_no_overlap([promo(date(2026, 12, 10), None)], TODAY, None)


def unit(quantity: str) -> dict[str, object]:
    return {"handling_unit_id": uuid.uuid4(), "quantity_base": D(quantity)}


def test_whole_units_cover_exactly_or_nothing() -> None:
    pick = SalesDeliveryService._whole_units_for
    boxes = [unit("3"), unit("2"), unit("5")]
    assert [u["quantity_base"] for u in pick(D("5"), boxes)] == [D("3"), D("2")]
    # Una caja más grande que lo que falta se salta: no se parte.
    assert [u["quantity_base"] for u in pick(D("2"), boxes)] == [D("2")]
    assert pick(D("2.5"), boxes) == []
    assert pick(D("11"), boxes) == []
