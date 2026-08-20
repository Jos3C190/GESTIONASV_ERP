"""SQLAlchemy coordination for hierarchical capacity configuration policies."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.domain.entities.capacity_hierarchy import (
    CapacityConfiguration,
    CapacityHierarchyIssue,
    CapacityUsageSnapshot,
    capacity_configuration,
    compare_child_to_parent,
    limits_below_usage,
    nominal_allocation_issues,
    requires_usage_validation,
)
from app.infrastructure.models.inventory import (
    CapacityReservationModel,
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
)
from app.infrastructure.models.organization import (
    Branch,
    Location,
    Warehouse,
    WarehouseCapacityGroup,
)

ZERO = Decimal("0")
CAPACITY_FIELD_NAMES = frozenset(
    {
        "certified_max_weight_kg",
        "operational_max_weight_kg",
        "certified_usable_volume_m3",
        "operational_usable_volume_m3",
        "capacity_enforcement_mode",
        "capacity_group_id",
        "parent_id",
    }
)


def _merged_configuration(resource: object, values: Mapping[str, Any]) -> CapacityConfiguration:
    merged = {
        name: values.get(name, getattr(resource, name, None))
        for name in (
            "certified_max_weight_kg",
            "operational_max_weight_kg",
            "certified_usable_volume_m3",
            "operational_usable_volume_m3",
            "capacity_enforcement_mode",
        )
    }
    return capacity_configuration(merged)


def _configuration_changed(resource: object, values: Mapping[str, Any]) -> bool:
    return any(
        name in values and values[name] != getattr(resource, name, None)
        for name in CAPACITY_FIELD_NAMES
        if name not in {"capacity_group_id", "parent_id"}
    )


def _issue_dict(issue: CapacityHierarchyIssue) -> dict[str, Any]:
    return {
        "severity": issue.severity,
        "code": issue.code,
        "scope_type": issue.scope_type,
        "scope_id": issue.scope_id,
        "parent_scope_type": issue.parent_scope_type,
        "parent_scope_id": issue.parent_scope_id,
        "metric": issue.metric,
        "limit_kind": issue.limit_kind,
        "child_limit": issue.child_limit,
        "parent_limit": issue.parent_limit,
        "allocated_children_total": issue.allocated_children_total,
        "allocation_ratio_pct": issue.allocation_ratio_pct,
    }


class SqlAlchemyCapacityHierarchyRepository:
    """Authoritative cross-row validation, executed under the warehouse lock."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _warehouse(self, warehouse_id: uuid.UUID, *, lock: bool) -> Warehouse:
        statement = select(Warehouse).where(Warehouse.id == warehouse_id)
        if lock:
            statement = statement.with_for_update()
        warehouse = await self._session.scalar(statement)
        if warehouse is None:
            raise NotFoundError("Almacén no encontrado.", code="warehouse_not_found")
        return warehouse

    async def _company_id(self, warehouse_id: uuid.UUID) -> uuid.UUID:
        company_id = await self._session.scalar(
            select(Branch.company_id)
            .join(Warehouse, Warehouse.branch_id == Branch.id)
            .where(Warehouse.id == warehouse_id)
        )
        if company_id is None:
            raise NotFoundError("Almacén no encontrado.", code="warehouse_not_found")
        return company_id

    async def _groups(self, warehouse_id: uuid.UUID, *, lock: bool) -> list[WarehouseCapacityGroup]:
        statement = (
            select(WarehouseCapacityGroup)
            .where(
                WarehouseCapacityGroup.warehouse_id == warehouse_id,
                WarehouseCapacityGroup.deleted_at.is_(None),
            )
            .order_by(WarehouseCapacityGroup.id)
        )
        if lock:
            statement = statement.with_for_update()
        return list((await self._session.scalars(statement)).all())

    async def _locations(self, warehouse_id: uuid.UUID, *, lock: bool) -> list[Location]:
        statement = (
            select(Location)
            .where(Location.warehouse_id == warehouse_id, Location.deleted_at.is_(None))
            .order_by(Location.id)
        )
        if lock:
            statement = statement.with_for_update()
        return list((await self._session.scalars(statement)).all())

    @staticmethod
    def _descendant_group_ids(
        groups: Sequence[WarehouseCapacityGroup], group_id: uuid.UUID
    ) -> set[uuid.UUID]:
        children: dict[uuid.UUID | None, list[uuid.UUID]] = {}
        for group in groups:
            children.setdefault(group.parent_id, []).append(group.id)
        result: set[uuid.UUID] = set()
        pending = [group_id]
        while pending:
            current = pending.pop()
            if current in result:
                continue
            result.add(current)
            pending.extend(children.get(current, []))
        return result

    @staticmethod
    def _ancestor_groups(
        groups: Sequence[WarehouseCapacityGroup], group_id: uuid.UUID | None
    ) -> list[WarehouseCapacityGroup]:
        by_id = {group.id: group for group in groups}
        result: list[WarehouseCapacityGroup] = []
        seen: set[uuid.UUID] = set()
        current = group_id
        while current is not None:
            if current in seen or current not in by_id:
                break
            seen.add(current)
            group = by_id[current]
            result.append(group)
            current = group.parent_id
        return result

    async def _usage(
        self, warehouse_id: uuid.UUID, location_ids: Sequence[uuid.UUID] | None
    ) -> CapacityUsageSnapshot:
        company_id = await self._company_id(warehouse_id)
        balance_filters = [
            InventoryBalanceModel.company_id == company_id,
            InventoryBalanceModel.warehouse_id == warehouse_id,
        ]
        reservation_filters = [
            CapacityReservationModel.company_id == company_id,
            CapacityReservationModel.warehouse_id == warehouse_id,
            CapacityReservationModel.status.in_(("active", "confirmed")),
            CapacityReservationModel.expires_at > datetime.now(UTC),
        ]
        handling_unit_filters = [
            InventoryHandlingUnitModel.company_id == company_id,
            InventoryHandlingUnitModel.warehouse_id == warehouse_id,
            InventoryHandlingUnitModel.closed_at.is_(None),
            InventoryHandlingUnitModel.measurement_status == "incomplete",
        ]
        if location_ids is not None:
            ids = list(location_ids)
            if not ids:
                return CapacityUsageSnapshot(ZERO, ZERO, ZERO, ZERO, False)
            balance_filters.append(InventoryBalanceModel.location_id.in_(ids))
            reservation_filters.append(CapacityReservationModel.location_id.in_(ids))
            handling_unit_filters.append(InventoryHandlingUnitModel.location_id.in_(ids))
        occupied = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(InventoryBalanceModel.occupied_weight_kg), ZERO),
                    func.coalesce(func.sum(InventoryBalanceModel.occupied_volume_m3), ZERO),
                ).where(*balance_filters)
            )
        ).one()
        reserved = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(CapacityReservationModel.reserved_weight_kg), ZERO),
                    func.coalesce(func.sum(CapacityReservationModel.reserved_volume_m3), ZERO),
                    func.count(CapacityReservationModel.id).filter(
                        CapacityReservationModel.measurement_status == "incomplete"
                    ),
                ).where(*reservation_filters)
            )
        ).one()
        incomplete_hus = int(
            await self._session.scalar(
                select(func.count(InventoryHandlingUnitModel.id)).where(*handling_unit_filters)
            )
            or 0
        )
        return CapacityUsageSnapshot(
            occupied_weight=Decimal(occupied[0]),
            reserved_weight=Decimal(reserved[0]),
            occupied_volume=Decimal(occupied[1]),
            reserved_volume=Decimal(reserved[1]),
            incomplete_measurements=bool(incomplete_hus or reserved[2]),
        )

    @staticmethod
    def _raise_relation_error(issues: Sequence[CapacityHierarchyIssue]) -> None:
        error = next((issue for issue in issues if issue.severity == "error"), None)
        if error is None:
            return
        metric = "peso" if error.metric == "weight" else "volumen"
        kind = "certificado" if error.limit_kind == "certified" else "operativo"
        raise ConflictError(
            f"El límite {kind} de {metric} del elemento hijo supera el límite de su contenedor.",
            code="capacity_child_limit_exceeds_parent",
        )

    async def _validate_reduction(
        self,
        *,
        previous: CapacityConfiguration,
        proposed: CapacityConfiguration,
        warehouse_id: uuid.UUID,
        location_ids: Sequence[uuid.UUID] | None,
    ) -> None:
        if not requires_usage_validation(previous, proposed):
            return
        usage = await self._usage(warehouse_id, location_ids)
        if usage.incomplete_measurements:
            raise ConflictError(
                "No se puede restringir la capacidad mientras existan existencias o reservas sin medición completa.",
                code="capacity_usage_incomplete",
            )
        if limits_below_usage(proposed=proposed, usage=usage):
            raise ConflictError(
                "El nuevo límite es menor que la ocupación más las reservas vigentes.",
                code="capacity_limit_below_projected_usage",
            )

    @staticmethod
    def _usage_exceeds_scope(
        usage: CapacityUsageSnapshot, configuration: CapacityConfiguration
    ) -> bool:
        for metric in ("weight", "volume"):
            projected = usage.projected(metric)
            certified = configuration.value(metric, "certified")
            operational = configuration.value(metric, "operational")
            if certified is not None and projected > certified:
                return True
            if (
                configuration.enforcement_mode == "enforce"
                and operational is not None
                and projected > operational
            ):
                return True
        return False

    @staticmethod
    def _has_configured_limit(configuration: CapacityConfiguration) -> bool:
        return any(
            configuration.value(metric, kind) is not None
            for metric in ("weight", "volume")
            for kind in ("certified", "operational")
        )

    @classmethod
    def _validate_moving_usage(
        cls,
        usage: CapacityUsageSnapshot,
        configuration: CapacityConfiguration,
        *,
        exceeds_message: str,
    ) -> None:
        if usage.incomplete_measurements and cls._has_configured_limit(configuration):
            raise ConflictError(
                "No se puede cambiar la jerarquía mientras el consumo trasladado tenga mediciones incompletas.",
                code="capacity_usage_incomplete",
            )
        if cls._usage_exceeds_scope(usage, configuration):
            raise ConflictError(
                exceeds_message,
                code="capacity_group_reparent_exceeds_target",
            )

    async def validate_warehouse_update(
        self, warehouse_id: uuid.UUID, values: Mapping[str, Any]
    ) -> None:
        warehouse = await self._warehouse(warehouse_id, lock=True)
        if not _configuration_changed(warehouse, values):
            return
        previous = capacity_configuration(warehouse)
        proposed = _merged_configuration(warehouse, values)
        groups = await self._groups(warehouse_id, lock=True)
        locations = await self._locations(warehouse_id, lock=True)
        direct_children: list[tuple[str, str, CapacityConfiguration]] = [
            ("capacity_group", str(group.id), capacity_configuration(group))
            for group in groups
            if group.parent_id is None and group.is_active and group.storage_eligible
        ]
        direct_children.extend(
            ("location", str(location.id), capacity_configuration(location))
            for location in locations
            if location.capacity_group_id is None
            and location.is_active
            and location.storage_eligible
        )
        for scope_type, scope_id, child in direct_children:
            self._raise_relation_error(
                compare_child_to_parent(
                    child=child,
                    parent=proposed,
                    scope_type=scope_type,
                    scope_id=scope_id,
                    parent_scope_type="warehouse",
                    parent_scope_id=str(warehouse.id),
                )
            )
        await self._validate_reduction(
            previous=previous,
            proposed=proposed,
            warehouse_id=warehouse_id,
            location_ids=None,
        )

    async def validate_location_write(
        self,
        warehouse_id: uuid.UUID,
        values: Mapping[str, Any],
        *,
        location_id: uuid.UUID | None = None,
    ) -> None:
        warehouse = await self._warehouse(warehouse_id, lock=True)
        groups = await self._groups(warehouse_id, lock=True)
        current = None
        if location_id is not None:
            current = await self._session.scalar(
                select(Location)
                .where(
                    Location.id == location_id,
                    Location.warehouse_id == warehouse_id,
                    Location.deleted_at.is_(None),
                )
                .with_for_update()
            )
            if current is None:
                raise NotFoundError("Ubicación no encontrada.", code="location_not_found")
        proposed = _merged_configuration(current, values)
        target_group_id = values.get(
            "capacity_group_id", getattr(current, "capacity_group_id", None)
        )
        if (
            current is not None
            and capacity_configuration(current) == proposed
            and target_group_id == current.capacity_group_id
        ):
            return
        target_group = next((group for group in groups if group.id == target_group_id), None)
        target_ancestors = self._ancestor_groups(groups, target_group_id)
        if target_group_id is not None and (
            target_group is None
            or any(not ancestor.is_active for ancestor in target_ancestors)
            or (target_ancestors and target_ancestors[-1].parent_id is not None)
            or target_group.deleted_at is not None
        ):
            raise ConflictError(
                "La estructura seleccionada no está disponible en el almacén.",
                code="location_capacity_group_unavailable",
            )
        parent = target_group or warehouse
        self._raise_relation_error(
            compare_child_to_parent(
                child=proposed,
                parent=capacity_configuration(parent),
                scope_type="location",
                scope_id=str(location_id or "new"),
                parent_scope_type="capacity_group" if target_group else "warehouse",
                parent_scope_id=str(parent.id),
            )
        )
        if current is None:
            return
        previous = capacity_configuration(current)
        await self._validate_reduction(
            previous=previous,
            proposed=proposed,
            warehouse_id=warehouse_id,
            location_ids=[current.id],
        )
        if target_group_id == current.capacity_group_id:
            return
        moving_usage = await self._usage(warehouse_id, [current.id])
        old_ancestors = {
            group.id for group in self._ancestor_groups(groups, current.capacity_group_id)
        }
        for ancestor in self._ancestor_groups(groups, target_group_id):
            ancestor_ids = self._descendant_group_ids(groups, ancestor.id)
            member_location_ids = [
                location.id
                for location in await self._locations(warehouse_id, lock=True)
                if location.capacity_group_id in ancestor_ids and location.id != current.id
            ]
            target_usage = await self._usage(warehouse_id, member_location_ids)
            combined = CapacityUsageSnapshot(
                occupied_weight=target_usage.occupied_weight + moving_usage.occupied_weight,
                reserved_weight=target_usage.reserved_weight + moving_usage.reserved_weight,
                occupied_volume=target_usage.occupied_volume + moving_usage.occupied_volume,
                reserved_volume=target_usage.reserved_volume + moving_usage.reserved_volume,
                incomplete_measurements=(
                    target_usage.incomplete_measurements or moving_usage.incomplete_measurements
                ),
            )
            if ancestor.id not in old_ancestors:
                self._validate_moving_usage(
                    combined,
                    capacity_configuration(ancestor),
                    exceeds_message=(
                        "La ocupación de la ubicación excedería la capacidad de la estructura destino."
                    ),
                )

    async def validate_group_write(  # noqa: C901 - one transactional hierarchy decision
        self,
        warehouse_id: uuid.UUID,
        values: Mapping[str, Any],
        *,
        group_id: uuid.UUID | None = None,
    ) -> None:
        warehouse = await self._warehouse(warehouse_id, lock=True)
        groups = await self._groups(warehouse_id, lock=True)
        locations = await self._locations(warehouse_id, lock=True)
        current = next((group for group in groups if group.id == group_id), None)
        if group_id is not None and current is None:
            raise NotFoundError(
                "Grupo de capacidad no encontrado.", code="capacity_group_not_found"
            )
        proposed = _merged_configuration(current, values)
        target_parent_id = values.get("parent_id", getattr(current, "parent_id", None))
        target_active = bool(values.get("is_active", getattr(current, "is_active", True)))
        if (
            current is not None
            and capacity_configuration(current) == proposed
            and target_parent_id == current.parent_id
            and target_active == current.is_active
        ):
            return
        if current is not None and current.is_active and not target_active:
            has_active_child = any(
                group.parent_id == current.id and group.is_active for group in groups
            )
            has_active_location = any(
                location.capacity_group_id == current.id
                and location.is_active
                and location.deleted_at is None
                for location in locations
            )
            if has_active_child or has_active_location:
                raise ConflictError(
                    "La estructura mantiene subestructuras o ubicaciones activas asignadas.",
                    code="capacity_group_has_active_assignments",
                )
        parent = next((group for group in groups if group.id == target_parent_id), None)
        parent_ancestors = self._ancestor_groups(groups, target_parent_id)
        invalid_parent = bool(
            target_parent_id is not None
            and (
                parent is None
                or any(not ancestor.is_active for ancestor in parent_ancestors)
                or (parent_ancestors and parent_ancestors[-1].parent_id is not None)
                or (
                    current is not None
                    and target_parent_id in self._descendant_group_ids(groups, current.id)
                )
            )
        )
        if invalid_parent:
            raise ConflictError(
                "La estructura superior no está disponible.",
                code="capacity_group_parent_unavailable",
            )
        parent_resource = parent or warehouse
        self._raise_relation_error(
            compare_child_to_parent(
                child=proposed,
                parent=capacity_configuration(parent_resource),
                scope_type="capacity_group",
                scope_id=str(group_id or "new"),
                parent_scope_type="capacity_group" if parent else "warehouse",
                parent_scope_id=str(parent_resource.id),
            )
        )
        if current is None:
            return
        for child_group in groups:
            if child_group.parent_id == current.id and child_group.id != current.id:
                self._raise_relation_error(
                    compare_child_to_parent(
                        child=capacity_configuration(child_group),
                        parent=proposed,
                        scope_type="capacity_group",
                        scope_id=str(child_group.id),
                        parent_scope_type="capacity_group",
                        parent_scope_id=str(current.id),
                    )
                )
        for location in locations:
            if location.capacity_group_id == current.id and location.storage_eligible:
                self._raise_relation_error(
                    compare_child_to_parent(
                        child=capacity_configuration(location),
                        parent=proposed,
                        scope_type="location",
                        scope_id=str(location.id),
                        parent_scope_type="capacity_group",
                        parent_scope_id=str(current.id),
                    )
                )
        descendant_ids = self._descendant_group_ids(groups, current.id)
        subtree_location_ids = [
            location.id for location in locations if location.capacity_group_id in descendant_ids
        ]
        await self._validate_reduction(
            previous=capacity_configuration(current),
            proposed=proposed,
            warehouse_id=warehouse_id,
            location_ids=subtree_location_ids,
        )
        if target_parent_id == current.parent_id:
            return
        moving_usage = await self._usage(warehouse_id, subtree_location_ids)
        old_ancestors = {group.id for group in self._ancestor_groups(groups, current.parent_id)}
        for ancestor in self._ancestor_groups(groups, target_parent_id):
            if ancestor.id in old_ancestors:
                continue
            target_descendants = self._descendant_group_ids(groups, ancestor.id) - descendant_ids
            target_location_ids = [
                location.id
                for location in locations
                if location.capacity_group_id in target_descendants
            ]
            target_usage = await self._usage(warehouse_id, target_location_ids)
            combined = CapacityUsageSnapshot(
                target_usage.occupied_weight + moving_usage.occupied_weight,
                target_usage.reserved_weight + moving_usage.reserved_weight,
                target_usage.occupied_volume + moving_usage.occupied_volume,
                target_usage.reserved_volume + moving_usage.reserved_volume,
                target_usage.incomplete_measurements or moving_usage.incomplete_measurements,
            )
            self._validate_moving_usage(
                combined,
                capacity_configuration(ancestor),
                exceeds_message=(
                    "La ocupación de la estructura excedería la capacidad de su nuevo contenedor."
                ),
            )

    async def diagnostics(self, warehouse_id: uuid.UUID) -> dict[str, Any]:
        warehouse = await self._warehouse(warehouse_id, lock=False)
        groups = [
            group for group in await self._groups(warehouse_id, lock=False) if group.is_active
        ]
        locations = [
            location
            for location in await self._locations(warehouse_id, lock=False)
            if location.is_active and location.storage_eligible
        ]
        by_id = {group.id: group for group in groups}
        issues: list[CapacityHierarchyIssue] = []
        for group in groups:
            parent = by_id.get(group.parent_id) if group.parent_id else warehouse
            if parent is None:
                continue
            issues.extend(
                compare_child_to_parent(
                    child=capacity_configuration(group),
                    parent=capacity_configuration(parent),
                    scope_type="capacity_group",
                    scope_id=str(group.id),
                    parent_scope_type="capacity_group" if group.parent_id else "warehouse",
                    parent_scope_id=str(parent.id),
                )
            )
        for location in locations:
            parent = (
                by_id.get(location.capacity_group_id) if location.capacity_group_id else warehouse
            )
            if parent is None:
                continue
            issues.extend(
                compare_child_to_parent(
                    child=capacity_configuration(location),
                    parent=capacity_configuration(parent),
                    scope_type="location",
                    scope_id=str(location.id),
                    parent_scope_type=(
                        "capacity_group" if location.capacity_group_id else "warehouse"
                    ),
                    parent_scope_id=str(parent.id),
                )
            )
        parent_resources: list[tuple[str, object, list[object]]] = [
            (
                "warehouse",
                warehouse,
                [group for group in groups if group.parent_id is None]
                + [location for location in locations if location.capacity_group_id is None],
            )
        ]
        parent_resources.extend(
            (
                "capacity_group",
                group,
                [child for child in groups if child.parent_id == group.id]
                + [location for location in locations if location.capacity_group_id == group.id],
            )
            for group in groups
        )
        for scope_type, parent, children in parent_resources:
            issues.extend(
                nominal_allocation_issues(
                    parent=capacity_configuration(parent),
                    children=tuple(capacity_configuration(child) for child in children),
                    scope_type=scope_type,
                    scope_id=str(parent.id),
                )
            )
        return {
            "warehouse_id": warehouse.id,
            "issues": [_issue_dict(issue) for issue in issues],
        }
