"""Customer returns linked to confirmed delivery allocations.

All physical and valuation effects are delegated to the canonical inventory
engine. Commercial responses deliberately omit inventory costs.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.application.audit.audit_service import AuditService
from app.application.inventory import InventoryUseCases
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError, ValidationError
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.document_record import DocumentRecordModel
from app.infrastructure.models.inventory import (
    InventoryHandlingUnitModel,
)
from app.infrastructure.models.inventory_valuation import InventoryValuationEntryModel
from app.infrastructure.models.organization import Location, Warehouse
from app.infrastructure.models.sales import SaleModel
from app.infrastructure.models.sales_delivery import (
    SalesDeliveryAllocationModel,
    SalesDeliveryLineModel,
    SalesDeliveryModel,
)
from app.infrastructure.models.sales_return import (
    SalesReturnCommandModel,
    SalesReturnDocumentModel,
    SalesReturnEventModel,
    SalesReturnLineModel,
    SalesReturnModel,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

ZERO = Decimal("0")
OPEN_STATUSES = ("draft", "received", "under_review")
MIN_CANCELLATION_REASON_LENGTH = 3
MAX_RETURN_REASON_LENGTH = 500


def _fingerprint(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_reason(reason: str) -> str:
    reason = reason.strip()
    if not MIN_CANCELLATION_REASON_LENGTH <= len(reason) <= MAX_RETURN_REASON_LENGTH:
        raise ValidationError(
            "El motivo debe tener entre 3 y 500 caracteres sin contar espacios exteriores.",
            code="sales_return_reason_invalid",
        )
    return reason


class SalesReturnService:
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
        return_id: uuid.UUID,
        request: Any,
        before: dict[str, object] | None = None,
        after: dict[str, object] | None = None,
    ) -> None:
        await self.audit.record(
            action=action,
            user_id=actor_id,
            company_id=company_id,
            branch_id=branch_id,
            resource_type="sales_return",
            resource_id=str(return_id),
            before_state=before,
            after_state=after,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            required=True,
        )

    async def _lock_key(self, company_id: uuid.UUID, action: str, key: str) -> None:
        lock = f"sales-return:{company_id}:{action}:{key}"
        await self.session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(lock, 0))))

    async def _sale(
        self, company_id: uuid.UUID, sale_id: uuid.UUID, *, lock: bool = False
    ) -> SaleModel:
        statement = select(SaleModel).where(
            SaleModel.company_id == company_id, SaleModel.id == sale_id
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        sale = await self.session.scalar(statement)
        if sale is None:
            raise NotFoundError("Venta no encontrada.", code="sales_sale_not_found")
        return sale

    async def _return(
        self, company_id: uuid.UUID, return_id: uuid.UUID, *, lock: bool = False
    ) -> SalesReturnModel:
        statement = select(SalesReturnModel).where(
            SalesReturnModel.company_id == company_id,
            SalesReturnModel.id == return_id,
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        row = await self.session.scalar(statement)
        if row is None:
            raise NotFoundError("Devolución no encontrada.", code="sales_return_not_found")
        return row

    async def return_header(self, company_id: uuid.UUID, return_id: uuid.UUID) -> SalesReturnModel:
        return await self._return(company_id, return_id)

    @staticmethod
    def _validate_create_input(
        lines: list[dict[str, Any]], document_ids: list[uuid.UUID]
    ) -> None:
        if len({line["delivery_allocation_id"] for line in lines}) != len(lines):
            raise ValidationError(
                "Cada asignación de entrega puede aparecer una sola vez en la devolución.",
                code="sales_return_duplicate_allocation",
            )
        if len(set(document_ids)) != len(document_ids):
            raise ValidationError(
                "No repita el mismo documento de evidencia.",
                code="sales_return_duplicate_evidence",
            )

    async def _source_allocation(
        self, company_id: uuid.UUID, sale_id: uuid.UUID, allocation_id: uuid.UUID
    ):
        row = (
            await self.session.execute(
                select(
                    SalesDeliveryAllocationModel,
                    SalesDeliveryLineModel,
                    SalesDeliveryModel,
                    SaleModel,
                    InventoryHandlingUnitModel,
                    InventoryValuationEntryModel,
                )
                .join(
                    SalesDeliveryLineModel,
                    (SalesDeliveryLineModel.company_id == SalesDeliveryAllocationModel.company_id)
                    & (SalesDeliveryLineModel.id == SalesDeliveryAllocationModel.delivery_line_id),
                )
                .join(
                    SalesDeliveryModel,
                    (SalesDeliveryModel.company_id == SalesDeliveryLineModel.company_id)
                    & (SalesDeliveryModel.id == SalesDeliveryLineModel.delivery_id),
                )
                .join(
                    SaleModel,
                    (SaleModel.company_id == SalesDeliveryModel.company_id)
                    & (SaleModel.id == SalesDeliveryModel.sale_id),
                )
                .join(
                    InventoryHandlingUnitModel,
                    (InventoryHandlingUnitModel.company_id == SalesDeliveryAllocationModel.company_id)
                    & (InventoryHandlingUnitModel.id == SalesDeliveryAllocationModel.handling_unit_id),
                )
                .join(
                    InventoryValuationEntryModel,
                    (InventoryValuationEntryModel.company_id == SalesDeliveryAllocationModel.company_id)
                    & (InventoryValuationEntryModel.id == SalesDeliveryAllocationModel.valuation_entry_id),
                )
                .where(
                    SalesDeliveryAllocationModel.company_id == company_id,
                    SalesDeliveryAllocationModel.id == allocation_id,
                    SalesDeliveryModel.sale_id == sale_id,
                    SalesDeliveryModel.status == "confirmed",
                    SaleModel.status == "confirmed",
                    SalesDeliveryLineModel.sale_id == sale_id,
                    SalesDeliveryAllocationModel.movement_line_id.is_not(None),
                    InventoryValuationEntryModel.kind == "issue",
                    InventoryValuationEntryModel.inventory_item_id
                    == SalesDeliveryAllocationModel.inventory_item_id,
                    InventoryValuationEntryModel.movement_line_id
                    == SalesDeliveryAllocationModel.movement_line_id,
                )
            )
        ).first()
        if row is None:
            raise ValidationError(
                "La asignación no corresponde a una entrega confirmada y valorizada de esta venta.",
                code="sales_return_source_allocation_invalid",
            )
        return row

    async def _allocation_usage(
        self, company_id: uuid.UUID, allocation_ids: set[uuid.UUID], *, exclude_reservation_return_id: uuid.UUID | None = None
    ) -> dict[uuid.UUID, tuple[Decimal, Decimal]]:
        """Return (accepted, reserved) quantities, serializable by locking the sale."""
        if not allocation_ids:
            return {}
        lines = list(
            (
                await self.session.execute(
                    select(SalesReturnLineModel, SalesReturnModel.status)
                    .join(
                        SalesReturnModel,
                        (SalesReturnModel.company_id == SalesReturnLineModel.company_id)
                        & (SalesReturnModel.id == SalesReturnLineModel.return_id),
                    )
                    .where(
                        SalesReturnLineModel.company_id == company_id,
                        SalesReturnLineModel.delivery_allocation_id.in_(allocation_ids),
                    )
                )
            ).all()
        )
        line_ids = {line.id for line, _status in lines}
        totals: dict[uuid.UUID, Decimal] = {}
        accepted: dict[uuid.UUID, Decimal] = {}
        if line_ids:
            for line_id, decision, quantity in (
                await self.session.execute(
                    select(
                        SalesReturnEventModel.return_line_id,
                        SalesReturnEventModel.decision,
                        func.sum(SalesReturnEventModel.quantity_base),
                    )
                    .where(
                        SalesReturnEventModel.company_id == company_id,
                        SalesReturnEventModel.return_line_id.in_(line_ids),
                    )
                    .group_by(SalesReturnEventModel.return_line_id, SalesReturnEventModel.decision)
                )
            ).all():
                totals.setdefault(line_id, ZERO)
                totals[line_id] += Decimal(quantity or ZERO)
                if decision == "accepted":
                    accepted[line_id] = Decimal(quantity or ZERO)
        result = {allocation_id: (ZERO, ZERO) for allocation_id in allocation_ids}
        statuses = {line.id: (line, status) for line, status in lines}
        for line_id, (line, status) in statuses.items():
            accepted_qty, reserved_qty = result[line.delivery_allocation_id]
            accepted_qty += accepted.get(line_id, ZERO)
            if (
                status in OPEN_STATUSES
                and line.return_id != exclude_reservation_return_id
            ):
                reserved_qty += max(line.quantity_received_base - totals.get(line_id, ZERO), ZERO)
            result[line.delivery_allocation_id] = (accepted_qty, reserved_qty)
        return result

    async def returnable_allocations(
        self, company_id: uuid.UUID, sale_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        await self._sale(company_id, sale_id)
        rows = list(
            (
                await self.session.execute(
                    select(
                        SalesDeliveryAllocationModel,
                        SalesDeliveryLineModel,
                        SalesDeliveryModel,
                        InventoryHandlingUnitModel,
                    )
                    .join(
                        SalesDeliveryLineModel,
                        (SalesDeliveryLineModel.company_id == SalesDeliveryAllocationModel.company_id)
                        & (SalesDeliveryLineModel.id == SalesDeliveryAllocationModel.delivery_line_id),
                    )
                    .join(
                        SalesDeliveryModel,
                        (SalesDeliveryModel.company_id == SalesDeliveryLineModel.company_id)
                        & (SalesDeliveryModel.id == SalesDeliveryLineModel.delivery_id),
                    )
                    .join(
                        InventoryHandlingUnitModel,
                        (InventoryHandlingUnitModel.company_id == SalesDeliveryAllocationModel.company_id)
                        & (InventoryHandlingUnitModel.id == SalesDeliveryAllocationModel.handling_unit_id),
                    )
                    .where(
                        SalesDeliveryAllocationModel.company_id == company_id,
                        SalesDeliveryModel.sale_id == sale_id,
                        SalesDeliveryModel.status == "confirmed",
                        SalesDeliveryAllocationModel.valuation_entry_id.is_not(None),
                    )
                    .order_by(SalesDeliveryModel.confirmed_at, SalesDeliveryLineModel.line_number, SalesDeliveryAllocationModel.id)
                )
            ).all()
        )
        usage = await self._allocation_usage(
            company_id, {allocation.id for allocation, *_ in rows}
        )
        output = []
        for allocation, line, delivery, unit in rows:
            returned, reserved = usage[allocation.id]
            output.append(
                {
                    "delivery_id": delivery.id,
                    "delivery_code": delivery.code,
                    "delivery_line_id": line.id,
                    "delivery_allocation_id": allocation.id,
                    "delivery_date": delivery.confirmed_at,
                    "handling_unit_code": unit.code,
                    "inventory_item_id": line.inventory_item_id,
                    "product_sku": line.product_sku,
                    "product_name": line.product_name,
                    "unit_name": line.unit_name,
                    "base_unit_name": line.base_unit_name,
                    "lot_code": allocation.lot_code,
                    "quantity_delivered_base": allocation.quantity_base,
                    "quantity_returned_base": returned,
                    "quantity_reserved_base": reserved,
                    "quantity_returnable_base": max(allocation.quantity_base - returned - reserved, ZERO),
                }
            )
        return output

    async def create_draft(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        sale_id: uuid.UUID,
        lines: list[dict[str, Any]],
        document_ids: list[uuid.UUID],
        notes: str | None,
        idempotency_key: str,
        request: Any,
    ) -> dict[str, Any]:
        self._validate_create_input(lines, document_ids)
        lines = [{**line, "reason": _normalize_reason(line["reason"])} for line in lines]
        digest = _fingerprint({"sale_id": sale_id, "lines": lines, "notes": notes, "document_ids": document_ids})
        async with self.session.begin_nested():
            sale = await self._sale(company_id, sale_id, lock=True)
            if sale.status != "confirmed":
                raise BusinessRuleError(
                    "Solo se puede devolver una venta confirmada con entregas registradas.",
                    code="sales_return_sale_not_confirmed",
                )
            await self._lock_key(company_id, "create", idempotency_key)
            command = await self.session.scalar(
                select(SalesReturnCommandModel).where(
                    SalesReturnCommandModel.company_id == company_id,
                    SalesReturnCommandModel.action == "create",
                    SalesReturnCommandModel.idempotency_key == idempotency_key,
                )
            )
            if command is not None:
                if command.fingerprint != digest or command.return_id is None:
                    raise ConflictError("La clave de devolución ya se usó con otro contenido.", code="sales_return_idempotency_conflict")
                return await self.return_out(company_id, command.return_id)

            evidence = await self._validate_evidence_documents(company_id, document_ids)

            sources = []
            for payload in lines:
                source = await self._source_allocation(
                    company_id, sale_id, payload["delivery_allocation_id"]
                )
                allocation = source[0]
                if payload["quantity_base"] > allocation.quantity_base:
                    raise ValidationError("La cantidad solicitada supera lo entregado en esa unidad.", code="sales_return_quantity_exceeds_delivered")
                sources.append((payload, source))
            usage = await self._allocation_usage(
                company_id, {source[0].id for _payload, source in sources}
            )
            for payload, source in sources:
                allocation = source[0]
                returned, reserved = usage[allocation.id]
                remaining = allocation.quantity_base - returned - reserved
                if payload["quantity_base"] > remaining:
                    raise ConflictError(
                        "La cantidad restante ya está reservada o fue aceptada en otra devolución.",
                        code="sales_return_quantity_no_longer_available",
                    )

            document = SalesReturnModel(
                company_id=company_id,
                branch_id=sale.branch_id,
                sale_id=sale.id,
                code=f"DEV-{datetime.now(UTC):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
                status="draft",
                notes=(notes or "").strip() or None,
                created_by_id=actor_id,
                updated_by_id=actor_id,
            )
            self.session.add(document)
            await self.session.flush()
            for record, _asset in evidence:
                self.session.add(SalesReturnDocumentModel(
                    company_id=company_id,
                    return_id=document.id,
                    document_id=record.id,
                    attached_by_id=actor_id,
                ))
            for index, (payload, source) in enumerate(sources, start=1):
                allocation, delivery_line, delivery, _source_sale, source_unit, valuation_entry = source
                self.session.add(
                    SalesReturnLineModel(
                        company_id=company_id,
                        return_id=document.id,
                        sale_id=sale.id,
                        delivery_id=delivery.id,
                        delivery_line_id=delivery_line.id,
                        delivery_allocation_id=allocation.id,
                        inventory_item_id=delivery_line.inventory_item_id,
                        source_valuation_entry_id=valuation_entry.id,
                        source_handling_unit_id=source_unit.id,
                        source_warehouse_id=allocation.warehouse_id,
                        source_location_id=allocation.location_id,
                        inventory_lot_detail_id=allocation.inventory_lot_detail_id,
                        line_number=index,
                        product_sku=delivery_line.product_sku,
                        product_name=delivery_line.product_name,
                        unit_name=delivery_line.unit_name,
                        base_unit_name=delivery_line.base_unit_name,
                        lot_code=allocation.lot_code,
                        expiry_date=allocation.expiry_date,
                        quantity_received_base=payload["quantity_base"],
                        reason=payload["reason"].strip(),
                        declared_condition=payload["declared_condition"],
                    )
                )
            self.session.add(
                SalesReturnCommandModel(
                    company_id=company_id,
                    action="create",
                    idempotency_key=idempotency_key,
                    fingerprint=digest,
                    return_id=document.id,
                    actor_id=actor_id,
                )
            )
            await self.session.flush()
            await self._audit(
                action="SALES_RETURN_DRAFT_CREATED",
                actor_id=actor_id,
                company_id=company_id,
                branch_id=sale.branch_id,
                return_id=document.id,
                request=request,
                after={"code": document.code, "status": document.status, "line_count": len(sources)},
            )
        return await self.return_out(company_id, document.id)

    async def receive(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        return_id: uuid.UUID,
        idempotency_key: str,
        request: Any,
    ) -> dict[str, Any]:
        digest = _fingerprint({"return_id": return_id, "action": "receive"})
        async with self.session.begin_nested():
            initial = await self._return(company_id, return_id)
            sale = await self._sale(company_id, initial.sale_id, lock=True)
            document = await self._return(company_id, return_id, lock=True)
            await self._lock_key(company_id, "receive", idempotency_key)
            command = await self._command(company_id, "receive", idempotency_key)
            if command:
                self._assert_replay(command, digest, return_id)
                return await self.return_out(company_id, return_id)
            if document.status != "draft":
                raise BusinessRuleError("Solo un borrador puede registrarse como recibido.", code="sales_return_state_invalid")
            document.status = "received"
            document.received_by_id = actor_id
            document.received_at = datetime.now(UTC)
            document.updated_by_id = actor_id
            self.session.add(self._command_row(company_id, "receive", idempotency_key, digest, return_id, actor_id))
            await self.session.flush()
            await self._audit(
                action="SALES_RETURN_RECEIVED",
                actor_id=actor_id,
                company_id=company_id,
                branch_id=sale.branch_id,
                return_id=return_id,
                request=request,
                before={"status": "draft"},
                after={"status": "received", "received_at": document.received_at.isoformat()},
            )
        return await self.return_out(company_id, return_id)

    async def _validate_evidence_documents(self, company_id: uuid.UUID, document_ids: list[uuid.UUID]):
        if not document_ids:
            return []
        rows = (await self.session.execute(
            select(DocumentRecordModel, DocumentAssetModel)
            .join(DocumentAssetModel, DocumentAssetModel.id == DocumentRecordModel.id)
            .where(
                DocumentRecordModel.company_id == company_id,
                DocumentRecordModel.id.in_(document_ids),
                DocumentRecordModel.module == "general",
                DocumentRecordModel.owner_type.is_(None),
                DocumentRecordModel.owner_id.is_(None),
                DocumentRecordModel.is_current.is_(True),
                DocumentAssetModel.company_id == company_id,
                DocumentAssetModel.status == "active",
                DocumentAssetModel.deleted_at.is_(None),
            )
        )).all()
        if len(rows) != len(document_ids):
            raise ValidationError(
                "Cada evidencia debe ser un documento general vigente, activo y accesible de esta empresa.",
                code="sales_return_evidence_unavailable",
            )
        return rows

    async def cancel_draft(
        self,
        *, company_id: uuid.UUID, actor_id: uuid.UUID, return_id: uuid.UUID,
        reason: str, idempotency_key: str, request: Any,
    ) -> dict[str, Any]:
        reason = reason.strip()
        if len(reason) < MIN_CANCELLATION_REASON_LENGTH:
            raise ValidationError("Escriba un motivo para cancelar.", code="sales_return_cancellation_reason_required")
        digest = _fingerprint({"return_id": return_id, "reason": reason})
        async with self.session.begin_nested():
            initial = await self._return(company_id, return_id)
            sale = await self._sale(company_id, initial.sale_id, lock=True)
            document = await self._return(company_id, return_id, lock=True)
            await self._lock_key(company_id, "cancel", idempotency_key)
            command = await self._command(company_id, "cancel", idempotency_key)
            if command:
                self._assert_replay(command, digest, return_id)
                return await self.return_out(company_id, return_id)
            if document.status != "draft":
                raise BusinessRuleError("Solo se puede cancelar un borrador de devolución.", code="sales_return_state_invalid")
            document.status = "cancelled"
            document.cancelled_by_id = actor_id
            document.cancelled_at = datetime.now(UTC)
            document.cancellation_reason = reason
            document.updated_by_id = actor_id
            self.session.add(self._command_row(company_id, "cancel", idempotency_key, digest, return_id, actor_id))
            await self.session.flush()
            await self._audit(action="SALES_RETURN_DRAFT_CANCELLED", actor_id=actor_id,
                company_id=company_id, branch_id=sale.branch_id, return_id=return_id,
                request=request, before={"status": "draft"}, after={"status": "cancelled", "reason": reason})
        return await self.return_out(company_id, return_id)

    async def _command(self, company_id: uuid.UUID, action: str, key: str) -> SalesReturnCommandModel | None:
        return await self.session.scalar(select(SalesReturnCommandModel).where(
            SalesReturnCommandModel.company_id == company_id,
            SalesReturnCommandModel.action == action,
            SalesReturnCommandModel.idempotency_key == key,
        ))

    @staticmethod
    def _assert_replay(command: SalesReturnCommandModel, digest: str, return_id: uuid.UUID) -> None:
        if command.fingerprint != digest or command.return_id != return_id:
            raise ConflictError("La clave idempotente ya se usó con otro contenido.", code="sales_return_idempotency_conflict")

    @staticmethod
    def _command_row(company_id, action, key, digest, return_id, actor_id):
        return SalesReturnCommandModel(company_id=company_id, action=action,
            idempotency_key=key, fingerprint=digest, return_id=return_id, actor_id=actor_id)

    async def resolve(  # noqa: C901
        self,
        *, company_id: uuid.UUID, actor_id: uuid.UUID, return_id: uuid.UUID,
        lines: list[dict[str, Any]], idempotency_key: str, request: Any,
    ) -> dict[str, Any]:
        lines = [{**line, "reason": _normalize_reason(line["reason"])} for line in lines]
        if len({line["return_line_id"] for line in lines}) != len(lines):
            raise ValidationError("Cada línea puede resolverse una sola vez por operación.", code="sales_return_duplicate_resolution_line")
        digest = _fingerprint({"return_id": return_id, "lines": lines})
        async with self.session.begin_nested():
            initial = await self._return(company_id, return_id)
            sale = await self._sale(company_id, initial.sale_id, lock=True)
            document = await self._return(company_id, return_id, lock=True)
            await self._lock_key(company_id, "resolve", idempotency_key)
            command = await self._command(company_id, "resolve", idempotency_key)
            if command:
                self._assert_replay(command, digest, return_id)
                return await self.return_out(company_id, return_id)
            if document.status not in {"received", "under_review"}:
                raise BusinessRuleError("La devolución debe estar recibida y pendiente de revisión.", code="sales_return_state_invalid")
            prior_status = document.status

            line_ids = {line["return_line_id"] for line in lines}
            db_lines = list((await self.session.scalars(
                select(SalesReturnLineModel).where(
                    SalesReturnLineModel.company_id == company_id,
                    SalesReturnLineModel.return_id == return_id,
                    SalesReturnLineModel.id.in_(line_ids),
                ).order_by(SalesReturnLineModel.id).with_for_update()
            )).all())
            if len(db_lines) != len(line_ids):
                raise NotFoundError("Una de las líneas no pertenece a esta devolución.", code="sales_return_line_not_found")
            payloads = {item["return_line_id"]: item for item in lines}
            event_sums = {
                line_id: Decimal(total or ZERO)
                for line_id, total in (await self.session.execute(select(SalesReturnEventModel.return_line_id,
                    func.sum(SalesReturnEventModel.quantity_base)).where(
                    SalesReturnEventModel.company_id == company_id,
                    SalesReturnEventModel.return_line_id.in_(line_ids),
                ).group_by(SalesReturnEventModel.return_line_id))).all()
            }
            allocation_ids = {line.delivery_allocation_id for line in db_lines}
            usage = await self._allocation_usage(
                company_id, allocation_ids, exclude_reservation_return_id=return_id
            )
            data_by_id = {}
            for line in db_lines:
                payload = payloads[line.id]
                pending = line.quantity_received_base - event_sums.get(line.id, ZERO)
                if payload["quantity_base"] > pending:
                    raise ConflictError("La cantidad excede lo recibido que sigue pendiente de decisión.", code="sales_return_resolution_exceeds_pending")
                if payload["decision"] == "accepted" and payload["condition"] != "resalable":
                    raise ValidationError("Solo mercancía revisada como apta para reventa puede aceptarse al inventario.", code="sales_return_acceptance_requires_resalable")
                if payload["decision"] == "accepted" and payload.get("destination_location_id") is None:
                    payload["destination_location_id"] = line.source_location_id
                data_by_id[line.id] = (line, payload)

            # Recheck the allocation-wide cap while holding the sale row lock.
            decisions_by_allocation: dict[uuid.UUID, Decimal] = {}
            accepted_by_allocation: dict[uuid.UUID, Decimal] = {}
            for line, payload in data_by_id.values():
                decisions_by_allocation[line.delivery_allocation_id] = decisions_by_allocation.get(line.delivery_allocation_id, ZERO) + payload["quantity_base"]
                if payload["decision"] == "accepted":
                    accepted_by_allocation[line.delivery_allocation_id] = accepted_by_allocation.get(line.delivery_allocation_id, ZERO) + payload["quantity_base"]
            for allocation_id in allocation_ids:
                accepted_prior, reserved_other = usage[allocation_id]
                current_pending = sum(
                    (line.quantity_received_base - event_sums.get(line.id, ZERO)
                     for line in db_lines if line.delivery_allocation_id == allocation_id), ZERO
                )
                allocation = await self.session.get(SalesDeliveryAllocationModel, allocation_id)
                if allocation is None:
                    raise ConflictError("La asignación original ya no está disponible.", code="sales_return_source_allocation_invalid")
                remaining_after = current_pending - decisions_by_allocation.get(allocation_id, ZERO)
                if accepted_prior + accepted_by_allocation.get(allocation_id, ZERO) + reserved_other + remaining_after > allocation.quantity_base:
                    raise ConflictError("La devolución supera la cantidad entregada aún disponible.", code="sales_return_quantity_no_longer_available")

            for line, payload in data_by_id.values():
                destination_id = payload.get("destination_location_id")
                if payload["decision"] == "accepted":
                    location = await self.session.scalar(
                        select(Location).join(Warehouse, Warehouse.id == Location.warehouse_id).where(
                            Location.id == destination_id,
                            Location.warehouse_id == line.source_warehouse_id,
                            Warehouse.company_id == company_id,
                            Warehouse.is_active.is_(True),
                            Warehouse.is_transit.is_(False),
                            Warehouse.operational_status == "active",
                            Warehouse.deleted_at.is_(None),
                            Location.is_active.is_(True),
                            Location.lifecycle_status == "active",
                            Location.location_type != "virtual",
                            Location.deleted_at.is_(None),
                        )
                    )
                    if location is None:
                        raise ValidationError("Seleccione una ubicación activa de la bodega de origen.", code="sales_return_location_invalid")
                    source_unit = await self.session.scalar(select(InventoryHandlingUnitModel).where(
                        InventoryHandlingUnitModel.company_id == company_id,
                        InventoryHandlingUnitModel.id == line.source_handling_unit_id,
                    ))
                    if source_unit is None:
                        raise ConflictError("No se puede recuperar el empaque y lote de la entrega original.", code="sales_return_source_unit_missing")
                    event_id = uuid.uuid4()
                    movement = await self.inventory.post_movement(
                        company_id=company_id,
                        idempotency_key=f"return:{return_id.hex}:{event_id.hex}",
                        movement_type="receipt",
                        source_reference=f"customer-return:{document.code}",
                        actor_id=actor_id,
                        lines=[{
                            "inventory_item_id": line.inventory_item_id,
                            "handling_unit_code": f"HU-RET-{uuid.uuid4().hex[:16].upper()}",
                            "inventory_lot_id": source_unit.inventory_lot_id,
                            "inventory_lot_detail_id": line.inventory_lot_detail_id,
                            "packaging_definition_id": source_unit.packaging_definition_id,
                            "lot_code": line.lot_code,
                            "expiry_date": line.expiry_date,
                            "to_location_id": destination_id,
                            "to_stock_status": "quarantine",
                            "quantity_base": payload["quantity_base"],
                            "valuation_kind": "customer_return",
                            "valuation_original_entry_id": line.source_valuation_entry_id,
                        }],
                    )
                    movement_line = movement["lines"][0]
                    valuation_entry = await self.session.scalar(select(InventoryValuationEntryModel).where(
                        InventoryValuationEntryModel.company_id == company_id,
                        InventoryValuationEntryModel.movement_line_id == movement_line["id"],
                    ))
                    if valuation_entry is None:
                        raise ConflictError("El motor no generó la entrada de valoración de la devolución.", code="sales_return_valuation_missing")
                    self.session.add(SalesReturnEventModel(
                        id=event_id,
                        company_id=company_id,
                        return_id=return_id,
                        return_line_id=line.id,
                        decision="accepted",
                        quantity_base=payload["quantity_base"],
                        condition=payload["condition"],
                        reason=payload["reason"].strip(),
                        destination_location_id=destination_id,
                        movement_id=movement["id"],
                        movement_line_id=movement_line["id"],
                        valuation_entry_id=valuation_entry.id,
                        actor_id=actor_id,
                        created_at=datetime.now(UTC),
                    ))
                else:
                    self.session.add(SalesReturnEventModel(
                        id=uuid.uuid4(),
                        company_id=company_id,
                        return_id=return_id,
                        return_line_id=line.id,
                        decision="rejected",
                        quantity_base=payload["quantity_base"],
                        condition=payload["condition"],
                        reason=payload["reason"].strip(),
                        destination_location_id=None,
                        movement_id=None,
                        movement_line_id=None,
                        valuation_entry_id=None,
                        actor_id=actor_id,
                        created_at=datetime.now(UTC),
                    ))
            await self.session.flush()
            await self._refresh_status(document)
            document.updated_by_id = actor_id
            self.session.add(self._command_row(company_id, "resolve", idempotency_key, digest, return_id, actor_id))
            await self.session.flush()
            await self._audit(
                action="SALES_RETURN_RESOLVED",
                actor_id=actor_id,
                company_id=company_id,
                branch_id=sale.branch_id,
                return_id=return_id,
                request=request,
                before={"status": prior_status},
                after={"status": document.status, "event_count": len(data_by_id)},
            )
        return await self.return_out(company_id, return_id)

    async def _refresh_status(self, document: SalesReturnModel) -> None:
        line_ids = list((await self.session.scalars(select(SalesReturnLineModel.id).where(
            SalesReturnLineModel.company_id == document.company_id,
            SalesReturnLineModel.return_id == document.id,
        ))).all())
        resolved = Decimal("0")
        accepted = False
        rejected = False
        if line_ids:
            rows = (await self.session.execute(select(
                SalesReturnEventModel.decision,
                func.sum(SalesReturnEventModel.quantity_base),
            ).where(
                SalesReturnEventModel.company_id == document.company_id,
                SalesReturnEventModel.return_line_id.in_(line_ids),
            ).group_by(SalesReturnEventModel.decision))).all()
            for decision, quantity in rows:
                resolved += Decimal(quantity or ZERO)
                accepted = accepted or decision == "accepted"
                rejected = rejected or decision == "rejected"
        received_value = await self.session.scalar(
            select(func.sum(SalesReturnLineModel.quantity_received_base)).where(
                SalesReturnLineModel.company_id == document.company_id,
                SalesReturnLineModel.return_id == document.id,
            )
        )
        received = Decimal(received_value or ZERO)
        if resolved < received:
            document.status = "under_review"
        elif accepted and rejected:
            document.status = "mixed"
        elif accepted:
            document.status = "accepted"
        else:
            document.status = "rejected"

    async def list_for_sale(self, company_id: uuid.UUID, sale_id: uuid.UUID) -> list[dict[str, Any]]:
        await self._sale(company_id, sale_id)
        rows = list((await self.session.scalars(select(SalesReturnModel).where(
            SalesReturnModel.company_id == company_id,
            SalesReturnModel.sale_id == sale_id,
        ).order_by(SalesReturnModel.created_at.desc(), SalesReturnModel.id))).all())
        return [await self.return_out(company_id, row.id) for row in rows]

    async def list_all(self, company_id: uuid.UUID, *, branch_ids: tuple[uuid.UUID, ...] | None = None) -> list[dict[str, Any]]:
        statement = select(SalesReturnModel).where(SalesReturnModel.company_id == company_id)
        if branch_ids is not None:
            if not branch_ids:
                return []
            statement = statement.where(SalesReturnModel.branch_id.in_(branch_ids))
        rows = list((await self.session.scalars(statement.order_by(SalesReturnModel.created_at.desc(), SalesReturnModel.id))).all())
        return [await self.return_out(company_id, row.id) for row in rows]

    async def return_out(self, company_id: uuid.UUID, return_id: uuid.UUID) -> dict[str, Any]:
        document = await self._return(company_id, return_id)
        lines = list((await self.session.scalars(select(SalesReturnLineModel).where(
            SalesReturnLineModel.company_id == company_id,
            SalesReturnLineModel.return_id == return_id,
        ).order_by(SalesReturnLineModel.line_number))).all())
        usage = await self._allocation_usage(company_id, {line.delivery_allocation_id for line in lines})
        evidence_rows = (await self.session.execute(
            select(SalesReturnDocumentModel.document_id, DocumentRecordModel.title, DocumentAssetModel.original_filename)
            .join(DocumentRecordModel, DocumentRecordModel.id == SalesReturnDocumentModel.document_id)
            .join(DocumentAssetModel, DocumentAssetModel.id == DocumentRecordModel.id)
            .where(
                SalesReturnDocumentModel.company_id == company_id,
                SalesReturnDocumentModel.return_id == return_id,
            )
            .order_by(SalesReturnDocumentModel.attached_at, SalesReturnDocumentModel.document_id)
        )).all()
        output_lines = []
        for line in lines:
            events = list((await self.session.scalars(select(SalesReturnEventModel).where(
                SalesReturnEventModel.company_id == company_id,
                SalesReturnEventModel.return_line_id == line.id,
            ).order_by(SalesReturnEventModel.created_at, SalesReturnEventModel.id))).all())
            accepted = sum((event.quantity_base for event in events if event.decision == "accepted"), ZERO)
            rejected = sum((event.quantity_base for event in events if event.decision == "rejected"), ZERO)
            delivered_back, reserved = usage[line.delivery_allocation_id]
            allocation = await self.session.get(SalesDeliveryAllocationModel, line.delivery_allocation_id)
            output_lines.append({
                "id": line.id,
                "delivery_id": line.delivery_id,
                "delivery_code": (await self.session.get(SalesDeliveryModel, line.delivery_id)).code,
                "delivery_allocation_id": line.delivery_allocation_id,
                "source_handling_unit_id": line.source_handling_unit_id,
                "inventory_item_id": line.inventory_item_id,
                "product_sku": line.product_sku,
                "product_name": line.product_name,
                "unit_name": line.unit_name,
                "base_unit_name": line.base_unit_name,
                "lot_code": line.lot_code,
                "quantity_received_base": line.quantity_received_base,
                "quantity_accepted_base": accepted,
                "quantity_rejected_base": rejected,
                "quantity_pending_base": line.quantity_received_base - accepted - rejected,
                "quantity_returnable_base": max((allocation.quantity_base if allocation else ZERO) - delivered_back - reserved, ZERO),
                "reason": line.reason,
                "declared_condition": line.declared_condition,
                "events": [{
                    "id": event.id,
                    "decision": event.decision,
                    "quantity_base": event.quantity_base,
                    "condition": event.condition,
                    "reason": event.reason,
                    "destination_location_id": event.destination_location_id,
                    "movement_id": event.movement_id,
                    "movement_line_id": event.movement_line_id,
                    "valuation_entry_id": event.valuation_entry_id,
                    "actor_id": event.actor_id,
                    "created_at": event.created_at,
                } for event in events],
            })
        return {
            "id": document.id,
            "company_id": document.company_id,
            "branch_id": document.branch_id,
            "sale_id": document.sale_id,
            "code": document.code,
            "status": document.status,
            "notes": document.notes,
            "created_by_id": document.created_by_id,
            "received_by_id": document.received_by_id,
            "received_at": document.received_at,
            "cancelled_at": document.cancelled_at,
            "cancellation_reason": document.cancellation_reason,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
            "evidence": [
                {"document_id": document_id, "title": title, "file_name": file_name}
                for document_id, title, file_name in evidence_rows
            ],
            "lines": output_lines,
        }


__all__ = ["SalesReturnService"]
