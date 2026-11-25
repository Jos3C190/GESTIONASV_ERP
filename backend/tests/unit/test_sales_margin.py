"""Margen, precio sugerido, escalas, topes y evaluación con valores exactos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_margin import (
    NONE_ALLOWED,
    UNLIMITED,
    AuthorizationReason,
    DiscountPolicy,
    DiscountSource,
    VolumeScale,
    effective_policy,
    evaluate_global,
    evaluate_line,
    margin_percent,
    pick_volume_discount,
    require_volume_scale,
    suggested_discount,
    suggested_price,
    target_margin_for,
)

D = Decimal
DAY = date(2026, 11, 16)


def test_margin_is_measured_on_the_price_without_vat() -> None:
    assert margin_percent(D("10.00"), False, D("7.00")) == D("30.00")
    assert margin_percent(D("11.30"), True, D("7.00")) == D("30.00")
    assert margin_percent(D("2.10"), True, D("1.40")) == D("24.67")
    assert margin_percent(D("5"), False, D("6")) == D("-20.00")
    assert margin_percent(D("5"), False, None) is None
    assert margin_percent(D("0"), False, D("1")) is None


def test_suggested_price_reaches_the_target_margin() -> None:
    assert suggested_price(D("7.00"), D("30"), False) == D("10.00")
    assert suggested_price(D("7.00"), D("30"), True) == D("11.30")
    assert suggested_price(D("1.40"), D("0"), False) == D("1.40")
    with pytest.raises(BusinessRuleError) as exc:
        suggested_price(D("1"), D("96"), False)
    assert exc.value.code == "sales_margin_target_invalid"


def test_category_margin_wins_over_list_margin() -> None:
    assert target_margin_for(D("35"), {7: D("20")}, 7) == D("20")
    assert target_margin_for(D("35"), {7: D("20")}, 8) == D("35")
    assert target_margin_for(None, {}, None) is None


def test_volume_scale_takes_the_highest_reached_and_in_force() -> None:
    scales = [
        VolumeScale(D("10"), D("3"), date(2026, 1, 1), None),
        VolumeScale(D("50"), D("6"), date(2026, 1, 1), None),
        VolumeScale(D("100"), D("9"), date(2026, 12, 1), None),
    ]
    assert pick_volume_discount(scales, D("9"), DAY) is None
    assert pick_volume_discount(scales, D("10"), DAY) == scales[0]
    assert pick_volume_discount(scales, D("120"), DAY) == scales[1]
    assert pick_volume_discount(scales, D("120"), date(2026, 12, 2)) == scales[2]
    for quantity, percent, code in (
        (D("0"), D("3"), "sales_volume_quantity_invalid"),
        (D("1"), D("0"), "sales_volume_percent_invalid"),
    ):
        with pytest.raises(BusinessRuleError) as exc:
            require_volume_scale(quantity, percent)
        assert exc.value.code == code


def test_suggested_discount_is_the_larger_not_the_sum() -> None:
    scale = VolumeScale(D("10"), D("6"), DAY, None)
    assert suggested_discount(D("5"), scale).percent == D("6")
    assert suggested_discount(D("5"), scale).source is DiscountSource.VOLUME
    assert suggested_discount(D("8"), scale).source is DiscountSource.CUSTOMER
    assert suggested_discount(D("0"), None).source is DiscountSource.NONE


def test_user_policy_is_the_maximum_of_their_roles() -> None:
    cashier = DiscountPolicy(D("5"), D("0"))
    manager = DiscountPolicy(D("10"), D("5"))
    combined = effective_policy([cashier, manager], is_superuser=False)
    assert combined == DiscountPolicy(D("10"), D("5"))
    assert effective_policy([], is_superuser=False) == NONE_ALLOWED
    assert effective_policy([], is_superuser=True) == UNLIMITED


def test_line_authorization_and_below_cost() -> None:
    policy = DiscountPolicy(D("5"), D("2"))
    within = evaluate_line(D("11.30"), True, D("5"), D("7.00"), policy)
    assert within.net_price == D("10.73500000")
    assert within.margin_percent == D("26.32")
    assert not within.requires_authorization

    above = evaluate_line(D("11.30"), True, D("8"), D("7.00"), policy)
    assert above.reasons == (AuthorizationReason.DISCOUNT_ABOVE_LIMIT,)

    # Bajo costo no se autoriza: se marca para bloquearlo, sin importar el rol.
    below = evaluate_line(D("10.00"), False, D("5"), D("9.60"), policy)
    assert below.below_cost
    assert below.reasons == ()
    assert evaluate_line(D("10.00"), False, D("5"), D("9.60"), UNLIMITED).below_cost
    assert not within.below_cost

    no_cost = evaluate_line(D("10.00"), False, D("0"), None, NONE_ALLOWED)
    assert no_cost.margin_percent is None
    assert not no_cost.requires_authorization

    assert evaluate_global(D("3"), policy) == (AuthorizationReason.GLOBAL_DISCOUNT_ABOVE_LIMIT,)
    assert evaluate_global(D("2"), policy) == ()
    with pytest.raises(BusinessRuleError):
        evaluate_line(D("1"), False, D("101"), None, UNLIMITED)
