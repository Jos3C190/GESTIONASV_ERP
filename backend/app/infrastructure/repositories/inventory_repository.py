"""Transactional PostgreSQL implementation of the inventory repository port."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.inventory import (
    ZERO,
    CapacityDecision,
    CapacityLimit,
    CapacityReservation,
    CapacityUsage,
    Consumption,
    InventoryItem,
    InventoryOperationError,
    MeasurementSource,
    MeasurementStatus,
    PackagingDefinition,
    PackagingType,
    PhysicalMeasures,
    ReservationStatus,
    StockStatus,
    calculate_consumption,
    calculate_measured_consumption,
    evaluate_capacity,
    require_quarantine_for_incomplete_measures,
)
from app.domain.entities.warehouse_capacity import capacity_status_for
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
from app.infrastructure.models.inventory import (
    CapacityOperationalOverrideModel,
    CapacityReservationModel,
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryItemModel,
    InventoryMovementLineModel,
    InventoryMovementModel,
    InventoryPackagingModel,
)
from app.infrastructure.models.organization import (
    Branch,
    Location,
    Warehouse,
    WarehouseCapacityGroup,
)
from app.infrastructure.models.product_variant import ProductVariantModel


def _decimal(value: Decimal | int | float | None) -> Decimal | None:
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _stock_status_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, StockStatus):
        return value.value
    if isinstance(value, str):
        return StockStatus(value).value
    raise InventoryOperationError(
        "El estado de inventario no es válido.", code="invalid_stock_status"
    )


def _capacity_metric_payload(
    *,
    certified: Decimal | None,
    operational: Decimal | None,
    occupied: Decimal,
    reserved: Decimal,
    projected: Decimal,
    utilization_pct: Decimal | None,
    occupied_known: bool,
    reserved_known: bool,
) -> dict[str, Decimal | None]:
    """Serialize one independent metric without inventing values for unknown stock."""
    total_known = occupied_known and reserved_known
    return {
        "certified": certified,
        "operational": operational,
        "occupied": occupied if occupied_known else None,
        "reserved": reserved if reserved_known else None,
        "projected": projected if total_known else None,
        "available": (operational - projected if operational is not None and total_known else None),
        "utilization_pct": utilization_pct if total_known else None,
    }


def _capacity_summary_status(
    *,
    measurements_complete: bool,
    configuration_status: str,
    effective_utilization_pct: Decimal | None,
    active_override: bool,
    certified_exceeded: bool = False,
) -> str:
    if certified_exceeded:
        # A known breach of a certified ceiling is a safety alarm. It must never
        # be softened into an operational override or a generic full state.
        status = "over_certified"
    elif not measurements_complete or configuration_status == "incomplete":
        status = "incomplete"
    elif configuration_status == "not_configured" or effective_utilization_pct is None:
        status = "not_configured"
    elif effective_utilization_pct > Decimal("100") and active_override:
        status = "over_operational"
    elif effective_utilization_pct >= Decimal("100"):
        status = "full"
    elif effective_utilization_pct >= Decimal("90"):
        status = "critical"
    elif effective_utilization_pct >= Decimal("80"):
        status = "warning"
    else:
        status = "available"
    return status


def _advisory_lock_key(*parts: object) -> int:
    digest = hashlib.sha256(":".join(str(part) for part in parts).encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


def _item_domain(row: InventoryItemModel) -> InventoryItem:
    return InventoryItem(
        id=row.id,
        company_id=row.company_id,
        product_id=row.product_id,
        variant_id=row.variant_id,
        base_unit_id=row.base_unit_id,
        is_active=row.is_active,
    )


def _packaging_domain(row: InventoryPackagingModel) -> PackagingDefinition:
    return PackagingDefinition(
        id=row.id,
        company_id=row.company_id,
        inventory_item_id=row.inventory_item_id,
        code=row.code,
        name=row.name,
        packaging_type=PackagingType(row.packaging_type),
        version=row.version,
        base_quantity=row.base_quantity,
        measures=PhysicalMeasures(
            gross_weight_kg=row.gross_weight_kg,
            length_m=row.length_m,
            width_m=row.width_m,
            height_m=row.height_m,
            volume_m3=row.volume_m3,
        ),
        stackable=row.stackable,
        max_stack=row.max_stack,
        is_current=row.is_current,
        is_active=row.is_active,
        created_at=row.created_at,
    )


def _reservation_domain(row: CapacityReservationModel) -> CapacityReservation:
    measurements_complete = row.measurement_status != MeasurementStatus.INCOMPLETE.value
    return CapacityReservation(
        id=row.id,
        company_id=row.company_id,
        warehouse_id=row.warehouse_id,
        location_id=row.location_id,
        inventory_item_id=row.inventory_item_id,
        quantity_base=row.quantity_base,
        weight_kg=row.reserved_weight_kg if measurements_complete else None,
        volume_m3=row.reserved_volume_m3 if measurements_complete else None,
        measurement_status=MeasurementStatus(row.measurement_status),
        status=ReservationStatus(row.status),
        expires_at=row.expires_at,
        operational_override_id=row.operational_override_id,
        created_at=row.created_at,
    )


@dataclass(slots=True)
class _ResolvedPhysical:
    packaging: InventoryPackagingModel | None
    measures: PhysicalMeasures
    consumption: Consumption | None
    snapshot: dict[str, Any] | None
    source: MeasurementSource


@dataclass(slots=True)
class _LocationContext:
    location: Location
    warehouse: Warehouse
    groups: list[WarehouseCapacityGroup]
    company_id: uuid.UUID


def _physical_from_handling_unit(
    row: InventoryHandlingUnitModel,
) -> _ResolvedPhysical:
    """Rehydrate physical truth without turning an unknown measure into zero."""

    snapshot = row.packaging_snapshot or {}
    try:
        source = MeasurementSource(row.measurement_source)
        measurement_status = MeasurementStatus(row.measurement_status)
    except ValueError as exc:
        raise InventoryOperationError(
            "La unidad logística contiene un estado de medición inconsistente.",
            code="handling_unit_measurements_inconsistent",
            status_code=409,
        ) from exc

    def snapshot_decimal(name: str) -> Decimal | None:
        value = snapshot.get(name)
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, ArithmeticError) as exc:
            raise InventoryOperationError(
                "El snapshot físico de la unidad logística no es válido.",
                code="invalid_packaging_snapshot",
                status_code=409,
            ) from exc

    measures = PhysicalMeasures(
        gross_weight_kg=(
            row.actual_gross_weight_kg
            if row.actual_gross_weight_kg is not None
            else (
                None
                if measurement_status is MeasurementStatus.INCOMPLETE
                else row.occupied_weight_kg
            )
        ),
        length_m=(
            row.actual_length_m if row.actual_length_m is not None else snapshot_decimal("length_m")
        ),
        width_m=(
            row.actual_width_m if row.actual_width_m is not None else snapshot_decimal("width_m")
        ),
        height_m=(
            row.actual_height_m if row.actual_height_m is not None else snapshot_decimal("height_m")
        ),
        volume_m3=(
            row.actual_volume_m3
            if row.actual_volume_m3 is not None
            else (
                None
                if measurement_status is MeasurementStatus.INCOMPLETE
                else row.occupied_volume_m3
            )
        ),
    )
    try:
        measures.validate()
    except ValueError as exc:
        raise InventoryOperationError(
            "La unidad logística contiene medidas inconsistentes.",
            code="handling_unit_measurements_inconsistent",
            status_code=409,
        ) from exc

    consumption: Consumption | None = None
    if measurement_status is not MeasurementStatus.INCOMPLETE:
        if not measures.is_complete:
            raise InventoryOperationError(
                "La unidad logística marcada como medida no tiene datos completos.",
                code="handling_unit_measurements_inconsistent",
                status_code=409,
            )
        consumption = Consumption(
            weight_kg=row.occupied_weight_kg,
            volume_m3=row.occupied_volume_m3,
        )
    return _ResolvedPhysical(
        packaging=None,
        measures=measures,
        consumption=consumption,
        snapshot=row.packaging_snapshot,
        source=source,
    )


class SqlAlchemyInventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_item(
        self,
        *,
        company_id: uuid.UUID,
        product_id: int | None,
        variant_id: uuid.UUID | None,
        base_unit_id: int,
    ) -> InventoryItem:
        company_unit = await self._session.scalar(
            select(CompanyUnitModel).where(
                CompanyUnitModel.company_id == company_id,
                CompanyUnitModel.unit_id == base_unit_id,
                CompanyUnitModel.is_enabled.is_(True),
            )
        )
        if company_unit is None:
            raise InventoryOperationError(
                "La unidad base no está habilitada para la empresa.",
                code="base_unit_not_enabled",
            )

        if product_id is not None:
            product = await self._session.scalar(
                select(ProductModel).where(
                    ProductModel.company_id == company_id,
                    ProductModel.id_product == product_id,
                )
            )
            if product is None:
                raise InventoryOperationError(
                    "Producto no encontrado.", code="product_not_found", status_code=404
                )
            if product.product_kind != "goods" or product.variant_mode != "standalone":
                raise InventoryOperationError(
                    "Solo un producto físico independiente puede tener inventario directo.",
                    code="product_not_inventory_eligible",
                )
        else:
            variant = await self._session.scalar(
                select(ProductVariantModel)
                .join(
                    ProductModel,
                    and_(
                        ProductModel.company_id == ProductVariantModel.company_id,
                        ProductModel.id_product == ProductVariantModel.product_id,
                    ),
                )
                .where(
                    ProductVariantModel.company_id == company_id,
                    ProductVariantModel.id == variant_id,
                    ProductModel.product_kind == "goods",
                    ProductModel.variant_mode == "template",
                )
            )
            if variant is None:
                raise InventoryOperationError(
                    "Variante inventariable no encontrada.",
                    code="variant_not_inventory_eligible",
                    status_code=404,
                )

        target_filter = (
            InventoryItemModel.product_id == product_id
            if product_id is not None
            else InventoryItemModel.variant_id == variant_id
        )
        existing = await self._session.scalar(
            select(InventoryItemModel).where(
                InventoryItemModel.company_id == company_id, target_filter
            )
        )
        if existing is not None:
            raise InventoryOperationError(
                "El producto o variante ya tiene identidad inventariable.",
                code="inventory_item_exists",
                status_code=409,
            )
        row = InventoryItemModel(
            company_id=company_id,
            product_id=product_id,
            variant_id=variant_id,
            base_unit_id=base_unit_id,
        )
        self._session.add(row)
        await self._session.flush()
        return _item_domain(row)

    async def get_item(self, company_id: uuid.UUID, item_id: uuid.UUID) -> InventoryItem | None:
        row = await self._session.scalar(
            select(InventoryItemModel).where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.id == item_id,
            )
        )
        return _item_domain(row) if row else None

    async def get_item_by_target(
        self,
        *,
        company_id: uuid.UUID,
        product_id: int | None,
        variant_id: uuid.UUID | None,
    ) -> InventoryItem | None:
        target_filter = (
            InventoryItemModel.product_id == product_id
            if product_id is not None
            else InventoryItemModel.variant_id == variant_id
        )
        row = await self._session.scalar(
            select(InventoryItemModel).where(
                InventoryItemModel.company_id == company_id,
                target_filter,
            )
        )
        return _item_domain(row) if row else None

    async def list_packaging(
        self, company_id: uuid.UUID, item_id: uuid.UUID
    ) -> list[PackagingDefinition]:
        rows = (
            await self._session.scalars(
                select(InventoryPackagingModel)
                .where(
                    InventoryPackagingModel.company_id == company_id,
                    InventoryPackagingModel.inventory_item_id == item_id,
                )
                .order_by(
                    InventoryPackagingModel.code,
                    InventoryPackagingModel.version.desc(),
                )
            )
        ).all()
        return [_packaging_domain(row) for row in rows]

    async def create_packaging(
        self,
        *,
        company_id: uuid.UUID,
        item_id: uuid.UUID,
        code: str,
        name: str,
        packaging_type: PackagingType,
        base_quantity: Decimal,
        measures: PhysicalMeasures,
        stackable: bool,
        max_stack: int | None,
        supersedes_id: uuid.UUID | None = None,
    ) -> PackagingDefinition:
        item = await self._session.scalar(
            select(InventoryItemModel)
            .where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.id == item_id,
                InventoryItemModel.is_active.is_(True),
            )
            .with_for_update()
        )
        if item is None:
            raise InventoryOperationError(
                "Identidad inventariable no encontrada.",
                code="inventory_item_not_found",
                status_code=404,
            )

        version = 1
        old: InventoryPackagingModel | None = None
        if supersedes_id is not None:
            old = await self._session.scalar(
                select(InventoryPackagingModel)
                .where(
                    InventoryPackagingModel.company_id == company_id,
                    InventoryPackagingModel.inventory_item_id == item_id,
                    InventoryPackagingModel.id == supersedes_id,
                    InventoryPackagingModel.is_current.is_(True),
                    InventoryPackagingModel.is_active.is_(True),
                )
                .with_for_update()
            )
            if old is None:
                raise InventoryOperationError(
                    "La versión a sustituir no está vigente.",
                    code="packaging_version_not_current",
                    status_code=409,
                )
            if old.code != code:
                raise InventoryOperationError(
                    "El código de una presentación versionada no puede cambiar.",
                    code="packaging_code_immutable",
                )
            version = old.version + 1
            old.is_current = False
        elif await self._session.scalar(
            select(InventoryPackagingModel.id).where(
                InventoryPackagingModel.company_id == company_id,
                InventoryPackagingModel.inventory_item_id == item_id,
                InventoryPackagingModel.code == code,
                InventoryPackagingModel.is_current.is_(True),
                InventoryPackagingModel.is_active.is_(True),
            )
        ):
            raise InventoryOperationError(
                "Ya existe una presentación vigente con ese código.",
                code="packaging_code_exists",
                status_code=409,
            )

        row = InventoryPackagingModel(
            company_id=company_id,
            inventory_item_id=item_id,
            code=code,
            name=name,
            packaging_type=packaging_type.value,
            version=version,
            base_quantity=base_quantity,
            gross_weight_kg=measures.gross_weight_kg,
            length_m=measures.length_m,
            width_m=measures.width_m,
            height_m=measures.height_m,
            volume_m3=measures.derived_volume_m3,
            stackable=stackable,
            max_stack=max_stack,
            supersedes_id=old.id if old else None,
            is_current=True,
            is_active=True,
        )
        self._session.add(row)
        await self._session.flush()
        return _packaging_domain(row)

    async def deactivate_packaging(
        self, company_id: uuid.UUID, item_id: uuid.UUID, packaging_id: uuid.UUID
    ) -> None:
        row = await self._session.scalar(
            select(InventoryPackagingModel)
            .where(
                InventoryPackagingModel.company_id == company_id,
                InventoryPackagingModel.inventory_item_id == item_id,
                InventoryPackagingModel.id == packaging_id,
                InventoryPackagingModel.is_active.is_(True),
            )
            .with_for_update()
        )
        if row is None:
            raise InventoryOperationError(
                "Presentación no encontrada.", code="packaging_not_found", status_code=404
            )
        row.is_active = False
        row.is_current = False
        await self._session.flush()

    async def _location_context(
        self,
        company_id: uuid.UUID,
        location_id: uuid.UUID,
        *,
        lock: bool,
    ) -> _LocationContext:
        discovered = (
            await self._session.execute(
                select(Location, Warehouse, Branch.company_id)
                .join(Warehouse, Warehouse.id == Location.warehouse_id)
                .join(Branch, Branch.id == Warehouse.branch_id)
                .where(Location.id == location_id, Branch.company_id == company_id)
            )
        ).one_or_none()
        if discovered is None:
            raise InventoryOperationError(
                "Ubicación no encontrada.", code="location_not_found", status_code=404
            )
        location, warehouse, persisted_company = discovered
        if lock:
            warehouse = await self._session.scalar(
                select(Warehouse).where(Warehouse.id == warehouse.id).with_for_update()
            )
            assert warehouse is not None

        all_groups = list(
            (
                await self._session.scalars(
                    select(WarehouseCapacityGroup).where(
                        WarehouseCapacityGroup.warehouse_id == warehouse.id,
                        WarehouseCapacityGroup.is_active.is_(True),
                        WarehouseCapacityGroup.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        by_id = {group.id: group for group in all_groups}
        group_path: list[WarehouseCapacityGroup] = []
        cursor = location.capacity_group_id
        seen: set[uuid.UUID] = set()
        while cursor is not None:
            if cursor in seen:
                raise InventoryOperationError(
                    "La jerarquía de capacidad contiene un ciclo.",
                    code="capacity_group_cycle",
                    status_code=409,
                )
            seen.add(cursor)
            group = by_id.get(cursor)
            if group is None:
                raise InventoryOperationError(
                    "El grupo estructural de la ubicación no está disponible.",
                    code="capacity_group_unavailable",
                    status_code=409,
                )
            group_path.append(group)
            cursor = group.parent_id
        if lock and group_path:
            locked = list(
                (
                    await self._session.scalars(
                        select(WarehouseCapacityGroup)
                        .where(
                            WarehouseCapacityGroup.id.in_(sorted(seen, key=str)),
                            WarehouseCapacityGroup.warehouse_id == warehouse.id,
                            WarehouseCapacityGroup.is_active.is_(True),
                            WarehouseCapacityGroup.deleted_at.is_(None),
                        )
                        .order_by(WarehouseCapacityGroup.id)
                        .with_for_update()
                    )
                ).all()
            )
            locked_by_id = {group.id: group for group in locked}
            group_path = [locked_by_id[group.id] for group in group_path]
        if lock:
            location = await self._session.scalar(
                select(Location).where(Location.id == location.id).with_for_update()
            )
            assert location is not None
        return _LocationContext(location, warehouse, group_path, persisted_company)

    async def _resolve_physical(
        self,
        *,
        company_id: uuid.UUID,
        item_id: uuid.UUID,
        packaging_id: uuid.UUID | None,
        quantity_base: Decimal,
        actual_measures: PhysicalMeasures | None,
    ) -> _ResolvedPhysical:
        item = await self._session.scalar(
            select(InventoryItemModel).where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.id == item_id,
                InventoryItemModel.is_active.is_(True),
            )
        )
        if item is None:
            raise InventoryOperationError(
                "Identidad inventariable no encontrada.",
                code="inventory_item_not_found",
                status_code=404,
            )
        packaging: InventoryPackagingModel | None = None
        base_quantity = Decimal("1")
        master = PhysicalMeasures(None, None, None, None, None)
        snapshot: dict[str, Any] | None = None
        if packaging_id is not None:
            packaging = await self._session.scalar(
                select(InventoryPackagingModel).where(
                    InventoryPackagingModel.company_id == company_id,
                    InventoryPackagingModel.inventory_item_id == item_id,
                    InventoryPackagingModel.id == packaging_id,
                    InventoryPackagingModel.is_current.is_(True),
                    InventoryPackagingModel.is_active.is_(True),
                )
            )
            if packaging is None:
                raise InventoryOperationError(
                    "Presentación vigente no encontrada.",
                    code="packaging_not_found",
                    status_code=404,
                )
            base_quantity = packaging.base_quantity
            master = PhysicalMeasures(
                packaging.gross_weight_kg,
                packaging.length_m,
                packaging.width_m,
                packaging.height_m,
                packaging.volume_m3,
            )
            snapshot = {
                "id": str(packaging.id),
                "code": packaging.code,
                "version": packaging.version,
                "packaging_type": packaging.packaging_type,
                "base_quantity": str(packaging.base_quantity),
                "gross_weight_kg": (
                    str(packaging.gross_weight_kg)
                    if packaging.gross_weight_kg is not None
                    else None
                ),
                "length_m": str(packaging.length_m) if packaging.length_m is not None else None,
                "width_m": str(packaging.width_m) if packaging.width_m is not None else None,
                "height_m": str(packaging.height_m) if packaging.height_m is not None else None,
                "volume_m3": str(packaging.volume_m3) if packaging.volume_m3 is not None else None,
            }

        source = MeasurementSource.MASTER
        measures = master
        consumption = calculate_consumption(
            quantity_base=quantity_base,
            base_quantity=base_quantity,
            measures=measures,
        )
        actual_values = (
            (
                actual_measures.gross_weight_kg,
                actual_measures.length_m,
                actual_measures.width_m,
                actual_measures.height_m,
                actual_measures.volume_m3,
            )
            if actual_measures is not None
            else ()
        )
        if actual_measures is not None and any(value is not None for value in actual_values):
            actual_measures.validate()
            measures = actual_measures
            consumption = calculate_measured_consumption(measures)
            source = MeasurementSource.RECEIPT
        measures.validate()
        return _ResolvedPhysical(packaging, measures, consumption, snapshot, source)

    async def _usage(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_ids: list[uuid.UUID] | None,
        exclude_reservation_id: uuid.UUID | None,
    ) -> CapacityUsage:
        expired_reservation_ids = list(
            (
                await self._session.scalars(
                    update(CapacityReservationModel)
                    .where(
                        CapacityReservationModel.company_id == company_id,
                        CapacityReservationModel.warehouse_id == warehouse_id,
                        CapacityReservationModel.status.in_(("active", "confirmed")),
                        CapacityReservationModel.expires_at <= datetime.now(UTC),
                    )
                    .values(status="expired")
                    .returning(CapacityReservationModel.id)
                )
            ).all()
        )
        if expired_reservation_ids:
            self._session.add_all(
                [
                    AuditLog(
                        action="EXPIRE",
                        user_id=None,
                        company_id=company_id,
                        resource_type="inventory_capacity_reservations",
                        resource_id=str(reservation_id),
                        before_state={"status": "active_or_confirmed"},
                        after_state={"status": "expired"},
                        metadata_={
                            "reason": "ttl_elapsed",
                            "warehouse_id": str(warehouse_id),
                        },
                    )
                    for reservation_id in expired_reservation_ids
                ]
            )
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
        if location_ids is not None:
            balance_filters.append(InventoryBalanceModel.location_id.in_(location_ids))
            reservation_filters.append(CapacityReservationModel.location_id.in_(location_ids))
        if exclude_reservation_id is not None:
            reservation_filters.append(CapacityReservationModel.id != exclude_reservation_id)
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
                ).where(*reservation_filters)
            )
        ).one()
        return CapacityUsage(
            occupied_weight_kg=_decimal(occupied[0]) or ZERO,
            occupied_volume_m3=_decimal(occupied[1]) or ZERO,
            reserved_weight_kg=_decimal(reserved[0]) or ZERO,
            reserved_volume_m3=_decimal(reserved[1]) or ZERO,
        )

    @staticmethod
    def _limit(scope: Any) -> CapacityLimit:
        return CapacityLimit(
            certified_weight_kg=_decimal(scope.certified_max_weight_kg),
            operational_weight_kg=_decimal(scope.operational_max_weight_kg),
            certified_volume_m3=_decimal(scope.certified_usable_volume_m3),
            operational_volume_m3=_decimal(scope.operational_usable_volume_m3),
            enforcement_mode=scope.capacity_enforcement_mode,
        )

    @staticmethod
    def _fits_dimensions(scope: Any, measures: PhysicalMeasures) -> bool:
        item_dimensions = [measures.length_m, measures.width_m, measures.height_m]
        scope_dimensions = [
            _decimal(scope.usable_length_m),
            _decimal(scope.usable_width_m),
            _decimal(scope.usable_height_m),
        ]
        if any(value is None for value in item_dimensions) or any(
            value is None for value in scope_dimensions
        ):
            return True
        item_sorted = sorted(value for value in item_dimensions if value is not None)
        scope_sorted = sorted(value for value in scope_dimensions if value is not None)
        return all(
            item <= available for item, available in zip(item_sorted, scope_sorted, strict=True)
        )

    async def _valid_override(
        self,
        *,
        company_id: uuid.UUID,
        location_id: uuid.UUID,
        override_id: uuid.UUID | None,
    ) -> bool:
        if override_id is None:
            return False
        row = await self._session.scalar(
            select(CapacityOperationalOverrideModel).where(
                CapacityOperationalOverrideModel.id == override_id,
                CapacityOperationalOverrideModel.company_id == company_id,
                CapacityOperationalOverrideModel.location_id == location_id,
                CapacityOperationalOverrideModel.status == "active",
                CapacityOperationalOverrideModel.valid_until > datetime.now(UTC),
            )
        )
        if row is None:
            raise InventoryOperationError(
                "La autorización operativa no es válida o ya venció.",
                code="capacity_override_invalid",
                status_code=409,
            )
        return True

    async def _group_location_ids(
        self,
        warehouse_id: uuid.UUID,
        ancestor: WarehouseCapacityGroup,
    ) -> list[uuid.UUID]:
        groups = list(
            (
                await self._session.scalars(
                    select(WarehouseCapacityGroup).where(
                        WarehouseCapacityGroup.warehouse_id == warehouse_id,
                    )
                )
            ).all()
        )
        children: dict[uuid.UUID | None, list[uuid.UUID]] = {}
        for group in groups:
            children.setdefault(group.parent_id, []).append(group.id)
        descendants: set[uuid.UUID] = set()
        pending = [ancestor.id]
        while pending:
            current = pending.pop()
            if current in descendants:
                continue
            descendants.add(current)
            pending.extend(children.get(current, []))
        return list(
            (
                await self._session.scalars(
                    select(Location.id).where(
                        Location.warehouse_id == warehouse_id,
                        Location.capacity_group_id.in_(descendants),
                    )
                )
            ).all()
        )

    async def _capacity_check(  # noqa: C901
        self,
        *,
        company_id: uuid.UUID,
        location_id: uuid.UUID,
        physical: _ResolvedPhysical,
        stock_status: StockStatus,
        override_id: uuid.UUID | None,
        exclude_reservation_id: uuid.UUID | None,
        lock: bool,
    ) -> tuple[_LocationContext, CapacityDecision]:
        context = await self._location_context(company_id, location_id, lock=lock)
        if context.warehouse.operational_status != "active":
            raise InventoryOperationError(
                "El almacén no admite ingresos en su estado actual.",
                code="warehouse_not_operational",
                status_code=409,
            )
        if context.location.lifecycle_status not in {"active", "blocked_out"}:
            raise InventoryOperationError(
                "La ubicación no admite ingresos en su estado actual.",
                code="location_not_inbound_eligible",
                status_code=409,
            )
        if stock_status is StockStatus.AVAILABLE and not context.location.storage_eligible:
            raise InventoryOperationError(
                "La ubicación no es elegible para almacenamiento normal.",
                code="location_not_storage_eligible",
                status_code=409,
            )
        try:
            require_quarantine_for_incomplete_measures(physical.measures, stock_status)
        except ValueError as exc:
            raise InventoryOperationError(str(exc), code="measurements_required") from exc
        consumption = physical.consumption or Consumption(ZERO, ZERO)
        has_override = await self._valid_override(
            company_id=company_id, location_id=location_id, override_id=override_id
        )

        scope_specs: list[tuple[str, Any, list[uuid.UUID] | None, bool]] = [
            ("location", context.location, [location_id], has_override)
        ]
        for group in context.groups:
            scope_specs.append(
                (
                    "capacity_group",
                    group,
                    await self._group_location_ids(context.warehouse.id, group),
                    False,
                )
            )
        scope_specs.append(("warehouse", context.warehouse, None, False))

        primary: CapacityDecision | None = None
        for scope_name, scope, location_ids, allow_override in scope_specs:
            if stock_status is StockStatus.AVAILABLE and not scope.storage_eligible:
                raise InventoryOperationError(
                    "Un límite estructural no es elegible para almacenamiento normal.",
                    code="capacity_scope_not_storage_eligible",
                    status_code=409,
                )
            if not self._fits_dimensions(scope, physical.measures):
                raise InventoryOperationError(
                    "Las dimensiones del bulto no caben en el espacio útil.",
                    code="capacity_dimension_mismatch",
                    status_code=409,
                )
            usage = await self._usage(
                company_id=company_id,
                warehouse_id=context.warehouse.id,
                location_ids=location_ids,
                exclude_reservation_id=exclude_reservation_id,
            )
            decision = evaluate_capacity(
                limit=self._limit(scope),
                usage=usage,
                incoming=consumption,
                has_operational_override=allow_override,
            )
            if primary is None:
                primary = decision
            if not decision.allowed:
                code = decision.code
                if scope_name != "location" and code != "certified_capacity_exceeded":
                    code = (
                        "capacity_group_exceeded"
                        if scope_name == "capacity_group"
                        else "warehouse_capacity_exceeded"
                    )
                return context, CapacityDecision(
                    allowed=False,
                    code=code,
                    projected_weight_kg=decision.projected_weight_kg,
                    projected_volume_m3=decision.projected_volume_m3,
                    weight_utilization_pct=decision.weight_utilization_pct,
                    volume_utilization_pct=decision.volume_utilization_pct,
                    limiting_metric=decision.limiting_metric,
                )
        assert primary is not None
        if physical.consumption is None:
            return context, CapacityDecision(
                allowed=True,
                code=None,
                projected_weight_kg=None,
                projected_volume_m3=None,
                weight_utilization_pct=None,
                volume_utilization_pct=None,
                limiting_metric=None,
                measurement_status=MeasurementStatus.INCOMPLETE,
            )
        return context, primary

    async def preview_capacity(
        self,
        *,
        company_id: uuid.UUID,
        location_id: uuid.UUID,
        item_id: uuid.UUID,
        packaging_id: uuid.UUID | None,
        quantity_base: Decimal,
        stock_status: StockStatus,
        actual_measures: PhysicalMeasures | None,
        override_id: uuid.UUID | None = None,
        exclude_reservation_id: uuid.UUID | None = None,
    ) -> CapacityDecision:
        physical = await self._resolve_physical(
            company_id=company_id,
            item_id=item_id,
            packaging_id=packaging_id,
            quantity_base=quantity_base,
            actual_measures=actual_measures,
        )
        _context, decision = await self._capacity_check(
            company_id=company_id,
            location_id=location_id,
            physical=physical,
            stock_status=stock_status,
            override_id=override_id,
            exclude_reservation_id=exclude_reservation_id,
            lock=False,
        )
        return decision

    async def reserve_capacity(
        self,
        *,
        company_id: uuid.UUID,
        location_id: uuid.UUID,
        item_id: uuid.UUID,
        packaging_id: uuid.UUID | None,
        quantity_base: Decimal,
        stock_status: StockStatus,
        actual_measures: PhysicalMeasures | None,
        expires_at: datetime,
        actor_id: uuid.UUID,
        override_id: uuid.UUID | None = None,
    ) -> tuple[CapacityReservation, CapacityDecision]:
        physical = await self._resolve_physical(
            company_id=company_id,
            item_id=item_id,
            packaging_id=packaging_id,
            quantity_base=quantity_base,
            actual_measures=actual_measures,
        )
        context, decision = await self._capacity_check(
            company_id=company_id,
            location_id=location_id,
            physical=physical,
            stock_status=stock_status,
            override_id=override_id,
            exclude_reservation_id=None,
            lock=True,
        )
        if not decision.allowed:
            raise InventoryOperationError(
                "La capacidad proyectada excede un límite aplicable.",
                code=decision.code or "capacity_exceeded",
                status_code=409,
            )
        if expires_at <= datetime.now(UTC):
            raise InventoryOperationError(
                "La ventana de la reserva venció durante la operación; intente de nuevo.",
                code="capacity_reservation_window_elapsed",
                status_code=409,
            )
        consumption = physical.consumption or Consumption(ZERO, ZERO)
        row = CapacityReservationModel(
            company_id=company_id,
            warehouse_id=context.warehouse.id,
            location_id=location_id,
            inventory_item_id=item_id,
            packaging_definition_id=packaging_id,
            quantity_base=quantity_base,
            reserved_weight_kg=consumption.weight_kg,
            reserved_volume_m3=consumption.volume_m3,
            measurement_status=(
                MeasurementStatus.COMPLETE.value
                if physical.measures.is_complete
                else MeasurementStatus.INCOMPLETE.value
            ),
            stock_status=stock_status.value,
            status="active",
            expires_at=expires_at,
            created_by=actor_id,
            operational_override_id=override_id,
        )
        self._session.add(row)
        await self._session.flush()
        return _reservation_domain(row), decision

    async def change_reservation_status(
        self,
        *,
        company_id: uuid.UUID,
        reservation_id: uuid.UUID,
        action: str,
        actor_id: uuid.UUID,
    ) -> CapacityReservation:
        del actor_id  # actor is recorded by the API audit log
        row = await self._session.scalar(
            select(CapacityReservationModel)
            .where(
                CapacityReservationModel.company_id == company_id,
                CapacityReservationModel.id == reservation_id,
            )
            .with_for_update()
        )
        if row is None:
            raise InventoryOperationError(
                "Reserva no encontrada.", code="capacity_reservation_not_found", status_code=404
            )
        now = datetime.now(UTC)
        if row.status == "expired":
            raise InventoryOperationError(
                "La reserva ya está cerrada.",
                code="capacity_reservation_closed",
                status_code=409,
            )
        if row.status in {"consumed", "cancelled"}:
            raise InventoryOperationError(
                "La reserva ya está cerrada.", code="capacity_reservation_closed", status_code=409
            )
        if row.expires_at <= now:
            row.status = "expired"
            await self._session.flush()
            return _reservation_domain(row)
        if action == "confirm":
            row.status = "confirmed"
            row.confirmed_at = now
        elif action == "cancel":
            row.status = "cancelled"
            row.cancelled_at = now
        else:
            raise InventoryOperationError(
                "Acción de reserva no admitida.", code="invalid_reservation_action"
            )
        await self._session.flush()
        return _reservation_domain(row)

    @staticmethod
    def _handling_unit_dict(row: InventoryHandlingUnitModel) -> dict[str, Any]:
        measurements_complete = row.measurement_status != MeasurementStatus.INCOMPLETE.value
        return {
            "id": row.id,
            "company_id": row.company_id,
            "warehouse_id": row.warehouse_id,
            "location_id": row.location_id,
            "inventory_item_id": row.inventory_item_id,
            "packaging_definition_id": row.packaging_definition_id,
            "code": row.code,
            "lot_code": row.lot_code,
            "expiry_date": row.expiry_date,
            "quantity_base": row.quantity_base,
            "actual_gross_weight_kg": row.actual_gross_weight_kg,
            "actual_length_m": row.actual_length_m,
            "actual_width_m": row.actual_width_m,
            "actual_height_m": row.actual_height_m,
            "actual_volume_m3": row.actual_volume_m3,
            "occupied_weight_kg": (row.occupied_weight_kg if measurements_complete else None),
            "occupied_volume_m3": (row.occupied_volume_m3 if measurements_complete else None),
            "stock_status": row.stock_status,
            "measurement_status": row.measurement_status,
            "measurement_source": row.measurement_source,
            "closed_at": row.closed_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    async def verify_handling_unit_measurements(
        self,
        *,
        company_id: uuid.UUID,
        handling_unit_id: uuid.UUID,
        measures: PhysicalMeasures,
        source: str,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        del actor_id  # The API appends the required audit record transactionally.
        measures.validate()
        if not measures.is_complete:
            raise InventoryOperationError(
                "La verificación requiere peso y volumen completos.",
                code="verified_measurements_required",
            )
        if source not in {MeasurementSource.MANUAL.value, MeasurementSource.DEVICE.value}:
            raise InventoryOperationError(
                "La fuente de medición no es válida.", code="invalid_measurement_source"
            )

        candidate = await self._session.scalar(
            select(InventoryHandlingUnitModel).where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.id == handling_unit_id,
            )
        )
        if candidate is None or candidate.closed_at is not None:
            raise InventoryOperationError(
                "Unidad logística no encontrada o cerrada.",
                code="handling_unit_not_available",
                status_code=404,
            )
        expected_location_id = candidate.location_id
        await self._location_context(company_id, expected_location_id, lock=True)
        row = await self._session.scalar(
            select(InventoryHandlingUnitModel)
            .where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.id == handling_unit_id,
            )
            .with_for_update()
        )
        if row is None or row.closed_at is not None or row.location_id != expected_location_id:
            raise InventoryOperationError(
                "La unidad logística cambió mientras se verificaba; recargue e intente de nuevo.",
                code="handling_unit_concurrency_conflict",
                status_code=409,
            )

        consumption = calculate_measured_consumption(measures)
        assert consumption is not None

        balance = await self._balance(
            company_id=company_id,
            warehouse_id=row.warehouse_id,
            location_id=row.location_id,
            item_id=row.inventory_item_id,
            stock_status=row.stock_status,
            lot_code=row.lot_code,
            expiry_date=row.expiry_date,
            lock=True,
        )
        if balance is None:
            raise InventoryOperationError(
                "No existe el saldo asociado a la unidad logística.",
                code="inventory_projection_inconsistent",
                status_code=409,
            )
        delta_weight = consumption.weight_kg - row.occupied_weight_kg
        delta_volume = consumption.volume_m3 - row.occupied_volume_m3
        projected_weight = balance.occupied_weight_kg + delta_weight
        projected_volume = balance.occupied_volume_m3 + delta_volume
        if projected_weight < ZERO or projected_volume < ZERO:
            raise InventoryOperationError(
                "La medición produciría una proyección física inválida.",
                code="inventory_projection_inconsistent",
                status_code=409,
            )
        balance.occupied_weight_kg = projected_weight
        balance.occupied_volume_m3 = projected_volume
        row.actual_gross_weight_kg = measures.gross_weight_kg
        row.actual_length_m = measures.length_m
        row.actual_width_m = measures.width_m
        row.actual_height_m = measures.height_m
        row.actual_volume_m3 = measures.derived_volume_m3
        row.occupied_weight_kg = consumption.weight_kg
        row.occupied_volume_m3 = consumption.volume_m3
        row.measurement_status = MeasurementStatus.VERIFIED.value
        row.measurement_source = source
        await self._session.flush()
        return self._handling_unit_dict(row)

    async def list_handling_units(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID | None = None,
        item_id: uuid.UUID | None = None,
        stock_status: StockStatus | None = None,
        include_closed: bool = False,
    ) -> list[dict[str, Any]]:
        filters = [
            InventoryHandlingUnitModel.company_id == company_id,
            InventoryHandlingUnitModel.warehouse_id == warehouse_id,
        ]
        if location_id is not None:
            filters.append(InventoryHandlingUnitModel.location_id == location_id)
        if item_id is not None:
            filters.append(InventoryHandlingUnitModel.inventory_item_id == item_id)
        if stock_status is not None:
            filters.append(InventoryHandlingUnitModel.stock_status == stock_status.value)
        if not include_closed:
            filters.append(InventoryHandlingUnitModel.closed_at.is_(None))
        rows = list(
            (
                await self._session.scalars(
                    select(InventoryHandlingUnitModel)
                    .where(*filters)
                    .order_by(InventoryHandlingUnitModel.created_at.desc())
                )
            ).all()
        )
        return [self._handling_unit_dict(row) for row in rows]

    async def list_balances(  # noqa: C901
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID | None = None,
        item_id: uuid.UUID | None = None,
        stock_status: StockStatus | None = None,
        lot_code: str | None = None,
        expiry_before: date | None = None,
    ) -> list[dict[str, Any]]:
        filters = [
            InventoryBalanceModel.company_id == company_id,
            InventoryBalanceModel.warehouse_id == warehouse_id,
            InventoryBalanceModel.quantity_base > ZERO,
        ]
        if location_id is not None:
            filters.append(InventoryBalanceModel.location_id == location_id)
        if item_id is not None:
            filters.append(InventoryBalanceModel.inventory_item_id == item_id)
        if stock_status is not None:
            filters.append(InventoryBalanceModel.stock_status == stock_status.value)
        if lot_code is not None:
            filters.append(InventoryBalanceModel.lot_code == lot_code)
        if expiry_before is not None:
            filters.append(InventoryBalanceModel.expiry_date <= expiry_before)
        rows = list(
            (
                await self._session.scalars(
                    select(InventoryBalanceModel)
                    .where(*filters)
                    .order_by(
                        InventoryBalanceModel.location_id,
                        InventoryBalanceModel.inventory_item_id,
                        InventoryBalanceModel.expiry_date,
                    )
                )
            ).all()
        )
        unmeasured_filters = [
            InventoryHandlingUnitModel.company_id == company_id,
            InventoryHandlingUnitModel.warehouse_id == warehouse_id,
            InventoryHandlingUnitModel.closed_at.is_(None),
            InventoryHandlingUnitModel.measurement_status == "incomplete",
        ]
        if location_id is not None:
            unmeasured_filters.append(InventoryHandlingUnitModel.location_id == location_id)
        if item_id is not None:
            unmeasured_filters.append(InventoryHandlingUnitModel.inventory_item_id == item_id)
        if stock_status is not None:
            unmeasured_filters.append(InventoryHandlingUnitModel.stock_status == stock_status.value)
        if lot_code is not None:
            unmeasured_filters.append(InventoryHandlingUnitModel.lot_code == lot_code)
        if expiry_before is not None:
            unmeasured_filters.append(InventoryHandlingUnitModel.expiry_date <= expiry_before)
        unmeasured_rows = (
            await self._session.execute(
                select(
                    InventoryHandlingUnitModel.location_id,
                    InventoryHandlingUnitModel.inventory_item_id,
                    InventoryHandlingUnitModel.stock_status,
                    InventoryHandlingUnitModel.lot_code,
                    InventoryHandlingUnitModel.expiry_date,
                ).where(*unmeasured_filters)
            )
        ).all()
        unmeasured_keys = {
            (location, item, status, lot, expiry)
            for location, item, status, lot, expiry in unmeasured_rows
        }
        result: list[dict[str, Any]] = []
        for row in rows:
            key = (
                row.location_id,
                row.inventory_item_id,
                row.stock_status,
                row.lot_code,
                row.expiry_date,
            )
            measurements_complete = key not in unmeasured_keys
            result.append(
                {
                    "id": row.id,
                    "company_id": row.company_id,
                    "warehouse_id": row.warehouse_id,
                    "location_id": row.location_id,
                    "inventory_item_id": row.inventory_item_id,
                    "stock_status": row.stock_status,
                    "lot_code": row.lot_code,
                    "expiry_date": row.expiry_date,
                    "quantity_base": row.quantity_base,
                    "occupied_weight_kg": (
                        row.occupied_weight_kg if measurements_complete else None
                    ),
                    "occupied_volume_m3": (
                        row.occupied_volume_m3 if measurements_complete else None
                    ),
                    "measurement_status": ("complete" if measurements_complete else "incomplete"),
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
            )
        return result

    async def _balance(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        item_id: uuid.UUID,
        stock_status: str,
        lot_code: str | None,
        expiry_date: date | None,
        lock: bool,
    ) -> InventoryBalanceModel | None:
        stmt = select(InventoryBalanceModel).where(
            InventoryBalanceModel.company_id == company_id,
            InventoryBalanceModel.warehouse_id == warehouse_id,
            InventoryBalanceModel.location_id == location_id,
            InventoryBalanceModel.inventory_item_id == item_id,
            InventoryBalanceModel.stock_status == stock_status,
            (
                InventoryBalanceModel.lot_code.is_(None)
                if lot_code is None
                else InventoryBalanceModel.lot_code == lot_code
            ),
            (
                InventoryBalanceModel.expiry_date.is_(None)
                if expiry_date is None
                else InventoryBalanceModel.expiry_date == expiry_date
            ),
        )
        if lock:
            stmt = stmt.with_for_update()
        return cast(InventoryBalanceModel | None, await self._session.scalar(stmt))

    async def _change_balance(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        item_id: uuid.UUID,
        stock_status: str,
        lot_code: str | None,
        expiry_date: date | None,
        quantity: Decimal,
        weight: Decimal,
        volume: Decimal,
    ) -> None:
        row = await self._balance(
            company_id=company_id,
            warehouse_id=warehouse_id,
            location_id=location_id,
            item_id=item_id,
            stock_status=stock_status,
            lot_code=lot_code,
            expiry_date=expiry_date,
            lock=True,
        )
        if row is None:
            if quantity < ZERO:
                raise InventoryOperationError(
                    "No existe saldo en la ubicación de origen.",
                    code="insufficient_inventory_balance",
                    status_code=409,
                )
            row = InventoryBalanceModel(
                company_id=company_id,
                warehouse_id=warehouse_id,
                location_id=location_id,
                inventory_item_id=item_id,
                stock_status=stock_status,
                lot_code=lot_code,
                expiry_date=expiry_date,
                quantity_base=ZERO,
                occupied_weight_kg=ZERO,
                occupied_volume_m3=ZERO,
            )
            self._session.add(row)
        projected = (
            row.quantity_base + quantity,
            row.occupied_weight_kg + weight,
            row.occupied_volume_m3 + volume,
        )
        if any(value < ZERO for value in projected):
            raise InventoryOperationError(
                "El movimiento produciría un saldo físico negativo.",
                code="insufficient_inventory_balance",
                status_code=409,
            )
        row.quantity_base, row.occupied_weight_kg, row.occupied_volume_m3 = projected

    @staticmethod
    def _fingerprint(
        movement_type: str,
        source_reference: str | None,
        lines: list[dict[str, Any]],
        reservation_id: uuid.UUID | None,
    ) -> str:
        canonical = json.dumps(
            {
                "movement_type": movement_type,
                "source_reference": source_reference,
                "reservation_id": str(reservation_id) if reservation_id else None,
                "lines": lines,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def _movement_dict(self, row: InventoryMovementModel) -> dict[str, Any]:
        lines = list(
            (
                await self._session.scalars(
                    select(InventoryMovementLineModel)
                    .where(InventoryMovementLineModel.movement_id == row.id)
                    .order_by(InventoryMovementLineModel.line_number)
                )
            ).all()
        )
        return {
            "id": row.id,
            "company_id": row.company_id,
            "movement_type": row.movement_type,
            "idempotency_key": row.idempotency_key,
            "source_reference": row.source_reference,
            "reservation_id": row.reservation_id,
            "posted_at": row.posted_at,
            "lines": [
                {
                    "id": line.id,
                    "line_number": line.line_number,
                    "inventory_item_id": line.inventory_item_id,
                    "handling_unit_id": line.handling_unit_id,
                    "operational_override_id": line.operational_override_id,
                    "from_location_id": line.from_location_id,
                    "to_location_id": line.to_location_id,
                    "quantity_base": line.quantity_base,
                    "occupied_weight_kg": (
                        line.occupied_weight_kg if line.measurement_status != "incomplete" else None
                    ),
                    "occupied_volume_m3": (
                        line.occupied_volume_m3 if line.measurement_status != "incomplete" else None
                    ),
                    "measurement_status": line.measurement_status,
                    "lot_code": line.lot_code,
                    "expiry_date": line.expiry_date,
                }
                for line in lines
            ],
        }

    async def post_movement(  # noqa: C901
        self,
        *,
        company_id: uuid.UUID,
        idempotency_key: str,
        movement_type: str,
        source_reference: str | None,
        lines: list[dict[str, Any]],
        actor_id: uuid.UUID,
        reservation_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        fingerprint = self._fingerprint(movement_type, source_reference, lines, reservation_id)
        advisory_key = _advisory_lock_key("inventory-movement", company_id, idempotency_key)
        # The repository is PostgreSQL-specific.  A transaction-scoped advisory
        # lock makes the company-wide idempotency key safe even when two retries
        # reference different warehouses and therefore lock different rows.
        await self._session.execute(select(func.pg_advisory_xact_lock(advisory_key)))
        existing = await self._session.scalar(
            select(InventoryMovementModel).where(
                InventoryMovementModel.company_id == company_id,
                InventoryMovementModel.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise InventoryOperationError(
                    "La clave de idempotencia ya se usó con otro contenido.",
                    code="idempotency_conflict",
                    status_code=409,
                )
            return await self._movement_dict(existing)

        reservation: CapacityReservationModel | None = None
        if reservation_id is not None:
            reservation = await self._session.scalar(
                select(CapacityReservationModel)
                .where(
                    CapacityReservationModel.company_id == company_id,
                    CapacityReservationModel.id == reservation_id,
                )
                .with_for_update()
            )
            if reservation is None:
                raise InventoryOperationError(
                    "Reserva no encontrada.", code="capacity_reservation_not_found", status_code=404
                )
            if reservation.status not in {
                "active",
                "confirmed",
            } or reservation.expires_at <= datetime.now(UTC):
                raise InventoryOperationError(
                    "La reserva no está vigente.",
                    code="capacity_reservation_stale",
                    status_code=409,
                )
            destination_lines = [line for line in lines if line.get("to_location_id")]
            if len(destination_lines) != 1:
                raise InventoryOperationError(
                    "Una reserva solo puede consumirse con una línea de destino.",
                    code="capacity_reservation_mismatch",
                )
            reserved_line = destination_lines[0]
            if (
                reserved_line.get("to_location_id") != reservation.location_id
                or reserved_line.get("inventory_item_id") != reservation.inventory_item_id
                or Decimal(str(reserved_line.get("quantity_base"))) != reservation.quantity_base
            ):
                raise InventoryOperationError(
                    "El movimiento no coincide con la reserva de capacidad.",
                    code="capacity_reservation_mismatch",
                    status_code=409,
                )

        # Lock all affected physical scopes in a deterministic order before changing balances.
        location_ids = {
            location_id
            for line in lines
            for location_id in (line.get("from_location_id"), line.get("to_location_id"))
            if location_id is not None
        }
        contexts: dict[uuid.UUID, _LocationContext] = {}
        discovered: list[tuple[uuid.UUID, uuid.UUID]] = []
        for location_id in location_ids:
            context = await self._location_context(company_id, location_id, lock=False)
            contexts[location_id] = context
            discovered.append((context.warehouse.id, location_id))
        for _warehouse_id, location_id in sorted(
            discovered, key=lambda pair: (str(pair[0]), str(pair[1]))
        ):
            contexts[location_id] = await self._location_context(company_id, location_id, lock=True)

        now = datetime.now(UTC)
        movement = InventoryMovementModel(
            company_id=company_id,
            movement_type=movement_type,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            source_reference=source_reference,
            reservation_id=reservation_id,
            posted_at=now,
            posted_by=actor_id,
            created_at=now,
        )
        self._session.add(movement)
        await self._session.flush()

        for line_number, data in enumerate(lines, start=1):
            item_id = data["inventory_item_id"]
            quantity = Decimal(str(data["quantity_base"]))
            from_location_id = data.get("from_location_id")
            to_location_id = data.get("to_location_id")
            from_status = _stock_status_value(data.get("from_stock_status"))
            to_status = _stock_status_value(data.get("to_stock_status"))
            handling_unit: InventoryHandlingUnitModel | None = None
            physical: _ResolvedPhysical | None = None
            packaging_snapshot: dict[str, Any] | None = None
            lot_code = data.get("lot_code")
            expiry_date = data.get("expiry_date")
            line_override_id = data.get("capacity_override_id") or (
                reservation.operational_override_id if reservation is not None else None
            )

            handling_unit_id = data.get("handling_unit_id")
            if handling_unit_id is not None:
                handling_unit = await self._session.scalar(
                    select(InventoryHandlingUnitModel)
                    .where(
                        InventoryHandlingUnitModel.company_id == company_id,
                        InventoryHandlingUnitModel.id == handling_unit_id,
                    )
                    .with_for_update()
                )
                if handling_unit is None or handling_unit.closed_at is not None:
                    raise InventoryOperationError(
                        "Unidad logística no encontrada o cerrada.",
                        code="handling_unit_not_available",
                        status_code=404,
                    )
                if (
                    handling_unit.inventory_item_id != item_id
                    or handling_unit.location_id != from_location_id
                    or handling_unit.quantity_base != quantity
                    or handling_unit.stock_status != from_status
                ):
                    raise InventoryOperationError(
                        "La unidad logística no coincide con el origen del movimiento.",
                        code="handling_unit_mismatch",
                        status_code=409,
                    )
                weight = handling_unit.occupied_weight_kg
                volume = handling_unit.occupied_volume_m3
                lot_code = handling_unit.lot_code
                expiry_date = handling_unit.expiry_date
                packaging_snapshot = handling_unit.packaging_snapshot
                physical = _physical_from_handling_unit(handling_unit)
            else:
                if from_location_id is not None:
                    raise InventoryOperationError(
                        "Los traslados y salidas requieren una unidad logística existente.",
                        code="handling_unit_required",
                    )
                if to_status is None:
                    raise InventoryOperationError(
                        "La entrada requiere un estado de destino.",
                        code="invalid_movement_endpoints",
                    )
                actual = data.get("actual_measures")
                if isinstance(actual, dict):
                    actual = PhysicalMeasures(**actual)
                physical = await self._resolve_physical(
                    company_id=company_id,
                    item_id=item_id,
                    packaging_id=data.get("packaging_definition_id"),
                    quantity_base=quantity,
                    actual_measures=actual,
                )
                requested_status = StockStatus(to_status)
                try:
                    require_quarantine_for_incomplete_measures(physical.measures, requested_status)
                except ValueError as exc:
                    raise InventoryOperationError(str(exc), code="measurements_required") from exc
                if (
                    expiry_date is not None
                    and expiry_date < datetime.now(UTC).date()
                    and requested_status is StockStatus.AVAILABLE
                ):
                    raise InventoryOperationError(
                        "Un lote vencido solo puede recibirse en cuarentena.",
                        code="expired_lot_requires_quarantine",
                    )
                consumption = physical.consumption or Consumption(ZERO, ZERO)
                weight, volume = consumption.weight_kg, consumption.volume_m3
                packaging_snapshot = physical.snapshot

            if from_location_id is not None:
                if from_status is None:
                    raise InventoryOperationError(
                        "La salida requiere un estado de origen.",
                        code="invalid_movement_endpoints",
                    )
                source = contexts[from_location_id]
                if handling_unit is not None and source.warehouse.id != handling_unit.warehouse_id:
                    raise InventoryOperationError(
                        "El almacén de origen no coincide con la unidad logística.",
                        code="handling_unit_mismatch",
                        status_code=409,
                    )
                await self._change_balance(
                    company_id=company_id,
                    warehouse_id=source.warehouse.id,
                    location_id=from_location_id,
                    item_id=item_id,
                    stock_status=from_status,
                    lot_code=lot_code,
                    expiry_date=expiry_date,
                    quantity=-quantity,
                    weight=-weight,
                    volume=-volume,
                )

            if to_location_id is not None:
                if to_status is None:
                    raise InventoryOperationError(
                        "El movimiento requiere un estado de destino.",
                        code="invalid_movement_endpoints",
                    )
                if physical is None:
                    raise InventoryOperationError(
                        "No fue posible reconstruir las medidas del movimiento.",
                        code="handling_unit_measurements_inconsistent",
                        status_code=409,
                    )
                _destination, decision = await self._capacity_check(
                    company_id=company_id,
                    location_id=to_location_id,
                    physical=physical,
                    stock_status=StockStatus(to_status),
                    override_id=line_override_id,
                    exclude_reservation_id=reservation.id if reservation else None,
                    lock=False,
                )
                if not decision.allowed:
                    raise InventoryOperationError(
                        "La capacidad proyectada excede un límite aplicable.",
                        code=decision.code or "capacity_exceeded",
                        status_code=409,
                    )
                destination = contexts[to_location_id]
                await self._change_balance(
                    company_id=company_id,
                    warehouse_id=destination.warehouse.id,
                    location_id=to_location_id,
                    item_id=item_id,
                    stock_status=to_status,
                    lot_code=lot_code,
                    expiry_date=expiry_date,
                    quantity=quantity,
                    weight=weight,
                    volume=volume,
                )

            if handling_unit is None:
                assert to_location_id is not None
                assert physical is not None
                assert to_status is not None
                destination = contexts[to_location_id]
                handling_unit = InventoryHandlingUnitModel(
                    company_id=company_id,
                    warehouse_id=destination.warehouse.id,
                    location_id=to_location_id,
                    inventory_item_id=item_id,
                    packaging_definition_id=data.get("packaging_definition_id"),
                    code=(
                        str(data["handling_unit_code"]).strip().upper()
                        if data.get("handling_unit_code")
                        else f"HU-{uuid.uuid4().hex[:16].upper()}"
                    ),
                    lot_code=lot_code,
                    expiry_date=expiry_date,
                    quantity_base=quantity,
                    packaging_snapshot=packaging_snapshot,
                    actual_gross_weight_kg=(
                        physical.measures.gross_weight_kg
                        if physical.source is MeasurementSource.RECEIPT
                        else None
                    ),
                    actual_length_m=(
                        physical.measures.length_m
                        if physical.source is MeasurementSource.RECEIPT
                        else None
                    ),
                    actual_width_m=(
                        physical.measures.width_m
                        if physical.source is MeasurementSource.RECEIPT
                        else None
                    ),
                    actual_height_m=(
                        physical.measures.height_m
                        if physical.source is MeasurementSource.RECEIPT
                        else None
                    ),
                    actual_volume_m3=(
                        physical.measures.derived_volume_m3
                        if physical.source is MeasurementSource.RECEIPT
                        else None
                    ),
                    occupied_weight_kg=weight,
                    occupied_volume_m3=volume,
                    stock_status=to_status,
                    measurement_status=(
                        MeasurementStatus.COMPLETE.value
                        if physical.measures.is_complete
                        else MeasurementStatus.INCOMPLETE.value
                    ),
                    measurement_source=physical.source.value,
                )
                self._session.add(handling_unit)
                await self._session.flush()
            elif to_location_id is None:
                handling_unit.closed_at = now
            else:
                assert to_status is not None
                destination = contexts[to_location_id]
                handling_unit.warehouse_id = destination.warehouse.id
                handling_unit.location_id = to_location_id
                handling_unit.stock_status = to_status

            movement_line = InventoryMovementLineModel(
                company_id=company_id,
                movement_id=movement.id,
                line_number=line_number,
                inventory_item_id=item_id,
                handling_unit_id=handling_unit.id,
                operational_override_id=line_override_id,
                lot_code=lot_code,
                expiry_date=expiry_date,
                from_warehouse_id=(
                    contexts[from_location_id].warehouse.id if from_location_id else None
                ),
                from_location_id=from_location_id,
                to_warehouse_id=(contexts[to_location_id].warehouse.id if to_location_id else None),
                to_location_id=to_location_id,
                from_stock_status=from_status,
                to_stock_status=to_status,
                quantity_base=quantity,
                occupied_weight_kg=weight,
                occupied_volume_m3=volume,
                measurement_status=handling_unit.measurement_status,
                packaging_snapshot=packaging_snapshot,
            )
            self._session.add(movement_line)
            await self._session.flush()

        if reservation is not None:
            reservation.status = "consumed"
            reservation.consumed_at = now
        await self._session.flush()
        return await self._movement_dict(movement)

    async def _capacity_scope_payload(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        scope: Warehouse | WarehouseCapacityGroup | Location,
        scope_type: str,
        location_ids: list[uuid.UUID] | None,
    ) -> dict[str, Any]:
        usage = await self._usage(
            company_id=company_id,
            warehouse_id=warehouse_id,
            location_ids=location_ids,
            exclude_reservation_id=None,
        )
        decision = evaluate_capacity(
            limit=self._limit(scope), usage=usage, incoming=Consumption(ZERO, ZERO)
        )
        assert decision.projected_weight_kg is not None
        assert decision.projected_volume_m3 is not None
        hu_filters = [
            InventoryHandlingUnitModel.company_id == company_id,
            InventoryHandlingUnitModel.warehouse_id == warehouse_id,
            InventoryHandlingUnitModel.closed_at.is_(None),
            InventoryHandlingUnitModel.measurement_status == "incomplete",
        ]
        if location_ids is not None:
            hu_filters.append(InventoryHandlingUnitModel.location_id.in_(location_ids))
        unmeasured_handling_units = int(
            await self._session.scalar(
                select(func.count(InventoryHandlingUnitModel.id)).where(*hu_filters)
            )
            or 0
        )
        reservation_filters = [
            CapacityReservationModel.company_id == company_id,
            CapacityReservationModel.warehouse_id == warehouse_id,
            CapacityReservationModel.status.in_(("active", "confirmed")),
            CapacityReservationModel.expires_at > datetime.now(UTC),
            CapacityReservationModel.measurement_status == "incomplete",
        ]
        if location_ids is not None:
            reservation_filters.append(CapacityReservationModel.location_id.in_(location_ids))
        unmeasured_reservations = int(
            await self._session.scalar(
                select(func.count(CapacityReservationModel.id)).where(*reservation_filters)
            )
            or 0
        )
        measurements_complete = not (unmeasured_handling_units or unmeasured_reservations)
        percentages = [
            value
            for value in (decision.weight_utilization_pct, decision.volume_utilization_pct)
            if value is not None
        ]
        effective = max(percentages) if percentages and measurements_complete else None
        configuration_status = capacity_status_for(scope)
        certified_exceeded = (
            decision.projected_weight_kg is not None
            and scope.certified_max_weight_kg is not None
            and decision.projected_weight_kg > scope.certified_max_weight_kg
        ) or (
            decision.projected_volume_m3 is not None
            and scope.certified_usable_volume_m3 is not None
            and decision.projected_volume_m3 > scope.certified_usable_volume_m3
        )
        active_override = False
        if scope_type == "location" and effective is not None and effective >= Decimal("100"):
            active_override = bool(
                await self._session.scalar(
                    select(CapacityOperationalOverrideModel.id).where(
                        CapacityOperationalOverrideModel.company_id == company_id,
                        CapacityOperationalOverrideModel.location_id == scope.id,
                        CapacityOperationalOverrideModel.status == "active",
                        CapacityOperationalOverrideModel.valid_until > datetime.now(UTC),
                    )
                )
            )
        status = _capacity_summary_status(
            measurements_complete=measurements_complete,
            configuration_status=configuration_status,
            effective_utilization_pct=effective,
            active_override=active_override,
            certified_exceeded=certified_exceeded,
        )
        return {
            "scope_type": scope_type,
            "scope_id": scope.id,
            "code": str(getattr(scope, "code", "ALMACEN")),
            "name": str(getattr(scope, "name", getattr(scope, "code", "Almacén"))),
            "measurement_status": "complete" if measurements_complete else "incomplete",
            "status": status,
            "limiting_metric": decision.limiting_metric,
            "weight": _capacity_metric_payload(
                certified=_decimal(scope.certified_max_weight_kg),
                operational=_decimal(scope.operational_max_weight_kg),
                occupied=usage.occupied_weight_kg,
                reserved=usage.reserved_weight_kg,
                projected=decision.projected_weight_kg,
                utilization_pct=decision.weight_utilization_pct,
                occupied_known=not unmeasured_handling_units,
                reserved_known=not unmeasured_reservations,
            ),
            "volume": _capacity_metric_payload(
                certified=_decimal(scope.certified_usable_volume_m3),
                operational=_decimal(scope.operational_usable_volume_m3),
                occupied=usage.occupied_volume_m3,
                reserved=usage.reserved_volume_m3,
                projected=decision.projected_volume_m3,
                utilization_pct=decision.volume_utilization_pct,
                occupied_known=not unmeasured_handling_units,
                reserved_known=not unmeasured_reservations,
            ),
            "effective_utilization_pct": effective,
            "unmeasured_handling_units": unmeasured_handling_units,
            "unmeasured_reservations": unmeasured_reservations,
        }

    async def capacity_summary(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        warehouse_row = (
            await self._session.execute(
                select(Warehouse, Branch.company_id)
                .join(Branch, Branch.id == Warehouse.branch_id)
                .where(Warehouse.id == warehouse_id, Branch.company_id == company_id)
            )
        ).one_or_none()
        if warehouse_row is None:
            raise InventoryOperationError(
                "Almacén no encontrado.", code="warehouse_not_found", status_code=404
            )
        warehouse, _persisted_company = warehouse_row
        path_specs: list[
            tuple[Warehouse | WarehouseCapacityGroup | Location, str, list[uuid.UUID] | None]
        ]
        if location_id is None:
            path_specs = [(warehouse, "warehouse", None)]
        else:
            context = await self._location_context(company_id, location_id, lock=False)
            if context.warehouse.id != warehouse_id:
                raise InventoryOperationError(
                    "La ubicación no pertenece al almacén.",
                    code="location_warehouse_mismatch",
                    status_code=404,
                )
            path_specs = [(context.location, "location", [location_id])]
            for group in context.groups:
                path_specs.append(
                    (
                        group,
                        "capacity_group",
                        await self._group_location_ids(warehouse_id, group),
                    )
                )
            path_specs.append((warehouse, "warehouse", None))
        scope_path = [
            await self._capacity_scope_payload(
                company_id=company_id,
                warehouse_id=warehouse_id,
                scope=scope,
                scope_type=scope_type,
                location_ids=location_ids,
            )
            for scope, scope_type, location_ids in path_specs
        ]
        primary = scope_path[0]
        limiting_scope = None
        if all(item["measurement_status"] == "complete" for item in scope_path):
            comparable = [
                item for item in scope_path if item["effective_utilization_pct"] is not None
            ]
            if comparable:
                limiting = max(comparable, key=lambda item: item["effective_utilization_pct"])
                limiting_scope = {
                    key: limiting[key] for key in ("scope_type", "scope_id", "code", "name")
                }
        return {
            "scope_type": primary["scope_type"],
            "warehouse_id": warehouse_id,
            "location_id": location_id,
            "measurement_status": primary["measurement_status"],
            "status": primary["status"],
            "limiting_metric": primary["limiting_metric"],
            "weight": primary["weight"],
            "volume": primary["volume"],
            "effective_utilization_pct": primary["effective_utilization_pct"],
            "unmeasured_handling_units": primary["unmeasured_handling_units"],
            "unmeasured_reservations": primary["unmeasured_reservations"],
            "scope_path": scope_path,
            "limiting_scope": limiting_scope,
        }

    @staticmethod
    def _override_dict(row: CapacityOperationalOverrideModel) -> dict[str, Any]:
        return {
            "id": row.id,
            "location_id": row.location_id,
            "reason": row.reason,
            "valid_until": row.valid_until,
            "status": row.status,
            "granted_by": row.granted_by,
            "revoked_at": row.revoked_at,
            "revoked_by": row.revoked_by,
        }

    async def create_operational_override(
        self,
        *,
        company_id: uuid.UUID,
        location_id: uuid.UUID,
        reason: str,
        valid_until: datetime,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        context = await self._location_context(company_id, location_id, lock=True)
        now = datetime.now(UTC)
        if valid_until <= now:
            raise InventoryOperationError(
                "La vigencia de la autorización ya terminó; intente de nuevo.",
                code="invalid_override_expiry",
                status_code=409,
            )
        expired_overrides = list(
            (
                await self._session.scalars(
                    select(CapacityOperationalOverrideModel)
                    .where(
                        CapacityOperationalOverrideModel.company_id == company_id,
                        CapacityOperationalOverrideModel.location_id == location_id,
                        CapacityOperationalOverrideModel.status == "active",
                        CapacityOperationalOverrideModel.valid_until <= now,
                    )
                    .with_for_update()
                )
            ).all()
        )
        for expired in expired_overrides:
            expired.status = "expired"
            self._session.add(
                AuditLog(
                    action="EXPIRE",
                    user_id=actor_id,
                    company_id=company_id,
                    branch_id=context.warehouse.branch_id,
                    resource_type="inventory_capacity_operational_overrides",
                    resource_id=str(expired.id),
                    before_state={"status": "active"},
                    after_state={"status": "expired"},
                    metadata_={"reason": "valid_until_elapsed"},
                )
            )
        existing = await self._session.scalar(
            select(CapacityOperationalOverrideModel.id).where(
                CapacityOperationalOverrideModel.company_id == company_id,
                CapacityOperationalOverrideModel.location_id == location_id,
                CapacityOperationalOverrideModel.status == "active",
                CapacityOperationalOverrideModel.valid_until > now,
            )
        )
        if existing is not None:
            raise InventoryOperationError(
                "La ubicación ya tiene una autorización operativa vigente.",
                code="capacity_override_exists",
                status_code=409,
            )
        row = CapacityOperationalOverrideModel(
            company_id=company_id,
            warehouse_id=context.warehouse.id,
            location_id=location_id,
            reason=reason.strip(),
            valid_until=valid_until,
            status="active",
            granted_by=actor_id,
        )
        self._session.add(row)
        await self._session.flush()
        return self._override_dict(row)

    async def revoke_operational_override(
        self,
        *,
        company_id: uuid.UUID,
        override_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        candidate = await self._session.scalar(
            select(CapacityOperationalOverrideModel).where(
                CapacityOperationalOverrideModel.company_id == company_id,
                CapacityOperationalOverrideModel.id == override_id,
            )
        )
        if candidate is None:
            raise InventoryOperationError(
                "Autorización operativa no encontrada.",
                code="capacity_override_not_found",
                status_code=404,
            )
        await self._location_context(company_id, candidate.location_id, lock=True)
        row = await self._session.scalar(
            select(CapacityOperationalOverrideModel)
            .where(
                CapacityOperationalOverrideModel.company_id == company_id,
                CapacityOperationalOverrideModel.id == override_id,
            )
            .with_for_update()
        )
        if row is None:
            raise InventoryOperationError(
                "Autorización operativa no encontrada.",
                code="capacity_override_not_found",
                status_code=404,
            )
        if row.status == "expired":
            raise InventoryOperationError(
                "La autorización operativa ya no está vigente.",
                code="capacity_override_closed",
                status_code=409,
            )
        if row.status != "active":
            raise InventoryOperationError(
                "La autorización operativa ya no está vigente.",
                code="capacity_override_closed",
                status_code=409,
            )
        if row.valid_until <= datetime.now(UTC):
            row.status = "expired"
            await self._session.flush()
            return self._override_dict(row)
        row.status = "revoked"
        row.revoked_at = datetime.now(UTC)
        row.revoked_by = actor_id
        await self._session.flush()
        return self._override_dict(row)


__all__ = ["SqlAlchemyInventoryRepository"]
