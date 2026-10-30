"""Transactional PostgreSQL implementation of the inventory repository port."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.entities.inventory import (
    ZERO,
    CapacityDecision,
    CapacityLimit,
    CapacityReservation,
    CapacityUsage,
    Consumption,
    InventoryItem,
    InventoryItemStatusSummary,
    InventoryItemSummary,
    InventoryOperationError,
    MeasurementSource,
    MeasurementStatus,
    PackagingDefinition,
    PackagingType,
    PhysicalMeasures,
    ProductStockSnapshot,
    ReservationStatus,
    StockStatus,
    calculate_consumption,
    calculate_measured_consumption,
    evaluate_capacity,
    require_quarantine_for_incomplete_measures,
)
from app.domain.entities.inventory_release import (
    ReleaseRequirement,
    handling_unit_release_requirements,
)
from app.domain.entities.warehouse_capacity import capacity_status_for
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel, UnitModel
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
from app.infrastructure.models.inventory_label_confirmation import (
    InventoryLabelConfirmationModel,
)
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from app.infrastructure.models.organization import (
    Branch,
    Location,
    Warehouse,
    WarehouseCapacityGroup,
)
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.models.purchase import PurchaseDetailModel, PurchaseModel
from app.infrastructure.models.purchase_consolidation import (
    PurchaseConsolidationAwardModel,
    PurchaseConsolidationModel,
    PurchaseConsolidationSourceModel,
)
from app.infrastructure.models.purchase_order import PurchaseOrderDetailModel, PurchaseOrderModel
from app.infrastructure.models.purchase_request import PurchaseRequestModel
from app.infrastructure.models.supplier import SupplierModel
from app.infrastructure.models.user import User
from app.infrastructure.repositories.retaceo_readiness import purchase_retaceo_readiness_error


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


def _require_labelled_split_in_quarantine(
    *,
    label_confirmation_required: bool,
    from_status: str | None,
    movement_type: str,
    to_status: str | None,
) -> None:
    is_quarantine_putaway = (
        from_status == StockStatus.QUARANTINE.value
        and movement_type == "putaway"
        and to_status == StockStatus.QUARANTINE.value
    )
    is_partial_transfer_receipt = (
        from_status == StockStatus.IN_TRANSIT.value
        and movement_type == "transfer"
        and to_status == StockStatus.QUARANTINE.value
    )
    if label_confirmation_required and not (is_quarantine_putaway or is_partial_transfer_receipt):
        raise InventoryOperationError(
            "Fraccione la unidad nueva durante la ubicación en cuarentena; cada parte requiere medidas y etiqueta propias.",
            code="labelled_handling_unit_split_requires_quarantine_putaway",
            status_code=409,
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
        packaging_unit_id=row.packaging_unit_id,
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


def _movement_history_filters(
    *,
    warehouse_id: uuid.UUID,
    period_from: date | None,
    period_to: date | None,
    query: str | None,
    lot_code: str | None,
    source_reference: str | None,
    direction: str | None,
) -> list[Any]:
    filters = []
    local_tz = ZoneInfo("America/El_Salvador")
    if period_from:
        filters.append(
            InventoryMovementModel.posted_at
            >= datetime.combine(period_from, datetime.min.time(), tzinfo=local_tz)
        )
    if period_to:
        filters.append(
            InventoryMovementModel.posted_at
            <= datetime.combine(period_to, datetime.max.time(), tzinfo=local_tz)
        )
    for value, columns in (
        (
            query,
            (
                ProductModel.name,
                ProductModel.sku,
                ProductVariantModel.name_override,
                ProductVariantModel.sku,
                InventoryHandlingUnitModel.code,
            ),
        ),
        (
            lot_code,
            (
                InventoryMovementLineModel.lot_code,
                InventoryLotDetailModel.code,
                InventoryLotModel.code,
            ),
        ),
        (source_reference, (InventoryMovementModel.source_reference,)),
    ):
        if value and value.strip():
            filters.append(
                or_(*[column.icontains(value.strip(), autoescape=True) for column in columns])
            )
    origin = InventoryMovementLineModel.from_warehouse_id
    destination = InventoryMovementLineModel.to_warehouse_id
    if direction == "incoming":
        filters.extend([destination == warehouse_id, or_(origin.is_(None), origin != warehouse_id)])
    elif direction == "outgoing":
        filters.extend(
            [origin == warehouse_id, or_(destination.is_(None), destination != warehouse_id)]
        )
    elif direction == "internal":
        filters.extend([origin == warehouse_id, destination == warehouse_id])
    return filters


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

    async def inventory_item_summary(
        self, *, company_id: uuid.UUID, item_id: uuid.UUID
    ) -> InventoryItemSummary | None:
        item_row = await self._session.scalar(
            select(InventoryItemModel).where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.id == item_id,
            )
        )
        if item_row is None:
            return None

        balance_filters = [
            InventoryBalanceModel.company_id == company_id,
            InventoryBalanceModel.inventory_item_id == item_id,
            InventoryBalanceModel.quantity_base > ZERO,
        ]
        balance_rows = (
            await self._session.execute(
                select(
                    InventoryBalanceModel.stock_status,
                    func.coalesce(func.sum(InventoryBalanceModel.quantity_base), ZERO),
                    func.coalesce(func.sum(InventoryBalanceModel.occupied_weight_kg), ZERO),
                    func.coalesce(func.sum(InventoryBalanceModel.occupied_volume_m3), ZERO),
                )
                .where(*balance_filters)
                .group_by(InventoryBalanceModel.stock_status)
            )
        ).all()
        incomplete_rows = (
            await self._session.execute(
                select(
                    InventoryHandlingUnitModel.stock_status,
                    func.count(InventoryHandlingUnitModel.id),
                )
                .where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.inventory_item_id == item_id,
                    InventoryHandlingUnitModel.closed_at.is_(None),
                    InventoryHandlingUnitModel.inventory_posted_at.is_not(None),
                    InventoryHandlingUnitModel.measurement_status
                    == MeasurementStatus.INCOMPLETE.value,
                )
                .group_by(InventoryHandlingUnitModel.stock_status)
            )
        ).all()
        incomplete_by_status = {
            StockStatus(status): int(count) for status, count in incomplete_rows
        }

        totals_by_status = {
            StockStatus(status): (quantity, weight, volume)
            for status, quantity, weight, volume in balance_rows
        }
        status_totals: list[InventoryItemStatusSummary] = []
        total_quantity = ZERO
        total_weight = ZERO
        total_volume = ZERO
        has_incomplete_measurements = False
        for stock_status in StockStatus:
            quantity, weight, volume = totals_by_status.get(stock_status, (ZERO, ZERO, ZERO))
            total_quantity += quantity
            total_weight += weight
            total_volume += volume
            incomplete = incomplete_by_status.get(stock_status, 0) > 0
            has_incomplete_measurements = has_incomplete_measurements or incomplete
            status_totals.append(
                InventoryItemStatusSummary(
                    stock_status=stock_status,
                    quantity_base=quantity,
                    occupied_weight_kg=None if incomplete else weight,
                    occupied_volume_m3=None if incomplete else volume,
                    measurement_status=(
                        MeasurementStatus.INCOMPLETE if incomplete else MeasurementStatus.COMPLETE
                    ),
                )
            )

        handling_unit_count = int(
            await self._session.scalar(
                select(func.count(InventoryHandlingUnitModel.id)).where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.inventory_item_id == item_id,
                    InventoryHandlingUnitModel.closed_at.is_(None),
                    InventoryHandlingUnitModel.inventory_posted_at.is_not(None),
                )
            )
            or 0
        )
        unmeasured_handling_units = sum(incomplete_by_status.values())
        warehouse_count, location_count, lot_count = (
            await self._session.execute(
                select(
                    func.count(func.distinct(InventoryBalanceModel.warehouse_id)),
                    func.count(func.distinct(InventoryBalanceModel.location_id)),
                    func.count(func.distinct(InventoryBalanceModel.lot_code)),
                ).where(*balance_filters)
            )
        ).one()

        return InventoryItemSummary(
            inventory_item_id=item_row.id,
            company_id=item_row.company_id,
            product_id=item_row.product_id,
            variant_id=item_row.variant_id,
            base_unit_id=item_row.base_unit_id,
            is_active=item_row.is_active,
            total_quantity_base=total_quantity,
            status_totals=tuple(status_totals),
            occupied_weight_kg=None if has_incomplete_measurements else total_weight,
            occupied_volume_m3=None if has_incomplete_measurements else total_volume,
            measurement_status=(
                MeasurementStatus.INCOMPLETE
                if has_incomplete_measurements
                else MeasurementStatus.COMPLETE
            ),
            handling_unit_count=handling_unit_count,
            unmeasured_handling_units=unmeasured_handling_units,
            warehouse_count=int(warehouse_count or 0),
            location_count=int(location_count or 0),
            lot_count=int(lot_count or 0),
        )

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
        packaging_unit_id: int,
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

        unit_enabled = await self._session.scalar(
            select(CompanyUnitModel.unit_id).where(
                CompanyUnitModel.company_id == company_id,
                CompanyUnitModel.unit_id == packaging_unit_id,
                CompanyUnitModel.is_enabled.is_(True),
            )
        )
        if unit_enabled is None:
            raise InventoryOperationError(
                "La unidad de empaque debe estar habilitada para la empresa.",
                code="packaging_unit_not_enabled",
            )
        if packaging_unit_id == item.base_unit_id and base_quantity != Decimal("1"):
            raise InventoryOperationError(
                "Si la unidad de empaque es la unidad base, la equivalencia debe ser 1 a 1.",
                code="packaging_unit_base_conversion_invalid",
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

        if await self._session.scalar(
            select(InventoryPackagingModel.id).where(
                InventoryPackagingModel.company_id == company_id,
                InventoryPackagingModel.inventory_item_id == item_id,
                InventoryPackagingModel.packaging_unit_id == packaging_unit_id,
                InventoryPackagingModel.is_current.is_(True),
                InventoryPackagingModel.is_active.is_(True),
            )
        ):
            raise InventoryOperationError(
                "Ya existe una equivalencia vigente para esa unidad de compra. Cree una nueva versión de esa presentación o desactive la anterior.",
                code="packaging_unit_conversion_exists",
                status_code=409,
            )

        row = InventoryPackagingModel(
            company_id=company_id,
            inventory_item_id=item_id,
            packaging_unit_id=packaging_unit_id,
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
                select(Location, Warehouse, Warehouse.company_id)
                .join(Warehouse, Warehouse.id == Location.warehouse_id)
                .where(Location.id == location_id, Warehouse.company_id == company_id)
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
                "packaging_unit_id": packaging.packaging_unit_id,
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
            "receipt_lot_id": row.inventory_lot_id,
            "packaging_definition_id": row.packaging_definition_id,
            "origin_handling_unit_id": row.origin_handling_unit_id,
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
        from app.infrastructure.repositories.inventory_valuation_repository import (
            SqlAlchemyInventoryValuationRepository,
        )

        # Keep the mutation order aligned with movements: company, physical scope, unit.
        await SqlAlchemyInventoryValuationRepository(self._session).lock(company_id)
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

        if getattr(row, "inventory_posted_at", True) is not None:
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
        enriched = await self._handling_units_with_release_metadata(
            company_id=company_id, rows=[row]
        )
        return enriched[0]

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
            InventoryHandlingUnitModel.inventory_posted_at.is_not(None),
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
        return await self._handling_units_with_release_metadata(company_id=company_id, rows=rows)

    async def _handling_units_with_release_metadata(
        self,
        *,
        company_id: uuid.UUID,
        rows: list[InventoryHandlingUnitModel],
    ) -> list[dict[str, Any]]:
        # Resolve identity in one batch, including legacy HUs without a receipt lot.
        identities = {}
        packaging = {}
        if rows:
            product_id = func.coalesce(
                InventoryItemModel.product_id, ProductVariantModel.product_id
            )
            identity_rows = (
                (
                    await self._session.execute(
                        select(
                            InventoryItemModel.id,
                            product_id.label("product_id"),
                            InventoryItemModel.base_unit_id.label("base_unit_id"),
                            func.coalesce(
                                ProductVariantModel.name_override, ProductModel.name
                            ).label("product_name"),
                            func.coalesce(ProductVariantModel.sku, ProductModel.sku).label(
                                "product_sku"
                            ),
                            UnitModel.name.label("base_unit_name"),
                            UnitModel.symbol.label("base_unit_symbol"),
                        )
                        .select_from(InventoryItemModel)
                        .outerjoin(
                            ProductVariantModel,
                            and_(
                                ProductVariantModel.id == InventoryItemModel.variant_id,
                                ProductVariantModel.company_id == company_id,
                            ),
                        )
                        .outerjoin(
                            ProductModel,
                            and_(
                                ProductModel.id_product == product_id,
                                ProductModel.company_id == company_id,
                            ),
                        )
                        .outerjoin(UnitModel, UnitModel.id_unit == InventoryItemModel.base_unit_id)
                        .where(
                            InventoryItemModel.company_id == company_id,
                            InventoryItemModel.id.in_({row.inventory_item_id for row in rows}),
                        )
                    )
                )
                .mappings()
                .all()
            )
            identities = {row["id"]: dict(row) for row in identity_rows}
            packaging_ids = {
                row.packaging_definition_id for row in rows if row.packaging_definition_id
            }
            if packaging_ids:
                definitions = (
                    await self._session.scalars(
                        select(InventoryPackagingModel).where(
                            InventoryPackagingModel.company_id == company_id,
                            InventoryPackagingModel.id.in_(packaging_ids),
                        )
                    )
                ).all()
                packaging = {definition.id: definition for definition in definitions}
        (
            release_reasons_by_unit,
            lots_by_id,
            purchase_codes,
            detail_codes,
        ) = await self._handling_unit_release_metadata(company_id=company_id, rows=rows)
        result: list[dict[str, Any]] = []
        for row in rows:
            unit_data = self._handling_unit_dict(row)
            identity = identities.get(row.inventory_item_id, {})
            unit_data.update({key: value for key, value in identity.items() if key != "id"})
            definition = (
                packaging.get(row.packaging_definition_id)
                if row.packaging_definition_id is not None
                else None
            )
            if definition is not None:
                unit_data["packaging_name"] = definition.name
                unit_data["packaging_base_quantity"] = definition.base_quantity
            receipt_lot = lots_by_id.get(row.inventory_lot_id) if row.inventory_lot_id else None
            if receipt_lot is not None:
                unit_data["receipt_lot_header_code"] = receipt_lot.code
                unit_data["received_at"] = receipt_lot.received_at
                unit_data["purchase_code"] = purchase_codes.get(receipt_lot.purchase_id)
            unit_data["receipt_lot_code"] = (
                detail_codes.get(row.inventory_lot_detail_id)
                if row.inventory_lot_detail_id is not None
                else None
            )
            if row.id in release_reasons_by_unit:
                unit_data["release_requirements"] = release_reasons_by_unit[row.id]
            result.append(unit_data)
        return result

    async def _handling_unit_release_metadata(
        self,
        *,
        company_id: uuid.UUID,
        rows: list[InventoryHandlingUnitModel],
    ) -> tuple[
        dict[uuid.UUID, list[str]],
        dict[uuid.UUID, InventoryLotModel],
        dict[uuid.UUID, str],
        dict[uuid.UUID, str],
    ]:
        release_units = [
            row
            for row in rows
            if row.stock_status == StockStatus.QUARANTINE.value and row.closed_at is None
        ]
        lots_by_id: dict[uuid.UUID, InventoryLotModel] = {}
        lot_ids = {row.inventory_lot_id for row in rows if row.inventory_lot_id}
        release_lot_ids = {row.inventory_lot_id for row in release_units if row.inventory_lot_id}
        if lot_ids:
            lots = list(
                (
                    await self._session.scalars(
                        select(InventoryLotModel).where(
                            InventoryLotModel.company_id == company_id,
                            InventoryLotModel.id.in_(lot_ids),
                        )
                    )
                ).all()
            )
            lots_by_id = {lot.id: lot for lot in lots}

        purchase_ids = {lot.purchase_id for lot in lots_by_id.values()}
        purchase_codes: dict[uuid.UUID, str] = {}
        if purchase_ids:
            purchase_rows = (
                await self._session.execute(
                    select(PurchaseModel.id, PurchaseModel.code).where(
                        PurchaseModel.company_id == company_id,
                        PurchaseModel.id.in_(purchase_ids),
                    )
                )
            ).all()
            purchase_codes = {row[0]: row[1] for row in purchase_rows}

        detail_ids = {row.inventory_lot_detail_id for row in rows if row.inventory_lot_detail_id}
        detail_codes: dict[uuid.UUID, str] = {}
        if detail_ids:
            detail_codes = {
                row[0]: row[1]
                for row in (
                    await self._session.execute(
                        select(InventoryLotDetailModel.id, InventoryLotDetailModel.code).where(
                            InventoryLotDetailModel.company_id == company_id,
                            InventoryLotDetailModel.id.in_(detail_ids),
                        )
                    )
                ).all()
            }

        label_confirmed_ids: set[uuid.UUID] = set()
        if release_units:
            label_confirmed_ids = set(
                (
                    await self._session.scalars(
                        select(InventoryLabelConfirmationModel.handling_unit_id)
                        .join(
                            InventoryHandlingUnitModel,
                            and_(
                                InventoryHandlingUnitModel.company_id
                                == InventoryLabelConfirmationModel.company_id,
                                InventoryHandlingUnitModel.id
                                == InventoryLabelConfirmationModel.handling_unit_id,
                                InventoryHandlingUnitModel.code
                                == InventoryLabelConfirmationModel.handling_unit_code,
                                InventoryHandlingUnitModel.label_revision
                                == InventoryLabelConfirmationModel.label_revision,
                                InventoryHandlingUnitModel.quantity_base
                                == InventoryLabelConfirmationModel.quantity_base,
                            ),
                        )
                        .where(
                            InventoryLabelConfirmationModel.company_id == company_id,
                            InventoryHandlingUnitModel.id.in_([unit.id for unit in release_units]),
                        )
                    )
                ).all()
            )

        retaceo_error_by_purchase: dict[uuid.UUID, str | None] = {}
        today = datetime.now(UTC).astimezone(ZoneInfo("America/El_Salvador")).date()
        release_purchase_ids = {
            lots_by_id[lot_id].purchase_id for lot_id in release_lot_ids if lot_id in lots_by_id
        }
        for lot in lots_by_id.values():
            if (
                lot.purchase_id not in release_purchase_ids
                or lot.purchase_id in retaceo_error_by_purchase
            ):
                continue
            retaceo_error_by_purchase[lot.purchase_id] = await purchase_retaceo_readiness_error(
                self._session,
                company_id=company_id,
                purchase_id=lot.purchase_id,
                received_at=lot.received_at,
            )

        release_reasons_by_unit: dict[uuid.UUID, list[str]] = {}
        for unit in release_units:
            release_lot = lots_by_id.get(unit.inventory_lot_id) if unit.inventory_lot_id else None
            reasons = handling_unit_release_requirements(
                is_partial=False,
                measurement_status=unit.measurement_status,
                measurement_source=unit.measurement_source,
                expiry_date=unit.expiry_date,
                today=today,
                label_confirmation_required=bool(
                    release_lot and release_lot.label_confirmation_required
                ),
                label_confirmed=unit.id in label_confirmed_ids,
                retaceo_readiness_error=(
                    retaceo_error_by_purchase.get(release_lot.purchase_id) if release_lot else None
                ),
            )
            release_reasons_by_unit[unit.id] = [reason.value for reason in reasons]
        return release_reasons_by_unit, lots_by_id, purchase_codes, detail_codes

    async def get_handling_unit_traceability(
        self,
        *,
        company_id: uuid.UUID,
        handling_unit_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        product_id = func.coalesce(InventoryItemModel.product_id, ProductVariantModel.product_id)
        unit_row = (
            await self._session.execute(
                select(
                    InventoryHandlingUnitModel,
                    product_id.label("target_product_id"),
                    ProductModel.sku.label("product_sku"),
                    ProductModel.name.label("product_name"),
                    ProductVariantModel.sku.label("variant_sku"),
                    ProductVariantModel.name_override.label("variant_name"),
                    UnitModel.name.label("base_unit_name"),
                    UnitModel.symbol.label("base_unit_symbol"),
                    Warehouse.code.label("warehouse_code"),
                    Warehouse.name.label("warehouse_name"),
                    Location.code.label("location_code"),
                    InventoryLotDetailModel.code.label("receipt_lot_code"),
                    InventoryLotModel.code.label("receipt_lot_header_code"),
                    InventoryLotModel.received_at.label("receipt_received_at"),
                )
                .join(
                    InventoryItemModel,
                    and_(
                        InventoryItemModel.id == InventoryHandlingUnitModel.inventory_item_id,
                        InventoryItemModel.company_id == InventoryHandlingUnitModel.company_id,
                    ),
                )
                .outerjoin(
                    ProductVariantModel,
                    and_(
                        ProductVariantModel.id == InventoryItemModel.variant_id,
                        ProductVariantModel.company_id == InventoryItemModel.company_id,
                    ),
                )
                .outerjoin(
                    ProductModel,
                    and_(
                        ProductModel.company_id == InventoryItemModel.company_id,
                        ProductModel.id_product == product_id,
                    ),
                )
                .join(UnitModel, UnitModel.id_unit == InventoryItemModel.base_unit_id)
                .join(
                    Warehouse,
                    and_(
                        Warehouse.id == InventoryHandlingUnitModel.warehouse_id,
                        Warehouse.company_id == company_id,
                    ),
                )
                .join(Location, Location.id == InventoryHandlingUnitModel.location_id)
                .outerjoin(
                    InventoryLotModel,
                    and_(
                        InventoryLotModel.company_id == InventoryHandlingUnitModel.company_id,
                        InventoryLotModel.id == InventoryHandlingUnitModel.inventory_lot_id,
                    ),
                )
                .outerjoin(
                    InventoryLotDetailModel,
                    and_(
                        InventoryLotDetailModel.company_id == InventoryHandlingUnitModel.company_id,
                        InventoryLotDetailModel.id
                        == InventoryHandlingUnitModel.inventory_lot_detail_id,
                        InventoryLotDetailModel.inventory_lot_id
                        == InventoryHandlingUnitModel.inventory_lot_id,
                        InventoryLotDetailModel.inventory_item_id
                        == InventoryHandlingUnitModel.inventory_item_id,
                    ),
                )
                .where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.id == handling_unit_id,
                )
            )
        ).one_or_none()
        if unit_row is None:
            return None

        handling_unit = unit_row[0]
        target_product_id = unit_row.target_product_id
        trace_unit_ids = [handling_unit.id]
        seen_unit_ids = {handling_unit.id}
        parent_unit = handling_unit
        while parent_unit.origin_handling_unit_id is not None:
            parent_id = parent_unit.origin_handling_unit_id
            if parent_id in seen_unit_ids:
                break
            parent_unit = await self._session.scalar(
                select(InventoryHandlingUnitModel).where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.id == parent_id,
                )
            )
            if parent_unit is None:
                break
            trace_unit_ids.append(parent_unit.id)
            seen_unit_ids.add(parent_unit.id)
        from_location = aliased(Location)
        to_location = aliased(Location)
        from_warehouse = aliased(Warehouse)
        to_warehouse = aliased(Warehouse)

        movement_rows = (
            (
                await self._session.execute(
                    select(
                        InventoryMovementModel.id.label("movement_id"),
                        InventoryMovementModel.movement_type,
                        InventoryMovementModel.source_reference,
                        InventoryMovementModel.posted_at,
                        InventoryMovementModel.posted_by,
                        User.username.label("operator"),
                        InventoryMovementLineModel.from_stock_status,
                        InventoryMovementLineModel.to_stock_status,
                        InventoryMovementLineModel.quantity_base,
                        from_warehouse.code.label("from_warehouse_code"),
                        from_warehouse.name.label("from_warehouse_name"),
                        from_location.code.label("from_location_code"),
                        to_warehouse.code.label("to_warehouse_code"),
                        to_warehouse.name.label("to_warehouse_name"),
                        to_location.code.label("to_location_code"),
                    )
                    .select_from(InventoryMovementLineModel)
                    .join(
                        InventoryMovementModel,
                        and_(
                            InventoryMovementModel.id == InventoryMovementLineModel.movement_id,
                            InventoryMovementModel.company_id
                            == InventoryMovementLineModel.company_id,
                        ),
                    )
                    .outerjoin(User, User.id == InventoryMovementModel.posted_by)
                    .outerjoin(
                        from_warehouse,
                        and_(
                            from_warehouse.id == InventoryMovementLineModel.from_warehouse_id,
                            from_warehouse.company_id == company_id,
                        ),
                    )
                    .outerjoin(
                        from_location,
                        from_location.id == InventoryMovementLineModel.from_location_id,
                    )
                    .outerjoin(
                        to_warehouse,
                        and_(
                            to_warehouse.id == InventoryMovementLineModel.to_warehouse_id,
                            to_warehouse.company_id == company_id,
                        ),
                    )
                    .outerjoin(
                        to_location, to_location.id == InventoryMovementLineModel.to_location_id
                    )
                    .where(
                        InventoryMovementLineModel.company_id == company_id,
                        InventoryMovementLineModel.handling_unit_id.in_(trace_unit_ids),
                    )
                    .order_by(
                        InventoryMovementModel.posted_at,
                        InventoryMovementLineModel.line_number,
                    )
                )
            )
            .mappings()
            .all()
        )

        purchase_rows = (
            (
                await self._session.execute(
                    select(
                        PurchaseModel.code.label("purchase_code"),
                        PurchaseModel.purchase_date,
                        PurchaseOrderModel.code.label("purchase_order_code"),
                        SupplierModel.code.label("supplier_code"),
                        SupplierModel.name.label("supplier_name"),
                        InventoryMovementModel.posted_at.label("received_at"),
                        PurchaseConsolidationModel.code.label("consolidation_code"),
                        PurchaseRequestModel.id.label("request_id"),
                        PurchaseRequestModel.code.label("request_code"),
                        PurchaseRequestModel.request_date.label("requested_at"),
                        PurchaseRequestModel.required_date,
                        Branch.name.label("branch_name"),
                    )
                    .select_from(InventoryMovementLineModel)
                    .join(
                        InventoryMovementModel,
                        and_(
                            InventoryMovementModel.id == InventoryMovementLineModel.movement_id,
                            InventoryMovementModel.company_id
                            == InventoryMovementLineModel.company_id,
                        ),
                    )
                    .join(
                        PurchaseModel,
                        and_(
                            PurchaseModel.company_id == company_id,
                            PurchaseModel.inventory_movement_id == InventoryMovementModel.id,
                        ),
                    )
                    .join(
                        PurchaseOrderModel,
                        and_(
                            PurchaseOrderModel.company_id == PurchaseModel.company_id,
                            PurchaseOrderModel.id == PurchaseModel.purchase_order_id,
                        ),
                    )
                    .join(
                        SupplierModel,
                        and_(
                            SupplierModel.company_id == PurchaseModel.company_id,
                            SupplierModel.id_supplier == PurchaseModel.supplier_id,
                        ),
                    )
                    .join(
                        PurchaseDetailModel,
                        and_(
                            PurchaseDetailModel.company_id == PurchaseModel.company_id,
                            PurchaseDetailModel.purchase_id == PurchaseModel.id,
                            PurchaseDetailModel.product_id == target_product_id,
                        ),
                    )
                    .join(
                        PurchaseOrderDetailModel,
                        and_(
                            PurchaseOrderDetailModel.company_id == PurchaseOrderModel.company_id,
                            PurchaseOrderDetailModel.id
                            == PurchaseDetailModel.purchase_order_detail_id,
                        ),
                    )
                    .outerjoin(
                        PurchaseConsolidationAwardModel,
                        and_(
                            PurchaseConsolidationAwardModel.company_id
                            == PurchaseOrderDetailModel.company_id,
                            PurchaseConsolidationAwardModel.id
                            == PurchaseOrderDetailModel.purchase_consolidation_award_id,
                        ),
                    )
                    .outerjoin(
                        PurchaseConsolidationModel,
                        and_(
                            PurchaseConsolidationModel.company_id
                            == PurchaseConsolidationAwardModel.company_id,
                            PurchaseConsolidationModel.id
                            == PurchaseConsolidationAwardModel.consolidation_id,
                        ),
                    )
                    .outerjoin(
                        PurchaseConsolidationSourceModel,
                        and_(
                            PurchaseConsolidationSourceModel.company_id
                            == PurchaseConsolidationAwardModel.company_id,
                            PurchaseConsolidationSourceModel.consolidation_line_id
                            == PurchaseConsolidationAwardModel.consolidation_line_id,
                            PurchaseConsolidationSourceModel.included_quantity > ZERO,
                        ),
                    )
                    .outerjoin(
                        PurchaseRequestModel,
                        and_(
                            PurchaseRequestModel.company_id
                            == PurchaseConsolidationSourceModel.company_id,
                            PurchaseRequestModel.id
                            == PurchaseConsolidationSourceModel.purchase_request_id,
                        ),
                    )
                    .outerjoin(
                        Branch,
                        and_(
                            Branch.company_id == PurchaseRequestModel.company_id,
                            Branch.id == PurchaseRequestModel.branch_id,
                        ),
                    )
                    .where(
                        InventoryMovementLineModel.company_id == company_id,
                        InventoryMovementLineModel.handling_unit_id.in_(trace_unit_ids),
                        InventoryMovementModel.movement_type == "receipt",
                    )
                    .order_by(PurchaseRequestModel.request_date)
                )
            )
            .mappings()
            .all()
        )

        requests: list[dict[str, Any]] = []
        seen_request_ids: set[uuid.UUID] = set()
        for row in purchase_rows:
            request_id = row["request_id"]
            if request_id is not None and request_id not in seen_request_ids:
                seen_request_ids.add(request_id)
                requests.append(
                    {
                        "request_code": row["request_code"],
                        "branch_name": row["branch_name"],
                        "requested_at": row["requested_at"],
                        "required_date": row["required_date"],
                    }
                )

        origin_row = purchase_rows[0] if purchase_rows else None
        unit = self._handling_unit_dict(handling_unit)
        unit.update(
            {
                "receipt_lot_code": unit_row.receipt_lot_code,
                "receipt_lot_header_code": unit_row.receipt_lot_header_code,
                "received_at": unit_row.receipt_received_at,
                "product_sku": unit_row.variant_sku or unit_row.product_sku,
                "product_name": unit_row.variant_name or unit_row.product_name,
                "base_unit_symbol": unit_row.base_unit_symbol,
            }
        )
        return {
            "handling_unit": unit,
            "product_sku": unit_row.variant_sku or unit_row.product_sku,
            "product_name": unit_row.variant_name or unit_row.product_name,
            "base_unit_name": unit_row.base_unit_name,
            "base_unit_symbol": unit_row.base_unit_symbol,
            "warehouse_code": unit_row.warehouse_code,
            "warehouse_name": unit_row.warehouse_name,
            "location_code": unit_row.location_code,
            "origin": {
                "supplier_code": origin_row["supplier_code"] if origin_row else None,
                "supplier_name": origin_row["supplier_name"] if origin_row else None,
                "purchase_code": origin_row["purchase_code"] if origin_row else None,
                "purchase_order_code": origin_row["purchase_order_code"] if origin_row else None,
                "received_at": origin_row["received_at"] if origin_row else None,
                "purchase_date": origin_row["purchase_date"] if origin_row else None,
                "consolidation_code": origin_row["consolidation_code"] if origin_row else None,
                "requests": requests,
            },
            "movements": [dict(row) for row in movement_rows],
        }

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
            InventoryHandlingUnitModel.inventory_posted_at.is_not(None),
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

    async def product_stock_snapshot(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        product_ids: Sequence[int],
    ) -> list[ProductStockSnapshot]:
        """Read current inventory balances without treating capacity holds as stock reservations."""
        product_ids = tuple(
            dict.fromkeys(product_id for product_id in product_ids if product_id > 0)
        )
        if not product_ids:
            return []

        unit_name = func.coalesce(CompanyUnitModel.alias, UnitModel.name)

        def status_total(stock_status: str) -> Any:
            return func.coalesce(
                func.sum(
                    case(
                        (
                            InventoryBalanceModel.stock_status == stock_status,
                            InventoryBalanceModel.quantity_base,
                        ),
                        else_=ZERO,
                    )
                ),
                ZERO,
            )

        rows = (
            await self._session.execute(
                select(
                    ProductModel.id_product,
                    InventoryItemModel.id,
                    InventoryItemModel.base_unit_id,
                    unit_name.label("base_unit_name"),
                    InventoryItemModel.is_active,
                    status_total(StockStatus.AVAILABLE.value).label("available_quantity"),
                    status_total(StockStatus.IN_TRANSIT.value).label("in_transit_quantity"),
                    status_total(StockStatus.QUARANTINE.value).label("quarantine_quantity"),
                    status_total(StockStatus.BLOCKED.value).label("blocked_quantity"),
                    status_total(StockStatus.DAMAGED.value).label("damaged_quantity"),
                )
                .select_from(ProductModel)
                .outerjoin(
                    InventoryItemModel,
                    and_(
                        InventoryItemModel.company_id == company_id,
                        InventoryItemModel.product_id == ProductModel.id_product,
                    ),
                )
                .outerjoin(
                    InventoryBalanceModel,
                    and_(
                        InventoryBalanceModel.company_id == company_id,
                        InventoryBalanceModel.inventory_item_id == InventoryItemModel.id,
                        InventoryBalanceModel.warehouse_id == warehouse_id,
                    ),
                )
                .outerjoin(UnitModel, UnitModel.id_unit == InventoryItemModel.base_unit_id)
                .outerjoin(
                    CompanyUnitModel,
                    and_(
                        CompanyUnitModel.company_id == company_id,
                        CompanyUnitModel.unit_id == InventoryItemModel.base_unit_id,
                    ),
                )
                .where(
                    ProductModel.company_id == company_id,
                    ProductModel.id_product.in_(product_ids),
                )
                .group_by(
                    ProductModel.id_product,
                    InventoryItemModel.id,
                    InventoryItemModel.base_unit_id,
                    CompanyUnitModel.alias,
                    UnitModel.name,
                    InventoryItemModel.is_active,
                )
                .order_by(ProductModel.id_product)
            )
        ).all()
        return [
            ProductStockSnapshot(
                product_id=int(row.id_product),
                inventory_item_id=row.id,
                base_unit_id=row.base_unit_id,
                base_unit_name=row.base_unit_name,
                is_active=row.is_active,
                available_quantity=row.available_quantity or ZERO,
                in_transit_quantity=row.in_transit_quantity or ZERO,
                quarantine_quantity=row.quarantine_quantity or ZERO,
                blocked_quantity=row.blocked_quantity or ZERO,
                damaged_quantity=row.damaged_quantity or ZERO,
            )
            for row in rows
        ]

    async def list_movements(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        limit: int,
        movement_type: str | None = None,
        offset: int = 0,
        period_from: date | None = None,
        period_to: date | None = None,
        query: str | None = None,
        lot_code: str | None = None,
        source_reference: str | None = None,
        direction: str | None = None,
    ) -> list[dict[str, Any]]:
        from_location = aliased(Location)
        to_location = aliased(Location)
        from_warehouse = aliased(Warehouse)
        to_warehouse = aliased(Warehouse)
        filters = _movement_history_filters(
            warehouse_id=warehouse_id,
            period_from=period_from,
            period_to=period_to,
            query=query,
            lot_code=lot_code,
            source_reference=source_reference,
            direction=direction,
        )
        rows = (
            (
                await self._session.execute(
                    select(
                        InventoryMovementLineModel.id.label("id"),
                        InventoryMovementModel.id.label("movement_id"),
                        InventoryMovementLineModel.line_number,
                        InventoryMovementModel.company_id,
                        InventoryMovementModel.movement_type,
                        InventoryMovementModel.source_reference,
                        InventoryMovementModel.posted_at,
                        InventoryMovementModel.posted_by,
                        User.username.label("operator"),
                        InventoryMovementLineModel.inventory_item_id,
                        InventoryItemModel.product_id,
                        InventoryItemModel.variant_id,
                        InventoryItemModel.base_unit_id,
                        UnitModel.name.label("base_unit_name"),
                        UnitModel.symbol.label("base_unit_symbol"),
                        ProductVariantModel.sku.label("variant_sku"),
                        ProductModel.sku.label("product_sku"),
                        ProductVariantModel.name_override.label("variant_name"),
                        ProductModel.name.label("product_name"),
                        InventoryMovementLineModel.handling_unit_id,
                        InventoryHandlingUnitModel.code.label("handling_unit_code"),
                        InventoryMovementLineModel.from_warehouse_id,
                        from_warehouse.code.label("from_warehouse_code"),
                        from_warehouse.name.label("from_warehouse_name"),
                        InventoryMovementLineModel.from_location_id,
                        from_location.code.label("from_location_code"),
                        InventoryMovementLineModel.from_stock_status,
                        InventoryMovementLineModel.to_warehouse_id,
                        to_warehouse.code.label("to_warehouse_code"),
                        to_warehouse.name.label("to_warehouse_name"),
                        InventoryMovementLineModel.to_location_id,
                        to_location.code.label("to_location_code"),
                        InventoryMovementLineModel.to_stock_status,
                        InventoryMovementLineModel.quantity_base,
                        InventoryMovementLineModel.occupied_weight_kg,
                        InventoryMovementLineModel.occupied_volume_m3,
                        InventoryMovementLineModel.measurement_status,
                        InventoryMovementLineModel.lot_code,
                        InventoryLotDetailModel.code.label("receipt_lot_code"),
                        InventoryLotModel.code.label("receipt_lot_header_code"),
                        InventoryMovementLineModel.expiry_date,
                        InventoryMovementLineModel.packaging_snapshot,
                    )
                    .join(
                        InventoryMovementModel,
                        and_(
                            InventoryMovementModel.id == InventoryMovementLineModel.movement_id,
                            InventoryMovementModel.company_id
                            == InventoryMovementLineModel.company_id,
                        ),
                    )
                    .join(
                        InventoryItemModel,
                        and_(
                            InventoryItemModel.id == InventoryMovementLineModel.inventory_item_id,
                            InventoryItemModel.company_id == InventoryMovementLineModel.company_id,
                        ),
                    )
                    .outerjoin(
                        ProductVariantModel,
                        and_(
                            ProductVariantModel.id == InventoryItemModel.variant_id,
                            ProductVariantModel.company_id == InventoryItemModel.company_id,
                        ),
                    )
                    .outerjoin(
                        ProductModel,
                        and_(
                            ProductModel.company_id == InventoryItemModel.company_id,
                            ProductModel.id_product
                            == func.coalesce(
                                InventoryItemModel.product_id,
                                ProductVariantModel.product_id,
                            ),
                        ),
                    )
                    .outerjoin(UnitModel, UnitModel.id_unit == InventoryItemModel.base_unit_id)
                    .outerjoin(User, User.id == InventoryMovementModel.posted_by)
                    .outerjoin(
                        InventoryHandlingUnitModel,
                        and_(
                            InventoryHandlingUnitModel.id
                            == InventoryMovementLineModel.handling_unit_id,
                            InventoryHandlingUnitModel.company_id
                            == InventoryMovementLineModel.company_id,
                        ),
                    )
                    .outerjoin(
                        InventoryLotDetailModel,
                        and_(
                            InventoryLotDetailModel.company_id
                            == InventoryMovementLineModel.company_id,
                            InventoryLotDetailModel.id
                            == func.coalesce(
                                InventoryMovementLineModel.inventory_lot_detail_id,
                                InventoryHandlingUnitModel.inventory_lot_detail_id,
                            ),
                        ),
                    )
                    .outerjoin(
                        InventoryLotModel,
                        and_(
                            InventoryLotModel.company_id == InventoryHandlingUnitModel.company_id,
                            InventoryLotModel.id == InventoryHandlingUnitModel.inventory_lot_id,
                        ),
                    )
                    .outerjoin(
                        from_location,
                        from_location.id == InventoryMovementLineModel.from_location_id,
                    )
                    .outerjoin(
                        from_warehouse,
                        and_(
                            from_warehouse.id == InventoryMovementLineModel.from_warehouse_id,
                            from_warehouse.company_id == InventoryMovementModel.company_id,
                        ),
                    )
                    .outerjoin(
                        to_location,
                        to_location.id == InventoryMovementLineModel.to_location_id,
                    )
                    .outerjoin(
                        to_warehouse,
                        and_(
                            to_warehouse.id == InventoryMovementLineModel.to_warehouse_id,
                            to_warehouse.company_id == InventoryMovementModel.company_id,
                        ),
                    )
                    .where(
                        InventoryMovementModel.company_id == company_id,
                        or_(
                            InventoryMovementLineModel.from_warehouse_id == warehouse_id,
                            InventoryMovementLineModel.to_warehouse_id == warehouse_id,
                        ),
                        *(
                            [InventoryMovementModel.movement_type == movement_type]
                            if movement_type is not None
                            else []
                        ),
                        *filters,
                    )
                    .order_by(
                        InventoryMovementModel.posted_at.desc(),
                        InventoryMovementModel.id.desc(),
                        InventoryMovementLineModel.line_number.desc(),
                    )
                    .limit(limit)
                    .offset(offset)
                )
            )
            .mappings()
            .all()
        )
        handling_unit_ids = {
            row["handling_unit_id"] for row in rows if row["handling_unit_id"] is not None
        }
        purchase_by_handling_unit: dict[uuid.UUID, tuple[str | None, str | None]] = {}
        if handling_unit_ids:
            purchase_rows = (
                (
                    await self._session.execute(
                        select(
                            InventoryMovementLineModel.handling_unit_id,
                            PurchaseModel.code.label("purchase_code"),
                            PurchaseOrderModel.code.label("purchase_order_code"),
                        )
                        .join(
                            InventoryMovementModel,
                            and_(
                                InventoryMovementModel.id == InventoryMovementLineModel.movement_id,
                                InventoryMovementModel.company_id
                                == InventoryMovementLineModel.company_id,
                            ),
                        )
                        .join(
                            PurchaseModel,
                            and_(
                                PurchaseModel.company_id == InventoryMovementModel.company_id,
                                PurchaseModel.inventory_movement_id == InventoryMovementModel.id,
                            ),
                        )
                        .outerjoin(
                            PurchaseOrderModel,
                            and_(
                                PurchaseOrderModel.id == PurchaseModel.purchase_order_id,
                                PurchaseOrderModel.company_id == PurchaseModel.company_id,
                            ),
                        )
                        .where(
                            InventoryMovementModel.company_id == company_id,
                            InventoryMovementModel.movement_type == "receipt",
                            InventoryMovementLineModel.handling_unit_id.in_(handling_unit_ids),
                        )
                        .order_by(InventoryMovementModel.posted_at.desc())
                    )
                )
                .mappings()
                .all()
            )
            for purchase_row in purchase_rows:
                purchase_by_handling_unit.setdefault(
                    purchase_row["handling_unit_id"],
                    (purchase_row["purchase_code"], purchase_row["purchase_order_code"]),
                )

        return [
            {
                "id": row["id"],
                "movement_id": row["movement_id"],
                "line_number": row["line_number"],
                "company_id": row["company_id"],
                "movement_type": row["movement_type"],
                "source_reference": row["source_reference"],
                "purchase_code": purchase_by_handling_unit.get(
                    row["handling_unit_id"], (None, None)
                )[0],
                "purchase_order_code": purchase_by_handling_unit.get(
                    row["handling_unit_id"], (None, None)
                )[1],
                "posted_at": row["posted_at"],
                "posted_by": row["posted_by"],
                "operator": row["operator"],
                "inventory_item_id": row["inventory_item_id"],
                "product_id": row["product_id"],
                "variant_id": row["variant_id"],
                "base_unit_id": row["base_unit_id"],
                "base_unit_name": row["base_unit_name"],
                "base_unit_symbol": row["base_unit_symbol"],
                "product_sku": row["variant_sku"] or row["product_sku"],
                "product_name": row["variant_name"] or row["product_name"],
                "handling_unit_id": row["handling_unit_id"],
                "handling_unit_code": row["handling_unit_code"],
                "from_warehouse_id": row["from_warehouse_id"],
                "from_warehouse_code": row["from_warehouse_code"],
                "from_warehouse_name": row["from_warehouse_name"],
                "from_location_id": row["from_location_id"],
                "from_location_code": row["from_location_code"],
                "from_stock_status": row["from_stock_status"],
                "to_warehouse_id": row["to_warehouse_id"],
                "to_warehouse_code": row["to_warehouse_code"],
                "to_warehouse_name": row["to_warehouse_name"],
                "to_location_id": row["to_location_id"],
                "to_location_code": row["to_location_code"],
                "to_stock_status": row["to_stock_status"],
                "quantity_base": row["quantity_base"],
                "occupied_weight_kg": (
                    row["occupied_weight_kg"] if row["measurement_status"] != "incomplete" else None
                ),
                "occupied_volume_m3": (
                    row["occupied_volume_m3"] if row["measurement_status"] != "incomplete" else None
                ),
                "measurement_status": row["measurement_status"],
                "lot_code": row["lot_code"],
                "receipt_lot_code": row["receipt_lot_code"],
                "receipt_lot_header_code": row["receipt_lot_header_code"],
                "expiry_date": row["expiry_date"],
                "packaging_snapshot": row["packaging_snapshot"],
            }
            for row in rows
        ]

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
                # Adding optional financial fields must not invalidate retries
                # of physical commands posted before valuation was introduced.
                "lines": [
                    {
                        key: value
                        for key, value in line.items()
                        if not (key.startswith("valuation_") and value is None)
                    }
                    for line in lines
                ],
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
        receipt_placement: bool = False,
    ) -> dict[str, Any]:
        from app.infrastructure.repositories.inventory_valuation_repository import (
            SqlAlchemyInventoryValuationRepository,
        )

        valuation = SqlAlchemyInventoryValuationRepository(self._session)
        # Includes companies awaiting their opening balance: receiving and
        # cutover must never observe different physical snapshots.
        await valuation.lock(company_id)
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

        handling_units_by_id: dict[uuid.UUID, InventoryHandlingUnitModel] = {}
        handling_unit_ids = sorted(
            {
                line["handling_unit_id"]
                for line in lines
                if line.get("handling_unit_id") is not None
            },
            key=str,
        )
        for handling_unit_id in handling_unit_ids:
            row = await self._session.scalar(
                select(InventoryHandlingUnitModel)
                .where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.id == handling_unit_id,
                )
                .with_for_update()
            )
            if row is not None:
                handling_units_by_id[handling_unit_id] = row

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
            source_handling_unit: InventoryHandlingUnitModel | None = None
            is_partial_split = False
            is_partial_adjustment_out = False
            unmeasured_transfer_receipt = False
            physical: _ResolvedPhysical | None = None
            packaging_snapshot: dict[str, Any] | None = None
            lot_code = data.get("lot_code")
            expiry_date = data.get("expiry_date")
            line_override_id = data.get("capacity_override_id") or (
                reservation.operational_override_id if reservation is not None else None
            )

            handling_unit_id = data.get("handling_unit_id")
            pending_receipt_unit: InventoryHandlingUnitModel | None = None
            if handling_unit_id is not None:
                handling_unit = handling_units_by_id.get(handling_unit_id)
                if handling_unit is None or handling_unit.closed_at is not None:
                    raise InventoryOperationError(
                        "Unidad logística no encontrada o cerrada.",
                        code="handling_unit_not_available",
                        status_code=404,
                    )
                if getattr(handling_unit, "inventory_posted_at", True) is None:
                    if (
                        not receipt_placement
                        or movement_type != "receipt"
                        or from_location_id is not None
                        or from_status is not None
                        or handling_unit.inventory_item_id != item_id
                        or quantity != handling_unit.quantity_base
                    ):
                        raise InventoryOperationError(
                            "La unidad está en preparación; confirme su ingreso desde la cola de ubicación.",
                            code="handling_unit_entry_pending",
                            status_code=409,
                        )
                    pending_receipt_unit = handling_unit
                    handling_unit = None
            if handling_unit is not None:
                source_handling_unit = handling_unit
                if (
                    handling_unit.inventory_item_id != item_id
                    or handling_unit.location_id != from_location_id
                    or quantity > handling_unit.quantity_base
                    or handling_unit.stock_status != from_status
                ):
                    raise InventoryOperationError(
                        "La unidad logística no coincide con el origen del movimiento.",
                        code="handling_unit_mismatch",
                        status_code=409,
                    )
                lot_code = handling_unit.lot_code
                expiry_date = handling_unit.expiry_date
                packaging_snapshot = handling_unit.packaging_snapshot
                is_partial_split = quantity < handling_unit.quantity_base
                is_partial_adjustment_out = (
                    is_partial_split
                    and movement_type == "adjustment_out"
                    and to_location_id is None
                    and to_status is None
                )
                if (
                    is_partial_split
                    and not is_partial_adjustment_out
                    and handling_unit.inventory_lot_id is not None
                ):
                    label_confirmation_required = await self._session.scalar(
                        select(InventoryLotModel.label_confirmation_required).where(
                            InventoryLotModel.company_id == company_id,
                            InventoryLotModel.id == handling_unit.inventory_lot_id,
                        )
                    )
                    _require_labelled_split_in_quarantine(
                        label_confirmation_required=bool(label_confirmation_required),
                        from_status=from_status,
                        movement_type=movement_type,
                        to_status=to_status,
                    )
                unmeasured_transfer_receipt = (
                    from_status == StockStatus.IN_TRANSIT.value
                    and to_status == StockStatus.QUARANTINE.value
                    and (
                        is_partial_split
                        or handling_unit.measurement_source
                        == MeasurementSource.SPLIT_ESTIMATE.value
                    )
                )
                if is_partial_split:
                    quarantine_putaway_split = (
                        movement_type == "putaway"
                        and from_status == StockStatus.QUARANTINE.value
                        and to_status == StockStatus.QUARANTINE.value
                    )
                    if is_partial_adjustment_out:
                        pass
                    elif (movement_type != "transfer" and not quarantine_putaway_split) or (
                        to_location_id is None
                    ):
                        raise InventoryOperationError(
                            "Solo un traslado o una ubicación en cuarentena puede fraccionar una unidad logística.",
                            code="partial_handling_unit_transfer_only",
                        )
                    if quarantine_putaway_split:
                        if to_location_id is None:
                            raise InventoryOperationError(
                                "El destino es obligatorio.",
                                code="putaway_split_warehouse_mismatch",
                                status_code=409,
                            )
                        destination_context = contexts[to_location_id]
                        if destination_context.warehouse.id != handling_unit.warehouse_id:
                            raise InventoryOperationError(
                                "Una ubicación agrupada debe permanecer dentro de la misma bodega.",
                                code="putaway_split_warehouse_mismatch",
                                status_code=409,
                            )
                        if not destination_context.location.storage_eligible:
                            raise InventoryOperationError(
                                "El destino no está habilitado para almacenar esta unidad.",
                                code="location_not_storage_eligible",
                                status_code=409,
                            )
                    if handling_unit.measurement_status == MeasurementStatus.INCOMPLETE.value:
                        raise InventoryOperationError(
                            "Verifique las medidas físicas antes de fraccionar esta unidad.",
                            code="handling_unit_measurements_required",
                        )
                    source_quantity = handling_unit.quantity_base
                    source_weight = handling_unit.occupied_weight_kg
                    source_volume = handling_unit.occupied_volume_m3
                    weight = (source_weight * quantity / source_quantity).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    )
                    volume = (source_volume * quantity / source_quantity).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    )
                    if weight <= ZERO or volume <= ZERO:
                        raise InventoryOperationError(
                            "La cantidad es demasiado pequeña para conservar sus medidas físicas.",
                            code="partial_handling_unit_precision",
                        )
                    if (
                        handling_unit.measurement_source == MeasurementSource.SPLIT_ESTIMATE.value
                        and to_status == StockStatus.AVAILABLE.value
                    ):
                        raise InventoryOperationError(
                            "La sucursal debe verificar las medidas del fraccionamiento antes de liberar el inventario.",
                            code="split_estimate_requires_verification",
                            status_code=409,
                        )
                    split_snapshot = dict(handling_unit.packaging_snapshot or {})
                    for physical_key in (
                        "gross_weight_kg",
                        "length_m",
                        "width_m",
                        "height_m",
                        "volume_m3",
                    ):
                        split_snapshot.pop(physical_key, None)
                    packaging_snapshot = split_snapshot or None
                    physical = _ResolvedPhysical(
                        packaging=None,
                        measures=PhysicalMeasures(
                            gross_weight_kg=weight,
                            length_m=None,
                            width_m=None,
                            height_m=None,
                            volume_m3=volume,
                        ),
                        consumption=Consumption(weight_kg=weight, volume_m3=volume),
                        snapshot=packaging_snapshot,
                        source=MeasurementSource.SPLIT_ESTIMATE,
                    )
                else:
                    weight = handling_unit.occupied_weight_kg
                    volume = handling_unit.occupied_volume_m3
                    physical = _physical_from_handling_unit(handling_unit)
                    if (
                        handling_unit.measurement_source == MeasurementSource.SPLIT_ESTIMATE.value
                        and to_status == StockStatus.AVAILABLE.value
                    ):
                        raise InventoryOperationError(
                            "La sucursal debe verificar las medidas del fraccionamiento antes de liberar el inventario.",
                            code="split_estimate_requires_verification",
                            status_code=409,
                        )
                if (
                    from_status == StockStatus.QUARANTINE.value
                    and to_status == StockStatus.AVAILABLE.value
                ):
                    if movement_type not in {"putaway", "transfer"}:
                        raise InventoryOperationError(
                            "La liberación de cuarentena debe registrarse como movimiento de bodega.",
                            code="quarantine_release_requires_putaway",
                        )
                    label_confirmation_required = False
                    label_confirmed = False
                    receipt_lot = None
                    if handling_unit.inventory_lot_id is not None:
                        receipt_lot = await self._session.scalar(
                            select(InventoryLotModel).where(
                                InventoryLotModel.company_id == company_id,
                                InventoryLotModel.id == handling_unit.inventory_lot_id,
                            )
                        )
                        label_confirmation_required = bool(
                            receipt_lot and receipt_lot.label_confirmation_required
                        )
                        if label_confirmation_required:
                            label_confirmed_id = await self._session.scalar(
                                select(InventoryLabelConfirmationModel.id).where(
                                    InventoryLabelConfirmationModel.company_id == company_id,
                                    InventoryLabelConfirmationModel.handling_unit_id
                                    == handling_unit.id,
                                    InventoryLabelConfirmationModel.handling_unit_code
                                    == handling_unit.code,
                                    InventoryLabelConfirmationModel.label_revision
                                    == handling_unit.label_revision,
                                    InventoryLabelConfirmationModel.quantity_base
                                    == handling_unit.quantity_base,
                                )
                            )
                            label_confirmed = label_confirmed_id is not None
                    readiness_error = None
                    if receipt_lot is not None:
                        readiness_error = await purchase_retaceo_readiness_error(
                            self._session,
                            company_id=company_id,
                            purchase_id=receipt_lot.purchase_id,
                            received_at=receipt_lot.received_at,
                        )
                    today = datetime.now(UTC).astimezone(ZoneInfo("America/El_Salvador")).date()
                    requirements = handling_unit_release_requirements(
                        is_partial=False,
                        measurement_status=handling_unit.measurement_status,
                        measurement_source=handling_unit.measurement_source,
                        expiry_date=expiry_date,
                        today=today,
                        label_confirmation_required=label_confirmation_required,
                        label_confirmed=label_confirmed,
                        retaceo_readiness_error=readiness_error,
                    )
                    if requirements:
                        requirement = requirements[0]
                        errors = {
                            ReleaseRequirement.MEASUREMENT: (
                                "Verifique las medidas físicas antes de liberar esta unidad.",
                                "quarantine_release_measurements_required",
                            ),
                            ReleaseRequirement.EXPIRY: (
                                "Un lote vencido no puede liberarse como disponible.",
                                "expired_lot_requires_quarantine",
                            ),
                            ReleaseRequirement.LABEL: (
                                "Confirme la etiqueta colocada en esta unidad antes de liberarla.",
                                "handling_unit_label_confirmation_required",
                            ),
                            ReleaseRequirement.RETACEO: (
                                "Verifique y cierre el retaceo exigible antes de liberar esta unidad.",
                                "inventory_label_retaceo_not_final",
                            ),
                            ReleaseRequirement.RETACEO_COST: (
                                "Aplique el retaceo verificado al costo del inventario antes de liberar.",
                                "inventory_label_retaceo_cost_unapplied",
                            ),
                        }
                        message, code = errors[requirement]
                        raise InventoryOperationError(message, code=code, status_code=409)
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
                    and expiry_date
                    < datetime.now(UTC).astimezone(ZoneInfo("America/El_Salvador")).date()
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
                if (
                    source_handling_unit is not None
                    and source.warehouse.id != source_handling_unit.warehouse_id
                ):
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
                destination_weight = ZERO if unmeasured_transfer_receipt else weight
                destination_volume = ZERO if unmeasured_transfer_receipt else volume
                await self._change_balance(
                    company_id=company_id,
                    warehouse_id=destination.warehouse.id,
                    location_id=to_location_id,
                    item_id=item_id,
                    stock_status=to_status,
                    lot_code=lot_code,
                    expiry_date=expiry_date,
                    quantity=quantity,
                    weight=destination_weight,
                    volume=destination_volume,
                )

            if is_partial_split:
                assert source_handling_unit is not None
                remaining_quantity = source_handling_unit.quantity_base - quantity
                remaining_weight = source_handling_unit.occupied_weight_kg - weight
                remaining_volume = source_handling_unit.occupied_volume_m3 - volume
                if (
                    remaining_quantity <= ZERO
                    or remaining_weight <= ZERO
                    or remaining_volume <= ZERO
                ):
                    raise InventoryOperationError(
                        "El fraccionamiento dejaría un remanente físico inválido.",
                        code="partial_handling_unit_precision",
                    )
                source_handling_unit.quantity_base = remaining_quantity
                source_handling_unit.label_revision += 1
                source_handling_unit.occupied_weight_kg = remaining_weight
                source_handling_unit.occupied_volume_m3 = remaining_volume
                source_handling_unit.actual_gross_weight_kg = None
                source_handling_unit.actual_length_m = None
                source_handling_unit.actual_width_m = None
                source_handling_unit.actual_height_m = None
                source_handling_unit.actual_volume_m3 = None
                source_handling_unit.packaging_snapshot = packaging_snapshot
                source_handling_unit.measurement_status = MeasurementStatus.COMPLETE.value
                source_handling_unit.measurement_source = MeasurementSource.SPLIT_ESTIMATE.value
                if is_partial_adjustment_out:
                    # A documented partial loss changes the quantity represented by
                    # this same physical unit. Keep its identity, invalidate the old
                    # label revision, and require the normal label review before use.
                    handling_unit = source_handling_unit
                else:
                    assert to_location_id is not None
                    assert to_status is not None
                    destination = contexts[to_location_id]
                    handling_unit = InventoryHandlingUnitModel(
                        company_id=company_id,
                        warehouse_id=destination.warehouse.id,
                        location_id=to_location_id,
                        inventory_item_id=item_id,
                        inventory_lot_id=source_handling_unit.inventory_lot_id,
                        inventory_lot_detail_id=source_handling_unit.inventory_lot_detail_id,
                        packaging_definition_id=source_handling_unit.packaging_definition_id,
                        origin_handling_unit_id=source_handling_unit.id,
                        code=f"HU-{uuid.uuid4().hex[:16].upper()}",
                        lot_code=lot_code,
                        expiry_date=expiry_date,
                        quantity_base=quantity,
                        packaging_snapshot=packaging_snapshot,
                        actual_gross_weight_kg=None,
                        actual_length_m=None,
                        actual_width_m=None,
                        actual_height_m=None,
                        actual_volume_m3=None,
                        occupied_weight_kg=(ZERO if unmeasured_transfer_receipt else weight),
                        occupied_volume_m3=(ZERO if unmeasured_transfer_receipt else volume),
                        stock_status=to_status,
                        measurement_status=(
                            MeasurementStatus.INCOMPLETE.value
                            if unmeasured_transfer_receipt
                            else MeasurementStatus.COMPLETE.value
                        ),
                        measurement_source=MeasurementSource.SPLIT_ESTIMATE.value,
                    )
                    self._session.add(handling_unit)
                    await self._session.flush()
            elif handling_unit is None:
                assert to_location_id is not None
                assert physical is not None
                assert to_status is not None
                destination = contexts[to_location_id]
                handling_unit = pending_receipt_unit or InventoryHandlingUnitModel(
                    company_id=company_id,
                    warehouse_id=destination.warehouse.id,
                    location_id=to_location_id,
                    inventory_item_id=item_id,
                    inventory_lot_id=data.get("inventory_lot_id"),
                    inventory_lot_detail_id=data.get("inventory_lot_detail_id"),
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
                if pending_receipt_unit is not None:
                    handling_unit.warehouse_id = destination.warehouse.id
                    handling_unit.location_id = to_location_id
                    handling_unit.stock_status = to_status
                    handling_unit.inventory_posted_at = now
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
                if unmeasured_transfer_receipt:
                    handling_unit.occupied_weight_kg = ZERO
                    handling_unit.occupied_volume_m3 = ZERO
                    handling_unit.measurement_status = MeasurementStatus.INCOMPLETE.value

            movement_line = InventoryMovementLineModel(
                company_id=company_id,
                movement_id=movement.id,
                line_number=line_number,
                inventory_item_id=item_id,
                handling_unit_id=handling_unit.id,
                inventory_lot_detail_id=handling_unit.inventory_lot_detail_id,
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
                occupied_weight_kg=(ZERO if unmeasured_transfer_receipt else weight),
                occupied_volume_m3=(ZERO if unmeasured_transfer_receipt else volume),
                measurement_status=handling_unit.measurement_status,
                packaging_snapshot=packaging_snapshot,
            )
            self._session.add(movement_line)
            await self._session.flush()
            await valuation.post_physical_line(
                movement_line,
                data,
                movement_type=movement_type,
                reference=source_reference,
                actor_id=actor_id,
            )

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
            InventoryHandlingUnitModel.inventory_posted_at.is_not(None),
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
                select(Warehouse, Warehouse.company_id).where(
                    Warehouse.id == warehouse_id, Warehouse.company_id == company_id
                )
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
