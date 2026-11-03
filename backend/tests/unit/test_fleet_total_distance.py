"""Distance over a vehicle's life, across meter replacements."""

from __future__ import annotations

from decimal import Decimal

from app.application.fleet.operations import total_distance


def test_no_readings_is_zero() -> None:
    assert total_distance([]) == Decimal("0")


def test_a_single_meter_counts_its_span() -> None:
    readings = [(Decimal("100"), "manual"), (Decimal("250"), "fuel")]

    assert total_distance(readings) == Decimal("150")


def test_replacements_add_each_span() -> None:
    readings = [
        (Decimal("100"), "manual"),
        (Decimal("500"), "manual"),
        (Decimal("10"), "meter_replacement"),
        (Decimal("40"), "manual"),
    ]

    assert total_distance(readings) == Decimal("430")


def test_a_replacement_with_no_later_reading_adds_nothing() -> None:
    readings = [(Decimal("100"), "manual"), (Decimal("7"), "meter_replacement")]

    assert total_distance(readings) == Decimal("0")
