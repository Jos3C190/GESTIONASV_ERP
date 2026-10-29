"""Transactional physical fulfilment for confirmed sales."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.application.audit.audit_service import AuditService
from app.application.inventory import InventoryUseCases
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError, ValidationError
from app.domain.entities.inventory import InventoryOperationError
from app.infrastructure.models.inventory import (
    InventoryHandlingUnitModel,
    InventoryMovementLineModel,
    InventoryMovementModel,
)
from app.infrastructure.models.inventory_label_confirmation import (
    InventoryLabelConfirmationModel,
)
from app.infrastructure.models.inventory_lot import InventoryLotModel
from app.infrastructure.models.inventory_valuation import (
    InventoryValuationEntryModel,
    InventoryValuationSettingModel,
)
from app.infrastructure.models.organization import Location, Warehouse
from app.infrastructure.models.sales import SaleLineModel, SaleModel
from app.infrastructure.models.sales_delivery import (
    SalesDeliveryAllocationModel,
    SalesDeliveryCommandModel,
    SalesDeliveryLineModel,
    SalesDeliveryModel,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

ZERO = Decimal("0")
QTY_QUANTUM = Decimal("0.000001")
SV_TZ = ZoneInfo("America/El_Salvador")


def _today() -> date:
    return datetime.now(SV_TZ).date()


def _fingerprint(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SalesDeliveryService:
    """Coordinates delivery documents with the canonical inventory engine."""

    def __init__(
        self, session: AsyncSession, audit: AuditService, inventory: InventoryUseCases
    ) -> None:
        self.session = session
        self.audit = audit
        self.inventory = inventory

    async def _audit(
        self,
        *,
        action: str,
        actor_id: uuid.UUID,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        delivery_id: uuid.UUID,
        request: Any,
        before: dict[str, object] | None = None,
        after: dict[str, object] | None = None,
    ) -> None:
        await self.audit.record(
            action=action,
            user_id=actor_id,
            company_id=company_id,
            branch_id=branch_id,
            resource_type="sales_delivery",
            resource_id=str(delivery_id),
            before_state=before,
            after_state=after,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            required=True,
        )

    async def _lock_key(self, company_id: uuid.UUID, action: str, key: str) -> None:
        lock = f"sales-delivery:{company_id}:{action}:{key}"
        await self.session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(lock, 0)))
        )

    async def _sale(
        self, company_id: uuid.UUID, sale_id: uuid.UUID, *, lock: bool = False
    ) -> SaleModel:
        statement = select(SaleModel).where(
            SaleModel.company_id == company_id, SaleModel.id == sale_id
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        row = await self.session.scalar(statement)
        if row is None:
            raise NotFoundError("Venta no encontrada.", code="sales_sale_not_found")
        return row

    async def _delivery(
        self, company_id: uuid.UUID, delivery_id: uuid.UUID, *, lock: bool = False
    ) -> SalesDeliveryModel:
        statement = select(SalesDeliveryModel).where(
            SalesDeliveryModel.company_id == company_id,
            SalesDeliveryModel.id == delivery_id,
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        row = await self.session.scalar(statement)
        if row is None:
            raise NotFoundError("Entrega no encontrada.", code="sales_delivery_not_found")
        return row

    async def delivery_header(
        self, company_id: uuid.UUID, delivery_id: uuid.UUID
    ) -> SalesDeliveryModel:
        return await self._delivery(company_id, delivery_id)

    async def _sale_lines(self, company_id: uuid.UUID, sale_id: uuid.UUID) -> list[SaleLineModel]:
        return list(
            (
                await self.session.scalars(
                    select(SaleLineModel)
                    .where(
                        SaleLineModel.company_id == company_id,
                        SaleLineModel.sale_id == sale_id,
                    )
                    .order_by(SaleLineModel.line_number)
                )
            ).all()
        )

    async def _delivered_by_line(
        self, company_id: uuid.UUID, sale_id: uuid.UUID
    ) -> dict[uuid.UUID, Decimal]:
        rows = (
            await self.session.execute(
                select(
                    SalesDeliveryLineModel.sale_line_id,
                    func.sum(SalesDeliveryLineModel.quantity_base),
                )
                .join(
                    SalesDeliveryModel,
                    (SalesDeliveryModel.company_id == SalesDeliveryLineModel.company_id)
                    & (SalesDeliveryModel.id == SalesDeliveryLineModel.delivery_id),
                )
                .where(
                    SalesDeliveryModel.company_id == company_id,
                    SalesDeliveryModel.sale_id == sale_id,
                    SalesDeliveryModel.status == "confirmed",
                )
                .group_by(SalesDeliveryLineModel.sale_line_id)
            )
        ).all()
        return {row[0]: Decimal(row[1] or ZERO) for row in rows}

    async def _label_is_current(self, unit: InventoryHandlingUnitModel) -> bool:
        if unit.inventory_lot_id is None:
            return True
        required = await self.session.scalar(
            select(InventoryLotModel.label_confirmation_required).where(
                InventoryLotModel.company_id == unit.company_id,
                InventoryLotModel.id == unit.inventory_lot_id,
            )
        )
        if not required:
            return True
        confirmation = await self.session.scalar(
            select(InventoryLabelConfirmationModel.id).where(
                InventoryLabelConfirmationModel.company_id == unit.company_id,
                InventoryLabelConfirmationModel.handling_unit_id == unit.id,
                InventoryLabelConfirmationModel.handling_unit_code == unit.code,
                InventoryLabelConfirmationModel.label_revision == unit.label_revision,
                InventoryLabelConfirmationModel.quantity_base == unit.quantity_base,
            )
        )
        return confirmation is not None

    async def _available_unit(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        inventory_item_id: uuid.UUID,
        handling_unit_id: uuid.UUID,
        expected_warehouse_id: uuid.UUID | None = None,
        expected_location_id: uuid.UUID | None = None,
        expected_quantity: Decimal | None = None,
        expected_lot_detail_id: uuid.UUID | None = None,
        validate_expected_lot_detail: bool = False,
    ) -> tuple[InventoryHandlingUnitModel, Warehouse, Location]:
        row = (
            await self.session.execute(
                select(InventoryHandlingUnitModel, Warehouse, Location)
                .join(
                    Warehouse,
                    (Warehouse.id == InventoryHandlingUnitModel.warehouse_id)
                    & (Warehouse.company_id == InventoryHandlingUnitModel.company_id),
                )
                .join(
                    Location,
                    (Location.id == InventoryHandlingUnitModel.location_id)
                    & (Location.warehouse_id == InventoryHandlingUnitModel.warehouse_id),
                )
                .where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.id == handling_unit_id,
                    InventoryHandlingUnitModel.inventory_item_id == inventory_item_id,
                    InventoryHandlingUnitModel.closed_at.is_(None),
                    InventoryHandlingUnitModel.stock_status == "available",
                    Warehouse.branch_id == branch_id,
                    Warehouse.is_active.is_(True),
                    Warehouse.is_transit.is_(False),
                    Warehouse.operational_status == "active",
                    Warehouse.deleted_at.is_(None),
                    Location.is_active.is_(True),
                    Location.lifecycle_status == "active",
                    Location.storage_eligible.is_(True),
                    Location.deleted_at.is_(None),
                    Location.location_type != "virtual",
                    (
                        InventoryHandlingUnitModel.expiry_date.is_(None)
                        | (InventoryHandlingUnitModel.expiry_date >= _today())
                    ),
                )
            )
        ).first()
        if row is None:
            raise ConflictError(
                "La unidad seleccionada ya no está disponible en una ubicación de esta sucursal. Recargue las existencias.",
                code="sales_delivery_unit_unavailable",
            )
        unit, warehouse, location = row
        if (expected_warehouse_id is not None and unit.warehouse_id != expected_warehouse_id) or (
            expected_location_id is not None and unit.location_id != expected_location_id
        ):
            raise ConflictError(
                "La ubicación de la unidad cambió desde la preparación. Revise el borrador.",
                code="sales_delivery_unit_location_changed",
            )
        if expected_quantity is not None and unit.quantity_base != expected_quantity:
            raise ConflictError(
                "La cantidad de la unidad cambió desde la preparación. Revise el borrador.",
                code="sales_delivery_unit_quantity_changed",
            )
        if validate_expected_lot_detail and unit.inventory_lot_detail_id != expected_lot_detail_id:
            raise ConflictError(
                "El lote de la unidad cambió desde la preparación. Revise el borrador.",
                code="sales_delivery_unit_lot_changed",
            )
        if not await self._label_is_current(unit):
            raise ConflictError(
                "La etiqueta vigente de la unidad no está confirmada. Revise la etiqueta antes de entregar.",
                code="sales_delivery_label_not_confirmed",
            )
        return unit, warehouse, location

    async def stock_options(
        self, company_id: uuid.UUID, sale_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        sale = await self._sale(company_id, sale_id)
        if sale.status != "confirmed":
            raise BusinessRuleError(
                "Solo una venta confirmada puede preparar entregas.",
                code="sales_delivery_sale_not_confirmed",
            )
        lines = await self._sale_lines(company_id, sale_id)
        delivered = await self._delivered_by_line(company_id, sale_id)
        options: list[dict[str, Any]] = []
        for line in lines:
            pending = max(ZERO, Decimal(line.quantity_base) - delivered.get(line.id, ZERO))
            if pending <= ZERO:
                continue
            candidates = list(
                (
                    await self.session.execute(
                        select(InventoryHandlingUnitModel, Warehouse, Location)
                        .join(
                            Warehouse,
                            (Warehouse.id == InventoryHandlingUnitModel.warehouse_id)
                            & (Warehouse.company_id == InventoryHandlingUnitModel.company_id),
                        )
                        .join(
                            Location,
                            (Location.id == InventoryHandlingUnitModel.location_id)
                            & (Location.warehouse_id == InventoryHandlingUnitModel.warehouse_id),
                        )
                        .where(
                            InventoryHandlingUnitModel.company_id == company_id,
                            InventoryHandlingUnitModel.inventory_item_id == line.inventory_item_id,
                            InventoryHandlingUnitModel.stock_status == "available",
                            InventoryHandlingUnitModel.closed_at.is_(None),
                            Warehouse.branch_id == sale.branch_id,
                            Warehouse.is_active.is_(True),
                            Warehouse.is_transit.is_(False),
                            Warehouse.operational_status == "active",
                            Warehouse.deleted_at.is_(None),
                            Location.is_active.is_(True),
                            Location.lifecycle_status == "active",
                            Location.storage_eligible.is_(True),
                            Location.deleted_at.is_(None),
                            Location.location_type != "virtual",
                            InventoryHandlingUnitModel.expiry_date.is_(None)
                            | (InventoryHandlingUnitModel.expiry_date >= _today()),
                        )
                        .order_by(
                            InventoryHandlingUnitModel.expiry_date.asc().nulls_last(),
                            InventoryHandlingUnitModel.created_at,
                            InventoryHandlingUnitModel.id,
                        )
                        .limit(500)
                    )
                ).all()
            )
            units: list[dict[str, Any]] = []
            for unit, warehouse, location in candidates:
                if not await self._label_is_current(unit):
                    continue
                units.append(
                    {
                        "handling_unit_id": unit.id,
                        "code": unit.code,
                        "inventory_item_id": line.inventory_item_id,
                        "quantity_base": unit.quantity_base,
                        "base_unit_name": line.base_unit_name,
                        "lot_code": unit.lot_code,
                        "expiry_date": unit.expiry_date,
                        "warehouse_id": warehouse.id,
                        "warehouse_name": warehouse.name,
                        "location_id": location.id,
                        "location_code": location.code,
                        "packaging_snapshot": unit.packaging_snapshot,
                    }
                )
            options.append(
                {
                    "sale_line_id": line.id,
                    "product_sku": line.product_sku,
                    "product_name": line.product_name,
                    "unit_name": line.unit_name,
                    "base_unit_name": line.base_unit_name,
                    "quantity_pending_base": pending,
                    "units": units,
                }
            )
        return options

    @staticmethod
    def _assignments_fingerprint(
        sale_id: uuid.UUID, assignments: list[dict[str, Any]], notes: str | None
    ) -> str:
        normalized = sorted(
            (
                {
                    "sale_line_id": str(item["sale_line_id"]),
                    "handling_unit_id": str(item["handling_unit_id"]),
                }
                for item in assignments
            ),
            key=lambda item: (item["sale_line_id"], item["handling_unit_id"]),
        )
        return _fingerprint({"sale_id": str(sale_id), "assignments": normalized, "notes": notes})

    async def _validated_assignment_groups(
        self, sale: SaleModel, assignments: list[dict[str, Any]]
    ) -> tuple[
        dict[uuid.UUID, SaleLineModel],
        dict[uuid.UUID, list[tuple[InventoryHandlingUnitModel, Warehouse, Location]]],
    ]:
        if not assignments:
            raise ValidationError(
                "Seleccione al menos una unidad logística completa.",
                code="sales_delivery_assignments_required",
            )
        unit_ids = [uuid.UUID(str(item["handling_unit_id"])) for item in assignments]
        if len(set(unit_ids)) != len(unit_ids):
            raise ValidationError(
                "Cada unidad logística solo puede asignarse una vez por entrega.",
                code="sales_delivery_duplicate_unit",
            )
        line_ids = [uuid.UUID(str(item["sale_line_id"])) for item in assignments]
        sale_lines = await self._sale_lines(sale.company_id, sale.id)
        by_id = {line.id: line for line in sale_lines}
        if not set(line_ids).issubset(by_id):
            raise ValidationError(
                "Una asignación no pertenece a una línea de esta venta.",
                code="sales_delivery_line_mismatch",
            )
        delivered = await self._delivered_by_line(sale.company_id, sale.id)
        grouped: dict[uuid.UUID, list[tuple[InventoryHandlingUnitModel, Warehouse, Location]]] = {}
        for item in assignments:
            sale_line_id = uuid.UUID(str(item["sale_line_id"]))
            line = by_id[sale_line_id]
            unit, warehouse, location = await self._available_unit(
                company_id=sale.company_id,
                branch_id=sale.branch_id,
                inventory_item_id=line.inventory_item_id,
                handling_unit_id=uuid.UUID(str(item["handling_unit_id"])),
            )
            grouped.setdefault(sale_line_id, []).append((unit, warehouse, location))
        self._ensure_assignments_within_pending(by_id, grouped, delivered)
        return by_id, grouped

    @staticmethod
    def _ensure_assignments_within_pending(
        by_id: dict[uuid.UUID, SaleLineModel],
        grouped: dict[uuid.UUID, list[tuple[InventoryHandlingUnitModel, Warehouse, Location]]],
        delivered: dict[uuid.UUID, Decimal],
    ) -> None:
        for sale_line_id, units in grouped.items():
            line = by_id[sale_line_id]
            requested = sum((Decimal(unit.quantity_base) for unit, _, _ in units), ZERO)
            pending = Decimal(line.quantity_base) - delivered.get(line.id, ZERO)
            if requested > pending:
                raise ConflictError(
                    f"Las unidades seleccionadas para {line.product_name} exceden el pendiente de {pending} {line.base_unit_name}.",
                    code="sales_delivery_exceeds_pending",
                )

    async def _clear_draft_lines(self, delivery: SalesDeliveryModel) -> None:
        old_lines = list(
            (
                await self.session.scalars(
                    select(SalesDeliveryLineModel).where(
                        SalesDeliveryLineModel.company_id == delivery.company_id,
                        SalesDeliveryLineModel.delivery_id == delivery.id,
                    )
                )
            ).all()
        )
        for old_line in old_lines:
            allocations = list(
                (
                    await self.session.scalars(
                        select(SalesDeliveryAllocationModel).where(
                            SalesDeliveryAllocationModel.company_id == delivery.company_id,
                            SalesDeliveryAllocationModel.delivery_line_id == old_line.id,
                        )
                    )
                ).all()
            )
            for allocation in allocations:
                await self.session.delete(allocation)
            await self.session.delete(old_line)
        if old_lines:
            await self.session.flush()

    async def _persist_draft_lines(
        self,
        sale: SaleModel,
        delivery: SalesDeliveryModel,
        by_id: dict[uuid.UUID, SaleLineModel],
        grouped: dict[uuid.UUID, list[tuple[InventoryHandlingUnitModel, Warehouse, Location]]],
    ) -> None:
        ordered_ids = sorted(grouped, key=lambda line_id: by_id[line_id].line_number)
        delivery_lines: dict[uuid.UUID, SalesDeliveryLineModel] = {}
        for number, sale_line_id in enumerate(ordered_ids, start=1):
            line = by_id[sale_line_id]
            units = grouped[sale_line_id]
            delivery_line = SalesDeliveryLineModel(
                company_id=sale.company_id,
                delivery_id=delivery.id,
                sale_id=sale.id,
                sale_line_id=line.id,
                inventory_item_id=line.inventory_item_id,
                line_number=number,
                quantity_base=sum((Decimal(unit.quantity_base) for unit, _, _ in units), ZERO),
                unit_factor=line.unit_factor,
                product_sku=line.product_sku,
                product_name=line.product_name,
                unit_name=line.unit_name,
                base_unit_name=line.base_unit_name,
            )
            self.session.add(delivery_line)
            delivery_lines[sale_line_id] = delivery_line
        await self.session.flush()
        for sale_line_id, units in grouped.items():
            for unit, warehouse, location in units:
                self.session.add(
                    SalesDeliveryAllocationModel(
                        company_id=sale.company_id,
                        delivery_line_id=delivery_lines[sale_line_id].id,
                        inventory_item_id=unit.inventory_item_id,
                        handling_unit_id=unit.id,
                        warehouse_id=warehouse.id,
                        location_id=location.id,
                        inventory_lot_detail_id=unit.inventory_lot_detail_id,
                        lot_code=unit.lot_code,
                        expiry_date=unit.expiry_date,
                        quantity_base=unit.quantity_base,
                        packaging_snapshot=unit.packaging_snapshot,
                    )
                )
        await self.session.flush()

    async def _replace_draft_lines(
        self,
        *,
        sale: SaleModel,
        delivery: SalesDeliveryModel,
        assignments: list[dict[str, Any]],
    ) -> None:
        by_id, grouped = await self._validated_assignment_groups(sale, assignments)
        await self._clear_draft_lines(delivery)
        await self._persist_draft_lines(sale, delivery, by_id, grouped)

    async def create_draft(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        sale_id: uuid.UUID,
        assignments: list[dict[str, Any]],
        notes: str | None,
        idempotency_key: str,
        request: Any,
    ) -> dict[str, Any]:
        digest = self._assignments_fingerprint(sale_id, assignments, notes)
        async with self.session.begin_nested():
            sale = await self._sale(company_id, sale_id, lock=True)
            if sale.status != "confirmed":
                raise BusinessRuleError(
                    "Solo una venta confirmada puede preparar entregas.",
                    code="sales_delivery_sale_not_confirmed",
                )
            await self._lock_key(company_id, "create", idempotency_key)
            command = await self.session.scalar(
                select(SalesDeliveryCommandModel).where(
                    SalesDeliveryCommandModel.company_id == company_id,
                    SalesDeliveryCommandModel.action == "create",
                    SalesDeliveryCommandModel.idempotency_key == idempotency_key,
                )
            )
            if command is not None:
                if command.fingerprint != digest:
                    raise ConflictError(
                        "La clave de creación ya se usó con otra selección.",
                        code="sales_delivery_idempotency_conflict",
                    )
                return await self.delivery_out(company_id, command.delivery_id)
            delivery = SalesDeliveryModel(
                company_id=company_id,
                branch_id=sale.branch_id,
                sale_id=sale.id,
                code=f"ENT-{datetime.now(UTC):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
                status="draft",
                version=1,
                notes=(notes or "").strip() or None,
                created_by_id=actor_id,
            )
            self.session.add(delivery)
            await self.session.flush()
            await self._replace_draft_lines(sale=sale, delivery=delivery, assignments=assignments)
            self.session.add(
                SalesDeliveryCommandModel(
                    company_id=company_id,
                    action="create",
                    idempotency_key=idempotency_key,
                    fingerprint=digest,
                    delivery_id=delivery.id,
                    actor_id=actor_id,
                )
            )
            await self.session.flush()
            await self._audit(
                action="SALES_DELIVERY_DRAFT_CREATED",
                actor_id=actor_id,
                company_id=company_id,
                branch_id=sale.branch_id,
                delivery_id=delivery.id,
                request=request,
                after={
                    "code": delivery.code,
                    "status": delivery.status,
                    "version": delivery.version,
                },
            )
        return await self.delivery_out(company_id, delivery.id)

    async def update_draft(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        delivery_id: uuid.UUID,
        expected_version: int,
        assignments: list[dict[str, Any]],
        notes: str | None,
        request: Any,
    ) -> dict[str, Any]:
        async with self.session.begin_nested():
            initial = await self._delivery(company_id, delivery_id)
            sale = await self._sale(company_id, initial.sale_id, lock=True)
            delivery = await self._delivery(company_id, delivery_id, lock=True)
            if delivery.status != "draft":
                raise BusinessRuleError(
                    "Solo se puede editar un borrador de entrega.",
                    code="sales_delivery_state_invalid",
                )
            if delivery.version != expected_version:
                raise ConflictError(
                    "El borrador cambió. Recárguelo antes de editar.",
                    code="sales_delivery_version_conflict",
                )
            before = {"status": delivery.status, "version": delivery.version}
            await self._replace_draft_lines(sale=sale, delivery=delivery, assignments=assignments)
            delivery.notes = (notes or "").strip() or None
            delivery.version += 1
            await self.session.flush()
            await self._audit(
                action="SALES_DELIVERY_DRAFT_UPDATED",
                actor_id=actor_id,
                company_id=company_id,
                branch_id=sale.branch_id,
                delivery_id=delivery.id,
                request=request,
                before=before,
                after={"status": delivery.status, "version": delivery.version},
            )
        return await self.delivery_out(company_id, delivery.id)

    async def cancel_draft(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        delivery_id: uuid.UUID,
        expected_version: int,
        reason: str,
        request: Any,
    ) -> dict[str, Any]:
        reason = reason.strip()
        if not reason:
            raise ValidationError(
                "Indique el motivo de cancelación.", code="sales_delivery_reason_required"
            )
        async with self.session.begin_nested():
            initial = await self._delivery(company_id, delivery_id)
            sale = await self._sale(company_id, initial.sale_id, lock=True)
            delivery = await self._delivery(company_id, delivery_id, lock=True)
            if delivery.status != "draft":
                raise BusinessRuleError(
                    "Solo se puede cancelar un borrador de entrega.",
                    code="sales_delivery_state_invalid",
                )
            if delivery.version != expected_version:
                raise ConflictError(
                    "El borrador cambió. Recárguelo antes de cancelar.",
                    code="sales_delivery_version_conflict",
                )
            before = {"status": delivery.status, "version": delivery.version}
            delivery.status = "cancelled"
            delivery.cancelled_by_id = actor_id
            delivery.cancelled_at = datetime.now(UTC)
            delivery.cancellation_reason = reason
            delivery.version += 1
            await self.session.flush()
            await self._audit(
                action="SALES_DELIVERY_DRAFT_CANCELLED",
                actor_id=actor_id,
                company_id=company_id,
                branch_id=sale.branch_id,
                delivery_id=delivery.id,
                request=request,
                before=before,
                after={"status": delivery.status, "version": delivery.version},
            )
        return await self.delivery_out(company_id, delivery_id)

    async def _confirmation_lines(
        self, company_id: uuid.UUID, sale: SaleModel, delivery: SalesDeliveryModel
    ) -> list[SalesDeliveryLineModel]:
        lines = list(
            (
                await self.session.scalars(
                    select(SalesDeliveryLineModel)
                    .where(
                        SalesDeliveryLineModel.company_id == company_id,
                        SalesDeliveryLineModel.delivery_id == delivery.id,
                    )
                    .order_by(SalesDeliveryLineModel.line_number)
                    .with_for_update()
                )
            ).all()
        )
        if not lines:
            raise ValidationError("La entrega no contiene unidades.", code="sales_delivery_empty")
        sale_lines = {line.id: line for line in await self._sale_lines(company_id, sale.id)}
        delivered = await self._delivered_by_line(company_id, sale.id)
        for line in lines:
            sale_line = sale_lines.get(line.sale_line_id)
            if sale_line is None or sale_line.inventory_item_id != line.inventory_item_id:
                raise ValidationError(
                    "Una línea de entrega ya no coincide con la venta.",
                    code="sales_delivery_line_mismatch",
                )
            pending = Decimal(sale_line.quantity_base) - delivered.get(sale_line.id, ZERO)
            if Decimal(line.quantity_base) > pending:
                raise ConflictError(
                    f"La entrega excedería el pendiente de {sale_line.product_name}.",
                    code="sales_delivery_exceeds_pending",
                )
        return lines

    async def _allocations_and_movement_inputs(
        self, company_id: uuid.UUID, sale: SaleModel, delivery: SalesDeliveryModel
    ) -> tuple[list[SalesDeliveryAllocationModel], list[dict[str, Any]]]:
        allocations = list(
            (
                await self.session.scalars(
                    select(SalesDeliveryAllocationModel)
                    .join(
                        SalesDeliveryLineModel,
                        (
                            SalesDeliveryLineModel.company_id
                            == SalesDeliveryAllocationModel.company_id
                        )
                        & (
                            SalesDeliveryLineModel.id
                            == SalesDeliveryAllocationModel.delivery_line_id
                        ),
                    )
                    .where(
                        SalesDeliveryAllocationModel.company_id == company_id,
                        SalesDeliveryLineModel.delivery_id == delivery.id,
                    )
                    .order_by(SalesDeliveryAllocationModel.handling_unit_id)
                    .with_for_update()
                )
            ).all()
        )
        if not allocations:
            raise ValidationError(
                "Seleccione unidades logísticas para entregar.",
                code="sales_delivery_assignments_required",
            )
        if len({row.handling_unit_id for row in allocations}) != len(allocations):
            raise ValidationError(
                "Una unidad aparece más de una vez.", code="sales_delivery_duplicate_unit"
            )
        movement_inputs: list[dict[str, Any]] = []
        for allocation in allocations:
            unit, _, _ = await self._available_unit(
                company_id=company_id,
                branch_id=sale.branch_id,
                inventory_item_id=allocation.inventory_item_id,
                handling_unit_id=allocation.handling_unit_id,
                expected_warehouse_id=allocation.warehouse_id,
                expected_location_id=allocation.location_id,
                expected_quantity=Decimal(allocation.quantity_base),
                expected_lot_detail_id=allocation.inventory_lot_detail_id,
                validate_expected_lot_detail=True,
            )
            movement_inputs.append(
                {
                    "inventory_item_id": allocation.inventory_item_id,
                    "handling_unit_id": unit.id,
                    "inventory_lot_detail_id": unit.inventory_lot_detail_id,
                    "from_location_id": unit.location_id,
                    "from_stock_status": "available",
                    "to_location_id": None,
                    "to_stock_status": None,
                    "quantity_base": unit.quantity_base,
                    "lot_code": unit.lot_code,
                    "expiry_date": unit.expiry_date,
                }
            )
        return allocations, movement_inputs

    async def _post_and_load_valuation(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        delivery: SalesDeliveryModel,
        movement_inputs: list[dict[str, Any]],
    ) -> tuple[
        InventoryMovementModel,
        dict[uuid.UUID, tuple[InventoryMovementLineModel, InventoryValuationEntryModel]],
    ]:
        movement = await self.inventory.post_movement(
            company_id=company_id,
            idempotency_key=f"sales-delivery-confirm:{delivery.id}",
            movement_type="shipment",
            source_reference=f"sales_delivery:{delivery.id}",
            lines=movement_inputs,
            actor_id=actor_id,
        )
        movement_row = await self.session.scalar(
            select(InventoryMovementModel).where(
                InventoryMovementModel.company_id == company_id,
                InventoryMovementModel.id == movement["id"],
            )
        )
        if movement_row is None:
            raise ConflictError(
                "No se pudo recuperar la salida física registrada.",
                code="sales_delivery_movement_not_found",
            )
        posted_lines = list(
            (
                await self.session.scalars(
                    select(InventoryMovementLineModel).where(
                        InventoryMovementLineModel.company_id == company_id,
                        InventoryMovementLineModel.movement_id == movement_row.id,
                    )
                )
            ).all()
        )
        if not posted_lines:
            raise ConflictError(
                "La salida no registró unidades.", code="sales_delivery_movement_incomplete"
            )
        valuation_rows = list(
            (
                await self.session.scalars(
                    select(InventoryValuationEntryModel).where(
                        InventoryValuationEntryModel.company_id == company_id,
                        InventoryValuationEntryModel.movement_line_id.in_(
                            [line.id for line in posted_lines]
                        ),
                        InventoryValuationEntryModel.kind == "issue",
                    )
                )
            ).all()
        )
        valuation_by_line = {row.movement_line_id: row for row in valuation_rows}
        entries_by_unit: dict[
            uuid.UUID, tuple[InventoryMovementLineModel, InventoryValuationEntryModel]
        ] = {}
        for line in posted_lines:
            entry = valuation_by_line.get(line.id)
            if line.handling_unit_id is not None and entry is not None:
                entries_by_unit[line.handling_unit_id] = (line, entry)
        return movement_row, entries_by_unit

    async def _finalize_confirmation(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        sale: SaleModel,
        delivery: SalesDeliveryModel,
        allocations: list[SalesDeliveryAllocationModel],
        entries_by_unit: dict[
            uuid.UUID, tuple[InventoryMovementLineModel, InventoryValuationEntryModel]
        ],
        movement_id: uuid.UUID,
        idempotency_key: str,
        digest: str,
        request: Any,
    ) -> None:
        before = {"status": delivery.status, "version": delivery.version}
        for allocation in allocations:
            posted = entries_by_unit.get(allocation.handling_unit_id)
            if posted is None:
                raise BusinessRuleError(
                    "La salida no generó su referencia de valoración. Verifique el corte inicial y reintente.",
                    code="sales_delivery_valuation_missing",
                )
            movement_line, entry = posted
            allocation.movement_line_id = movement_line.id
            allocation.valuation_entry_id = entry.id
            allocation.applied_total_cost = max(ZERO, -Decimal(entry.inventory_delta))
            allocation.applied_unit_cost = Decimal(entry.average_unit_cost).quantize(
                QTY_QUANTUM, rounding=ROUND_HALF_UP
            )
        delivery.status = "confirmed"
        delivery.confirmed_by_id = actor_id
        delivery.confirmed_at = datetime.now(UTC)
        delivery.version += 1
        self.session.add(
            SalesDeliveryCommandModel(
                company_id=company_id,
                action="confirm",
                idempotency_key=idempotency_key,
                fingerprint=digest,
                delivery_id=delivery.id,
                actor_id=actor_id,
            )
        )
        await self.session.flush()
        await self._audit(
            action="SALES_DELIVERY_CONFIRMED",
            actor_id=actor_id,
            company_id=company_id,
            branch_id=sale.branch_id,
            delivery_id=delivery.id,
            request=request,
            before=before,
            after={
                "code": delivery.code,
                "status": delivery.status,
                "version": delivery.version,
                "movement_id": str(movement_id),
            },
        )

    async def _confirm_locked(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        sale: SaleModel,
        delivery: SalesDeliveryModel,
        expected_version: int,
        idempotency_key: str,
        digest: str,
        request: Any,
    ) -> None:
        if sale.status != "confirmed":
            raise BusinessRuleError(
                "No se puede entregar una venta cancelada o sin confirmar.",
                code="sales_delivery_sale_not_confirmed",
            )
        if delivery.status != "draft":
            raise BusinessRuleError(
                "Solo se puede confirmar un borrador de entrega.",
                code="sales_delivery_state_invalid",
            )
        if delivery.version != expected_version:
            raise ConflictError(
                "El borrador cambió. Recárguelo antes de confirmar.",
                code="sales_delivery_version_conflict",
            )
        if await self.session.get(InventoryValuationSettingModel, company_id) is None:
            raise BusinessRuleError(
                "Apruebe el saldo inicial de valoración antes de entregar inventario.",
                code="inventory_valuation_opening_required",
            )
        await self._confirmation_lines(company_id, sale, delivery)
        allocations, movement_inputs = await self._allocations_and_movement_inputs(
            company_id, sale, delivery
        )
        try:
            movement, entries_by_unit = await self._post_and_load_valuation(
                company_id, actor_id, delivery, movement_inputs
            )
        except InventoryOperationError as exc:
            # The HUs were revalidated above. If another transaction consumes one
            # before the inventory engine locks it, the engine reports it as
            # missing/closed; at this boundary it is a stale draft conflict.
            if exc.code == "handling_unit_not_available":
                raise ConflictError(
                    "La unidad seleccionada ya no está disponible. Recargue las existencias y prepare la entrega de nuevo.",
                    code="sales_delivery_unit_unavailable",
                ) from exc
            raise
        if len(entries_by_unit) != len(allocations):
            raise ConflictError(
                "La salida no registró todas las unidades con su valoración.",
                code="sales_delivery_movement_incomplete",
            )
        await self._finalize_confirmation(
            company_id=company_id,
            actor_id=actor_id,
            sale=sale,
            delivery=delivery,
            allocations=allocations,
            entries_by_unit=entries_by_unit,
            movement_id=movement.id,
            idempotency_key=idempotency_key,
            digest=digest,
            request=request,
        )

    async def confirm(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        delivery_id: uuid.UUID,
        expected_version: int,
        idempotency_key: str,
        request: Any,
    ) -> dict[str, Any]:
        digest = _fingerprint(
            {"delivery_id": str(delivery_id), "expected_version": expected_version}
        )
        async with self.session.begin_nested():
            initial = await self._delivery(company_id, delivery_id)
            # Sale is shared with cancellation to serialize sale-state mutations.
            sale = await self._sale(company_id, initial.sale_id, lock=True)
            delivery = await self._delivery(company_id, delivery_id, lock=True)
            await self._lock_key(company_id, "confirm", idempotency_key)
            command = await self.session.scalar(
                select(SalesDeliveryCommandModel).where(
                    SalesDeliveryCommandModel.company_id == company_id,
                    SalesDeliveryCommandModel.action == "confirm",
                    SalesDeliveryCommandModel.idempotency_key == idempotency_key,
                )
            )
            if command is not None:
                if command.fingerprint != digest or command.delivery_id != delivery.id:
                    raise ConflictError(
                        "La clave de confirmación ya se usó con otra entrega o contenido.",
                        code="sales_delivery_idempotency_conflict",
                    )
                return await self.delivery_out(company_id, delivery.id)
            await self._confirm_locked(
                company_id=company_id,
                actor_id=actor_id,
                sale=sale,
                delivery=delivery,
                expected_version=expected_version,
                idempotency_key=idempotency_key,
                digest=digest,
                request=request,
            )
        return await self.delivery_out(company_id, delivery_id)

    async def deliveries_for_sale(
        self, company_id: uuid.UUID, sale_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        rows = list(
            (
                await self.session.scalars(
                    select(SalesDeliveryModel)
                    .where(
                        SalesDeliveryModel.company_id == company_id,
                        SalesDeliveryModel.sale_id == sale_id,
                    )
                    .order_by(SalesDeliveryModel.created_at.desc(), SalesDeliveryModel.id)
                )
            ).all()
        )
        return [await self.delivery_out(company_id, row.id) for row in rows]

    async def delivery_out(self, company_id: uuid.UUID, delivery_id: uuid.UUID) -> dict[str, Any]:
        delivery = await self._delivery(company_id, delivery_id)
        lines = list(
            (
                await self.session.scalars(
                    select(SalesDeliveryLineModel)
                    .where(
                        SalesDeliveryLineModel.company_id == company_id,
                        SalesDeliveryLineModel.delivery_id == delivery_id,
                    )
                    .order_by(SalesDeliveryLineModel.line_number)
                )
            ).all()
        )
        result_lines: list[dict[str, Any]] = []
        for line in lines:
            allocations = list(
                (
                    await self.session.scalars(
                        select(SalesDeliveryAllocationModel)
                        .where(
                            SalesDeliveryAllocationModel.company_id == company_id,
                            SalesDeliveryAllocationModel.delivery_line_id == line.id,
                        )
                        .order_by(SalesDeliveryAllocationModel.id)
                    )
                ).all()
            )
            unit_ids = [allocation.handling_unit_id for allocation in allocations]
            units = (
                {
                    row.id: row
                    for row in (
                        await self.session.scalars(
                            select(InventoryHandlingUnitModel).where(
                                InventoryHandlingUnitModel.company_id == company_id,
                                InventoryHandlingUnitModel.id.in_(unit_ids),
                            )
                        )
                    ).all()
                }
                if unit_ids
                else {}
            )
            movement_lines = (
                {
                    row.id: row
                    for row in (
                        await self.session.scalars(
                            select(InventoryMovementLineModel).where(
                                InventoryMovementLineModel.company_id == company_id,
                                InventoryMovementLineModel.id.in_(
                                    [
                                        allocation.movement_line_id
                                        for allocation in allocations
                                        if allocation.movement_line_id
                                    ]
                                ),
                            )
                        )
                    ).all()
                }
                if any(allocation.movement_line_id for allocation in allocations)
                else {}
            )
            result_lines.append(
                {
                    "id": line.id,
                    "sale_line_id": line.sale_line_id,
                    "product_sku": line.product_sku,
                    "product_name": line.product_name,
                    "unit_name": line.unit_name,
                    "base_unit_name": line.base_unit_name,
                    "quantity_base": line.quantity_base,
                    "quantity_in_sale_unit": (
                        Decimal(line.quantity_base) / Decimal(line.unit_factor)
                    ).quantize(QTY_QUANTUM, rounding=ROUND_HALF_UP),
                    "unit_factor": line.unit_factor,
                    "allocations": [
                        {
                            "id": allocation.id,
                            "handling_unit_id": allocation.handling_unit_id,
                            "handling_unit_code": units[allocation.handling_unit_id].code
                            if allocation.handling_unit_id in units
                            else None,
                            "warehouse_id": allocation.warehouse_id,
                            "location_id": allocation.location_id,
                            "inventory_lot_detail_id": allocation.inventory_lot_detail_id,
                            "lot_code": allocation.lot_code,
                            "expiry_date": allocation.expiry_date,
                            "quantity_base": allocation.quantity_base,
                            "movement_id": movement_lines[allocation.movement_line_id].movement_id
                            if allocation.movement_line_id in movement_lines
                            else None,
                            "movement_line_id": allocation.movement_line_id,
                            "valuation_entry_id": allocation.valuation_entry_id,
                        }
                        for allocation in allocations
                    ],
                }
            )
        return {
            "id": delivery.id,
            "company_id": delivery.company_id,
            "branch_id": delivery.branch_id,
            "sale_id": delivery.sale_id,
            "code": delivery.code,
            "status": delivery.status,
            "version": delivery.version,
            "notes": delivery.notes,
            "created_by_id": delivery.created_by_id,
            "confirmed_by_id": delivery.confirmed_by_id,
            "confirmed_at": delivery.confirmed_at,
            "cancelled_by_id": delivery.cancelled_by_id,
            "cancelled_at": delivery.cancelled_at,
            "cancellation_reason": delivery.cancellation_reason,
            "created_at": delivery.created_at,
            "updated_at": delivery.updated_at,
            "lines": result_lines,
        }
