"""Pure policies for hierarchical physical-capacity configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

CapacityMetricName = Literal["weight", "volume"]
CapacityLimitKind = Literal["certified", "operational"]
CapacityIssueSeverity = Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class CapacityConfiguration:
    certified_weight: Decimal | None = None
    operational_weight: Decimal | None = None
    certified_volume: Decimal | None = None
    operational_volume: Decimal | None = None
    enforcement_mode: str = "disabled"

    def value(self, metric: CapacityMetricName, kind: CapacityLimitKind) -> Decimal | None:
        return getattr(self, f"{kind}_{metric}")


@dataclass(frozen=True, slots=True)
class CapacityHierarchyIssue:
    severity: CapacityIssueSeverity
    code: str
    scope_type: str
    scope_id: str
    parent_scope_type: str | None
    parent_scope_id: str | None
    metric: CapacityMetricName
    limit_kind: CapacityLimitKind
    child_limit: Decimal | None = None
    parent_limit: Decimal | None = None
    allocated_children_total: Decimal | None = None
    allocation_ratio_pct: Decimal | None = None


@dataclass(frozen=True, slots=True)
class CapacityUsageSnapshot:
    occupied_weight: Decimal
    reserved_weight: Decimal
    occupied_volume: Decimal
    reserved_volume: Decimal
    incomplete_measurements: bool = False

    def projected(self, metric: CapacityMetricName) -> Decimal:
        return getattr(self, f"occupied_{metric}") + getattr(self, f"reserved_{metric}")


_LIMITS: tuple[tuple[CapacityMetricName, CapacityLimitKind], ...] = (
    ("weight", "certified"),
    ("weight", "operational"),
    ("volume", "certified"),
    ("volume", "operational"),
)


def decimal_or_none(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def capacity_configuration(
    source: object | Mapping[str, object],
) -> CapacityConfiguration:
    def read(name: str, default: object = None) -> object:
        if isinstance(source, Mapping):
            return source.get(name, default)
        return getattr(source, name, default)

    return CapacityConfiguration(
        certified_weight=decimal_or_none(read("certified_max_weight_kg")),
        operational_weight=decimal_or_none(read("operational_max_weight_kg")),
        certified_volume=decimal_or_none(read("certified_usable_volume_m3")),
        operational_volume=decimal_or_none(read("operational_usable_volume_m3")),
        enforcement_mode=str(read("capacity_enforcement_mode", "disabled")),
    )


def compare_child_to_parent(
    *,
    child: CapacityConfiguration,
    parent: CapacityConfiguration,
    scope_type: str,
    scope_id: str,
    parent_scope_type: str,
    parent_scope_id: str,
) -> tuple[CapacityHierarchyIssue, ...]:
    """Compare corresponding limits; nominal children are never summed here."""

    issues: list[CapacityHierarchyIssue] = []
    for metric, kind in _LIMITS:
        child_limit = child.value(metric, kind)
        if child_limit is None:
            continue
        parent_limit = parent.value(metric, kind)
        if parent_limit is None:
            issues.append(
                CapacityHierarchyIssue(
                    severity="warning",
                    code="parent_limit_not_configured",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    parent_scope_type=parent_scope_type,
                    parent_scope_id=parent_scope_id,
                    metric=metric,
                    limit_kind=kind,
                    child_limit=child_limit,
                )
            )
        elif child_limit > parent_limit:
            issues.append(
                CapacityHierarchyIssue(
                    severity="error",
                    code="capacity_child_limit_exceeds_parent",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    parent_scope_type=parent_scope_type,
                    parent_scope_id=parent_scope_id,
                    metric=metric,
                    limit_kind=kind,
                    child_limit=child_limit,
                    parent_limit=parent_limit,
                )
            )
    return tuple(issues)


def nominal_allocation_issues(
    *,
    parent: CapacityConfiguration,
    children: tuple[CapacityConfiguration, ...],
    scope_type: str,
    scope_id: str,
) -> tuple[CapacityHierarchyIssue, ...]:
    """Report oversubscription of direct nominal children without blocking it."""

    issues: list[CapacityHierarchyIssue] = []
    for metric, kind in _LIMITS:
        parent_limit = parent.value(metric, kind)
        if parent_limit is None:
            continue
        allocated = sum(
            (child.value(metric, kind) or Decimal("0") for child in children),
            Decimal("0"),
        )
        if allocated > parent_limit:
            issues.append(
                CapacityHierarchyIssue(
                    severity="warning",
                    code="nominal_capacity_overallocated",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    parent_scope_type=None,
                    parent_scope_id=None,
                    metric=metric,
                    limit_kind=kind,
                    parent_limit=parent_limit,
                    allocated_children_total=allocated,
                    allocation_ratio_pct=allocated / parent_limit * Decimal("100"),
                )
            )
    return tuple(issues)


def requires_usage_validation(
    previous: CapacityConfiguration | None,
    proposed: CapacityConfiguration,
) -> bool:
    if previous is None:
        return any(proposed.value(metric, kind) is not None for metric, kind in _LIMITS)
    if previous.enforcement_mode != "enforce" and proposed.enforcement_mode == "enforce":
        return True
    for metric, kind in _LIMITS:
        before = previous.value(metric, kind)
        after = proposed.value(metric, kind)
        if after is not None and (before is None or after < before):
            return True
    return False


def limits_below_usage(
    *,
    proposed: CapacityConfiguration,
    usage: CapacityUsageSnapshot,
) -> tuple[tuple[CapacityMetricName, CapacityLimitKind, Decimal, Decimal], ...]:
    violations: list[tuple[CapacityMetricName, CapacityLimitKind, Decimal, Decimal]] = []
    for metric, kind in _LIMITS:
        limit = proposed.value(metric, kind)
        projected = usage.projected(metric)
        if limit is not None and projected > limit:
            violations.append((metric, kind, projected, limit))
    return tuple(violations)
