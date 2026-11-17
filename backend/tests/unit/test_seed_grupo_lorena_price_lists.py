"""Precios de demostración de Grupo Lorena."""

from __future__ import annotations

from decimal import Decimal

from app.domain.entities.sales_margin import margin_percent
from seed.seed_grupo_lorena_price_lists import (
    COUNTER,
    COUNTER_PRICES,
    PREVIOUS_COUNTER_PRICES,
    ROOSEVELT_COFFEE,
    WHOLESALE,
    wholesale_price,
)


def test_lists_keep_the_vat_convention_of_each_channel() -> None:
    assert COUNTER.is_default
    assert COUNTER.prices_include_vat
    assert not WHOLESALE.is_default
    assert not WHOLESALE.prices_include_vat


def test_wholesale_is_ten_percent_below_counter_without_vat() -> None:
    assert wholesale_price(Decimal("11.30"), Decimal("1")) == Decimal("9.00")
    assert wholesale_price(Decimal("0.95"), Decimal("25")) == Decimal("18.92")
    assert all(price > 0 for price in COUNTER_PRICES.values())


#: Costo promedio por unidad base que deja la operación de demostración.
DEMO_COSTS = {
    "PRD-AZU-004": Decimal("1.285"),
    "PRD-CAF-011": Decimal("11.40"),
    "PRD-CHO-006": Decimal("6.949417"),
    "PRD-EMP-009": Decimal("0.544"),
    "PRD-EMP-010": Decimal("0.0635"),
    "PRD-HAR-001": Decimal("24.50"),
    "PRD-HAR-003": Decimal("0.754"),
    "PRD-LAC-002": Decimal("59.583333"),
    "PRD-MAR-008": Decimal("2.06"),
    "PRD-REL-007": Decimal("4.075"),
}


def test_demo_prices_reach_the_target_margins() -> None:
    for sku, cost in DEMO_COSTS.items():
        counter = margin_percent(COUNTER_PRICES[sku], True, cost)
        wholesale = margin_percent(wholesale_price(COUNTER_PRICES[sku], Decimal("1")), False, cost)
        assert counter is not None
        assert counter >= Decimal("35"), (sku, counter)
        assert wholesale is not None
        assert wholesale >= Decimal("20"), (sku, wholesale)
    assert COUNTER_PRICES["PRD-CAF-011"] < ROOSEVELT_COFFEE
    assert set(PREVIOUS_COUNTER_PRICES) <= set(COUNTER_PRICES)
