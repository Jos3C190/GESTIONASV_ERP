"""Precios de demostración de Grupo Lorena."""

from __future__ import annotations

from decimal import Decimal

from seed.seed_grupo_lorena_price_lists import COUNTER, COUNTER_PRICES, WHOLESALE, wholesale_price


def test_lists_keep_the_vat_convention_of_each_channel() -> None:
    assert COUNTER.is_default
    assert COUNTER.prices_include_vat
    assert not WHOLESALE.is_default
    assert not WHOLESALE.prices_include_vat


def test_wholesale_is_ten_percent_below_counter_without_vat() -> None:
    assert wholesale_price(Decimal("11.30"), Decimal("1")) == Decimal("9.00")
    assert wholesale_price(Decimal("0.95"), Decimal("25")) == Decimal("18.92")
    assert all(price > 0 for price in COUNTER_PRICES.values())
