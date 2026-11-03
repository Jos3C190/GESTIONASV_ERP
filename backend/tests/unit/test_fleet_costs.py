"""The cost report's arithmetic and what a contract does to a vehicle's fitness."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.application.fleet.costs import (
    cost_per_unit,
    period_bounds,
    period_distance,
    report_rows,
    report_totals,
)
from app.application.fleet.dispatch import HARD_BLOCKS
from app.application.fleet.views import contract_issues

TODAY = date(2026, 11, 3)


def _vehicle(vehicle_id: str, *, retired: bool = False) -> dict[str, object]:
    return {"vehicle_id": vehicle_id, "code": vehicle_id.upper(), "retired": retired}


def test_owned_vehicles_and_contracts_without_a_date_raise_nothing() -> None:
    assert contract_issues("owned", TODAY - timedelta(days=1), "active", TODAY) == []
    assert contract_issues("rented", None, "active", TODAY) == []
    assert contract_issues("rented", TODAY - timedelta(days=1), "retired", TODAY) == []


def test_contract_warns_until_its_last_day_and_blocks_the_day_after() -> None:
    far = contract_issues("leased", TODAY + timedelta(days=31), "active", TODAY)
    assert far == []
    assert contract_issues("leased", TODAY + timedelta(days=30), "active", TODAY)[0].severity == (
        "warning"
    )
    assert contract_issues("leased", TODAY, "active", TODAY)[0].code == "contract_expiring"
    expired = contract_issues("leased", TODAY - timedelta(days=1), "active", TODAY)[0]
    assert (expired.code, expired.severity) == ("contract_expired", "blocking")


def test_an_expired_contract_can_be_authorized_at_dispatch() -> None:
    assert "contract_expired" not in HARD_BLOCKS


def test_period_covers_whole_local_days() -> None:
    start, end = period_bounds(date(2026, 11, 1), date(2026, 11, 30))
    assert start.isoformat() == "2026-11-01T00:00:00-06:00"
    assert end.isoformat() == "2026-12-01T00:00:00-06:00"


def test_distance_crosses_a_meter_replacement() -> None:
    readings = [
        (Decimal("1000"), "manual"),
        (Decimal("1500"), "fuel"),
        (Decimal("0"), "meter_replacement"),
        (Decimal("200"), "manual"),
    ]
    assert period_distance(readings) == Decimal("700")
    assert period_distance([]) == Decimal("0")


def test_cost_per_unit_needs_distance() -> None:
    assert cost_per_unit(Decimal("100"), Decimal("0")) is None
    assert cost_per_unit(Decimal("100"), Decimal("400")) == Decimal("0.2500")


def test_rows_add_up_and_sort_by_cost() -> None:
    rows = report_rows(
        [_vehicle("a"), _vehicle("b")],
        fuel={"a": Decimal("10")},
        maintenance={"b": Decimal("50")},
        other={"a": Decimal("5")},
        distance={"a": Decimal("100")},
    )
    assert [row["vehicle_id"] for row in rows] == ["b", "a"]
    assert rows[1]["total"] == Decimal("15")
    assert rows[1]["cost_per_unit"] == Decimal("0.1500")
    assert rows[0]["cost_per_unit"] is None
    assert "retired" not in rows[0]
    assert report_totals(rows) == {
        "fuel": Decimal("10"),
        "maintenance": Decimal("50"),
        "other": Decimal("5"),
        "total": Decimal("65"),
    }


def test_a_retired_vehicle_only_appears_if_it_cost_something() -> None:
    vehicles = [_vehicle("idle", retired=True), _vehicle("paid", retired=True), _vehicle("new")]
    rows = report_rows(
        vehicles,
        fuel={},
        maintenance={},
        other={"paid": Decimal("20")},
        distance={},
    )
    assert [row["vehicle_id"] for row in rows] == ["paid", "new"]
