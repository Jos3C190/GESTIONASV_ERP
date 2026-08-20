from decimal import Decimal

import pytest
from app.domain.entities.capacity_hierarchy import (
    CapacityConfiguration,
    CapacityUsageSnapshot,
    compare_child_to_parent,
    limits_below_usage,
    nominal_allocation_issues,
    requires_usage_validation,
)


def config(weight: str | None, volume: str | None) -> CapacityConfiguration:
    return CapacityConfiguration(
        certified_weight=Decimal(weight) if weight else None,
        operational_weight=Decimal(weight) if weight else None,
        certified_volume=Decimal(volume) if volume else None,
        operational_volume=Decimal(volume) if volume else None,
        enforcement_mode="enforce",
    )


def test_child_limits_compare_like_for_like_without_summing() -> None:
    issues = compare_child_to_parent(
        child=config("101", "9"),
        parent=config("100", "10"),
        scope_type="location",
        scope_id="child",
        parent_scope_type="capacity_group",
        parent_scope_id="parent",
    )
    assert {(issue.metric, issue.limit_kind) for issue in issues} == {
        ("weight", "certified"),
        ("weight", "operational"),
    }
    assert all(issue.code == "capacity_child_limit_exceeds_parent" for issue in issues)


def test_missing_parent_metric_is_diagnostic_not_error() -> None:
    issues = compare_child_to_parent(
        child=config("100", "10"),
        parent=CapacityConfiguration(),
        scope_type="location",
        scope_id="child",
        parent_scope_type="warehouse",
        parent_scope_id="parent",
    )
    assert len(issues) == 4
    assert all(issue.severity == "warning" for issue in issues)
    assert all(issue.code == "parent_limit_not_configured" for issue in issues)


def test_nominal_overallocation_warns_but_does_not_become_parent_error() -> None:
    issues = nominal_allocation_issues(
        parent=config("100", "10"),
        children=(config("60", "6"), config("60", "6")),
        scope_type="capacity_group",
        scope_id="rack-a",
    )
    assert len(issues) == 4
    assert all(issue.severity == "warning" for issue in issues)
    assert all(issue.allocation_ratio_pct == Decimal("120") for issue in issues)


def test_reduction_and_enforcement_require_usage_validation() -> None:
    assert requires_usage_validation(config("100", "10"), config("90", "10"))
    previous = CapacityConfiguration(
        certified_weight=Decimal("100"),
        operational_weight=Decimal("90"),
        certified_volume=Decimal("10"),
        operational_volume=Decimal("9"),
        enforcement_mode="observe",
    )
    proposed = CapacityConfiguration(
        certified_weight=Decimal("100"),
        operational_weight=Decimal("90"),
        certified_volume=Decimal("10"),
        operational_volume=Decimal("9"),
        enforcement_mode="enforce",
    )
    assert requires_usage_validation(previous, proposed)


@pytest.mark.parametrize(
    ("before", "after", "requires_check"),
    [("100", "99", True), ("100", "100", False), ("100", "101", False)],
)
def test_limit_change_matrix(before: str, after: str, requires_check: bool) -> None:
    assert requires_usage_validation(config(before, "10"), config(after, "10")) is requires_check


def test_usage_is_occupied_plus_reserved_for_both_metrics() -> None:
    usage = CapacityUsageSnapshot(
        occupied_weight=Decimal("70"),
        reserved_weight=Decimal("21"),
        occupied_volume=Decimal("6"),
        reserved_volume=Decimal("3.5"),
    )
    violations = limits_below_usage(proposed=config("90", "9"), usage=usage)
    assert {(metric, kind) for metric, kind, _projected, _limit in violations} == {
        ("weight", "certified"),
        ("weight", "operational"),
        ("volume", "certified"),
        ("volume", "operational"),
    }
