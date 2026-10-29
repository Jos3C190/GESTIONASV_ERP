"""Transactional bridge between physical movements and company valuation.

The company lock is acquired before physical locks, including before opening
valuation. This prevents cutover races and concurrent average calculations.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, NoReturn
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.inventory import InventoryOperationError
from app.domain.entities.inventory_valuation import (
    ZERO,
    ValuationEvent,
    adjustment_breakdown,
    amount,
    project,
)
from app.domain.entities.purchase_conversion import PurchaseValuationConversion
from app.domain.entities.retaceo import Retaceo
from app.domain.ports.inventory_valuation import RetaceoAverageComparison
from app.infrastructure.models.inventory import (
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryMovementLineModel,
)
from app.infrastructure.models.inventory_valuation import (
    InventoryCostAverageModel,
    InventoryRetaceoApplicationModel,
    InventoryValuationEntryModel,
    InventoryValuationSettingModel,
)
from app.infrastructure.models.purchase import PurchaseDetailModel, PurchaseModel
from app.infrastructure.models.retaceo import RetaceoModel
from app.infrastructure.models.supplier_master_data import CurrencyModel


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def error(message: str, code: str) -> NoReturn:
    raise InventoryOperationError(message, code=code, status_code=409)


class SqlAlchemyInventoryValuationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def average_comparison(self, retaceo: Retaceo) -> RetaceoAverageComparison:
        from app.infrastructure.repositories.retaceo_average_comparison import compare_average

        return await compare_average(self, retaceo)

    async def lock(self, company_id: uuid.UUID) -> None:
        key = int.from_bytes(
            hashlib.sha256(f"valuation:{company_id}".encode()).digest()[:8], "big", signed=True
        )
        await self.session.execute(select(func.pg_advisory_xact_lock(key)))

    async def settings(self, company_id: uuid.UUID) -> InventoryValuationSettingModel | None:
        return await self.session.get(InventoryValuationSettingModel, company_id)

    async def enabled(self, company_id: uuid.UUID) -> bool:
        return await self.settings(company_id) is not None

    async def receipt_is_valued(self, company_id: uuid.UUID, purchase_id: uuid.UUID) -> bool:
        return (
            await self.session.scalar(
                select(InventoryValuationEntryModel.id)
                .join(
                    PurchaseDetailModel,
                    PurchaseDetailModel.id == InventoryValuationEntryModel.purchase_detail_id,
                )
                .where(
                    InventoryValuationEntryModel.company_id == company_id,
                    InventoryValuationEntryModel.kind == "receipt",
                    PurchaseDetailModel.purchase_id == purchase_id,
                )
                .limit(1)
            )
            is not None
        )

    async def _rows(
        self, company_id: uuid.UUID, item_id: uuid.UUID
    ) -> list[InventoryValuationEntryModel]:
        return list(
            (
                await self.session.scalars(
                    select(InventoryValuationEntryModel)
                    .where(
                        InventoryValuationEntryModel.company_id == company_id,
                        InventoryValuationEntryModel.inventory_item_id == item_id,
                    )
                    .order_by(InventoryValuationEntryModel.sequence)
                )
            ).all()
        )

    @staticmethod
    def _event(row: InventoryValuationEntryModel) -> ValuationEvent:
        return ValuationEvent(
            row.id, row.kind, row.quantity_base, row.source_value, row.original_entry_id
        )

    async def append(
        self,
        *,
        company_id: uuid.UUID,
        item_id: uuid.UUID,
        kind: str,
        quantity: Decimal,
        value: Decimal,
        actor_id: uuid.UUID,
        key: str,
        reference: str,
        original_id: uuid.UUID | None = None,
        movement_line_id: uuid.UUID | None = None,
        purchase_detail_id: uuid.UUID | None = None,
        retaceo_id: uuid.UUID | None = None,
        operational_date: date | None = None,
        accounting_date: date | None = None,
    ) -> InventoryValuationEntryModel:
        await self.lock(company_id)
        if not await self.enabled(company_id):
            error(
                "Registre y apruebe el corte inicial de valoración de la empresa.",
                "valuation_opening_required",
            )
        if not reference.strip():
            error("Indique el documento de origen del valor.", "valuation_reference_required")
        digest = fingerprint(
            [
                item_id,
                kind,
                quantity,
                value,
                reference,
                original_id,
                movement_line_id,
                purchase_detail_id,
                retaceo_id,
                operational_date,
                accounting_date,
            ]
        )
        existing = await self.session.scalar(
            select(InventoryValuationEntryModel).where(
                InventoryValuationEntryModel.company_id == company_id,
                InventoryValuationEntryModel.idempotency_key == key,
            )
        )
        if existing is not None:
            if existing.fingerprint != digest:
                error(
                    "La operación de valoración ya existe con otro contenido.",
                    "valuation_idempotency_conflict",
                )
            return existing
        rows = await self._rows(company_id, item_id)
        events = [self._event(row) for row in rows]
        before = project(events)
        event = ValuationEvent(uuid.uuid4(), kind, quantity, value, original_id)
        after = project([*events, event])
        now = datetime.now(UTC)
        today = now.astimezone(ZoneInfo("America/El_Salvador")).date()
        sequence = (
            await self.session.scalar(
                select(func.max(InventoryValuationEntryModel.sequence)).where(
                    InventoryValuationEntryModel.company_id == company_id,
                )
            )
            or 0
        ) + 1
        breakdown = adjustment_breakdown(events, before, after) if kind == "cost_adjustment" else []
        if kind == "supplier_credit":
            cost = after.costs[original_id]
            breakdown = [
                {
                    "event_id": str(original_id),
                    "kind": "supplier_credit",
                    "credit_net": str(value),
                    "inventory_cost": str(cost),
                    "cost_difference": str(value - cost),
                }
            ]
        sources = {str(source.id): source for source in rows}
        positions = {str(source.id): str(index // 50) for index, source in enumerate(rows)}
        for item in breakdown:
            source = sources.get(item["event_id"])
            if source is not None:
                item["source_reference"] = source.source_reference
                item["sequence"] = str(source.sequence)
                item["ledger_page"] = positions[item["event_id"]]
        row = InventoryValuationEntryModel(
            id=event.id,
            company_id=company_id,
            inventory_item_id=item_id,
            sequence=sequence,
            kind=kind,
            quantity_base=quantity,
            source_value=value,
            original_entry_id=original_id,
            movement_line_id=movement_line_id,
            purchase_detail_id=purchase_detail_id,
            retaceo_id=retaceo_id,
            source_reference=reference,
            idempotency_key=key,
            fingerprint=digest,
            operational_date=operational_date or today,
            accounting_date=accounting_date or operational_date or today,
            posted_at=now,
            posted_by=actor_id,
            inventory_delta=after.value - before.value,
            balance_quantity=after.quantity,
            balance_value=after.value,
            average_unit_cost=after.average,
            cost_breakdown=breakdown,
        )
        self.session.add(row)
        balance = await self.session.get(InventoryCostAverageModel, (company_id, item_id))
        if balance is None:
            balance = InventoryCostAverageModel(company_id=company_id, inventory_item_id=item_id)
            self.session.add(balance)
        balance.quantity_base = after.quantity
        balance.inventory_value = after.value
        balance.average_unit_cost = after.average
        balance.updated_at = now
        await self.session.flush()
        return row

    async def open_valuation(
        self,
        *,
        company_id: uuid.UUID,
        currency: str,
        reference: str,
        lines: list[dict[str, Any]],
        actor_id: uuid.UUID,
        snapshot_fingerprint: str,
    ) -> InventoryValuationSettingModel:
        await self.lock(company_id)
        lines = sorted(lines, key=lambda row: str(row["inventory_item_id"]))
        digest = fingerprint([currency, reference, lines, snapshot_fingerprint])
        existing = await self.settings(company_id)
        if existing is not None:
            if existing.opening_fingerprint != digest:
                error(
                    "La empresa ya tiene un corte de valoración aprobado.", "valuation_already_open"
                )
            return existing
        currency_row = await self.session.get(CurrencyModel, currency)
        if currency_row is None or not currency_row.is_active:
            error("Seleccione una moneda activa del catálogo.", "valuation_currency_invalid")
        pending_retaceos = await self.session.scalar(
            select(func.count())
            .select_from(RetaceoModel)
            .where(
                RetaceoModel.company_id == company_id,
                RetaceoModel.status.in_(["draft", "calculated", "verified"]),
            )
        )
        if pending_retaceos:
            error(
                f"Hay {pending_retaceos} retaceos en proceso. Finalícelos antes de aprobar el saldo inicial y use sus costos en la conciliación.",
                "valuation_opening_pending_retaceos",
            )
        snapshot = await self.physical_snapshot(company_id)
        if fingerprint(snapshot) != snapshot_fingerprint:
            error(
                "Las existencias cambiaron desde el conteo. Actualice el corte antes de aprobar.",
                "valuation_opening_snapshot_changed",
            )
        totals: dict[uuid.UUID, Decimal] = {}
        for row in snapshot:
            item_id = uuid.UUID(row["inventory_item_id"])
            totals[item_id] = totals.get(item_id, ZERO) + Decimal(row["quantity_base"])
        supplied = {row["inventory_item_id"]: row["quantity_base"] for row in lines}
        if len(supplied) != len(lines) or supplied != totals:
            error(
                "El corte debe incluir exactamente todas las existencias actuales, incluida cuarentena y tránsito. Actualice el conteo.",
                "valuation_opening_quantity_mismatch",
            )
        setting = InventoryValuationSettingModel(
            company_id=company_id,
            currency=currency,
            opened_at=datetime.now(UTC),
            opened_by=actor_id,
            opening_reference=reference,
            opening_fingerprint=digest,
            physical_snapshot=snapshot,
        )
        self.session.add(setting)
        await self.session.flush()
        for line in lines:
            await self.append(
                company_id=company_id,
                item_id=line["inventory_item_id"],
                kind="opening",
                quantity=line["quantity_base"],
                value=line["total_cost"],
                actor_id=actor_id,
                key=f"opening:{line['inventory_item_id']}",
                reference=f"{reference} | {line['cost_reference']}",
            )
        return setting

    async def physical_snapshot(self, company_id: uuid.UUID) -> list[dict[str, Any]]:
        balances = list(
            (
                await self.session.scalars(
                    select(InventoryBalanceModel)
                    .where(
                        InventoryBalanceModel.company_id == company_id,
                        InventoryBalanceModel.quantity_base > ZERO,
                    )
                    .order_by(InventoryBalanceModel.id)
                )
            ).all()
        )
        snapshot = []
        for row in balances:
            snapshot.append(
                {
                    "inventory_item_id": str(row.inventory_item_id),
                    "warehouse_id": str(row.warehouse_id),
                    "location_id": str(row.location_id),
                    "stock_status": row.stock_status,
                    "lot_code": row.lot_code,
                    "expiry_date": str(row.expiry_date) if row.expiry_date else None,
                    "quantity_base": str(row.quantity_base),
                }
            )
        return snapshot

    async def post_physical_line(
        self,
        row: InventoryMovementLineModel,
        data: dict[str, Any],
        *,
        movement_type: str,
        reference: str | None,
        actor_id: uuid.UUID,
    ) -> None:
        setting = await self.settings(row.company_id)
        if setting is None:
            if data.get("purchase_detail_id") is None and any(
                data.get(field) is not None
                for field in (
                    "valuation_kind",
                    "valuation_value",
                    "valuation_currency",
                    "valuation_original_entry_id",
                )
            ):
                error(
                    "Apruebe el saldo inicial antes de registrar valores o devoluciones valoradas.",
                    "valuation_opening_required",
                )
            return
        if row.from_location_id is not None and row.to_location_id is not None:
            if row.to_stock_status == "available":
                await self._ensure_retaceo_applied(row)
            # Quarantine, availability, transit and relocation remain part of
            # the same company balance. No purchase or cost is created here.
            return
        inbound = row.from_location_id is None
        default_kind = (
            movement_type
            if movement_type in {"adjustment_in", "adjustment_out"}
            else "receipt"
            if inbound
            else "issue"
        )
        kind = data.get("valuation_kind") or default_kind
        allowed = (
            {"opening", "receipt", "adjustment_in", "customer_return"}
            if inbound
            else {"issue", "adjustment_out", "supplier_return"}
        )
        if kind not in allowed:
            error(
                "El tratamiento del costo no corresponde al movimiento físico.",
                "valuation_movement_mismatch",
            )
        if kind == "opening" and movement_type != "opening":
            error("El saldo inicial requiere su operación dedicada.", "valuation_movement_mismatch")
        if data.get("valuation_currency") not in {None, setting.currency}:
            error(
                "La recepción debe expresarse en la moneda de valoración de la empresa.",
                "valuation_currency_mismatch",
            )
        value = data.get("valuation_value")
        if kind == "adjustment_in" and value is None:
            balance = await self.session.get(
                InventoryCostAverageModel, (row.company_id, row.inventory_item_id)
            )
            if balance is None or balance.quantity_base <= ZERO:
                error(
                    "Sin existencia previa, el ajuste positivo requiere un costo documentado.",
                    "valuation_cost_required",
                )
            value = amount(balance.inventory_value * row.quantity_base / balance.quantity_base)
        if kind in {"opening", "receipt", "adjustment_in"} and value is None:
            error("Indique el costo provisional total de la entrada.", "valuation_cost_required")
        original_id = data.get("valuation_original_entry_id")
        initial_retaceo_id = await self._initial_receipt_retaceo(
            row.company_id, kind, data.get("purchase_detail_id")
        )
        await self.append(
            company_id=row.company_id,
            item_id=row.inventory_item_id,
            kind=kind,
            quantity=row.quantity_base,
            value=Decimal(str(value)) if value is not None else ZERO,
            actor_id=actor_id,
            key=f"movement-line:{row.id}",
            reference=reference or f"inventory-movement:{row.movement_id}",
            movement_line_id=row.id,
            purchase_detail_id=data.get("purchase_detail_id"),
            original_id=original_id,
            retaceo_id=initial_retaceo_id,
            operational_date=data.get("operational_date"),
            accounting_date=data.get("accounting_date"),
        )

    async def _initial_receipt_retaceo(
        self, company_id: uuid.UUID, kind: str, purchase_detail_id: uuid.UUID | None
    ) -> uuid.UUID | None:
        if kind != "receipt" or purchase_detail_id is None:
            return None
        return await self.session.scalar(
            select(RetaceoModel.id)
            .join(
                PurchaseModel,
                (PurchaseModel.id == RetaceoModel.purchase_id)
                & (PurchaseModel.company_id == RetaceoModel.company_id),
            )
            .join(
                PurchaseDetailModel,
                (PurchaseDetailModel.purchase_id == PurchaseModel.id)
                & (PurchaseDetailModel.company_id == PurchaseModel.company_id),
            )
            .where(
                RetaceoModel.company_id == company_id,
                RetaceoModel.status == "closed",
                PurchaseModel.inventory_workflow.in_(["retaceo_before_inventory", "placement_before_inventory"]),
                PurchaseDetailModel.id == purchase_detail_id,
            )
        )

    async def _ensure_retaceo_applied(self, row: InventoryMovementLineModel) -> None:
        # Follow split handling units back to the receipt without attributing
        # the physical lot's cost to company-average issues.
        unit_id = row.handling_unit_id
        seen: set[uuid.UUID] = set()
        while unit_id is not None and unit_id not in seen:
            seen.add(unit_id)
            source = await self.session.scalar(
                select(InventoryValuationEntryModel)
                .join(
                    InventoryMovementLineModel,
                    InventoryMovementLineModel.id == InventoryValuationEntryModel.movement_line_id,
                )
                .where(
                    InventoryValuationEntryModel.company_id == row.company_id,
                    InventoryValuationEntryModel.kind == "receipt",
                    InventoryValuationEntryModel.purchase_detail_id.is_not(None),
                    InventoryMovementLineModel.handling_unit_id == unit_id,
                )
            )
            if source is not None:
                active_retaceo = await self.session.scalar(
                    select(RetaceoModel.id)
                    .join(
                        PurchaseDetailModel,
                        (PurchaseDetailModel.company_id == RetaceoModel.company_id)
                        & (PurchaseDetailModel.purchase_id == RetaceoModel.purchase_id),
                    )
                    .where(
                        RetaceoModel.company_id == row.company_id,
                        RetaceoModel.status != "cancelled",
                        PurchaseDetailModel.id == source.purchase_detail_id,
                    )
                    .limit(1)
                )
                # A receipt with no applicable retaceo is already valued at its
                # purchase cost. Match the readiness policy used by labels.
                if active_retaceo is None:
                    return
                if source.retaceo_id == active_retaceo:
                    initial_application = await self.session.scalar(
                        select(InventoryRetaceoApplicationModel.id).where(
                            InventoryRetaceoApplicationModel.company_id == row.company_id,
                            InventoryRetaceoApplicationModel.retaceo_id == active_retaceo,
                            InventoryRetaceoApplicationModel.summary["mode"].astext
                            == "initial_receipt",
                        )
                    )
                    if initial_application is not None:
                        return
                applied = await self.session.scalar(
                    select(InventoryValuationEntryModel.id).where(
                        InventoryValuationEntryModel.company_id == row.company_id,
                        InventoryValuationEntryModel.original_entry_id == source.id,
                        InventoryValuationEntryModel.kind == "cost_adjustment",
                        InventoryValuationEntryModel.retaceo_id.is_not(None),
                    )
                )
                if applied is None:
                    error(
                        "Aplique el retaceo de esta recepción antes de liberar la mercancía a disponible.",
                        "inventory_retaceo_application_required",
                    )
                return
            unit = await self.session.get(InventoryHandlingUnitModel, unit_id)
            if unit is None or unit.company_id != row.company_id:
                error(
                    "No se pudo verificar el origen de la unidad logística.",
                    "valuation_handling_unit_origin_invalid",
                )
            unit_id = unit.origin_handling_unit_id
        if unit_id is not None:
            error(
                "La cadena de origen de la unidad logística es circular.",
                "valuation_handling_unit_origin_invalid",
            )

    async def _retaceo_conversion(
        self,
        retaceo: Retaceo,
        valuation_currency: str,
    ) -> PurchaseValuationConversion | None:
        if retaceo.currency == valuation_currency:
            return None
        purchase = await self.session.scalar(
            select(PurchaseModel).where(
                PurchaseModel.company_id == retaceo.company_id,
                PurchaseModel.id == retaceo.purchase_id,
            )
        )
        if (
            purchase is None
            or purchase.currency != retaceo.currency
            or not purchase.valuation_conversion
        ):
            error(
                "Esta recepción requiere un tipo de cambio documentado antes de aplicar su retaceo.",
                "purchase_valuation_conversion_required",
            )
        conversion = PurchaseValuationConversion.from_dict(purchase.valuation_conversion)
        if conversion.currency != valuation_currency:
            error(
                "La conversión de la recepción no corresponde a la valoración activa.",
                "purchase_valuation_currency_changed",
            )
        return conversion

    async def apply_retaceo(self, retaceo: Retaceo, actor_id: uuid.UUID) -> None:
        await self.lock(retaceo.company_id)
        setting = await self.settings(retaceo.company_id)
        if setting is None:
            error("Apruebe primero el corte inicial de valoración.", "valuation_opening_required")
        existing = await self.session.scalar(
            select(InventoryRetaceoApplicationModel).where(
                InventoryRetaceoApplicationModel.company_id == retaceo.company_id,
                InventoryRetaceoApplicationModel.purchase_id == retaceo.purchase_id,
            )
        )
        if existing is not None:
            if existing.retaceo_id != retaceo.id:
                error(
                    "Esta recepción ya tiene un retaceo aplicado.",
                    "retaceo_receipt_already_applied",
                )
            return
        conversion = await self._retaceo_conversion(retaceo, setting.currency)
        summary = []
        for detail in retaceo.details:
            rows = list(
                (
                    await self.session.scalars(
                        select(InventoryValuationEntryModel)
                        .where(
                            InventoryValuationEntryModel.company_id == retaceo.company_id,
                            InventoryValuationEntryModel.purchase_detail_id
                            == detail.purchase_detail_id,
                            InventoryValuationEntryModel.kind == "receipt",
                        )
                        .order_by(InventoryValuationEntryModel.sequence)
                    )
                ).all()
            )
            if not rows:
                error(
                    "La recepción es anterior al corte o no tiene costo provisional vinculado. Requiere una regularización documentada del saldo inicial.",
                    "retaceo_receipt_valuation_missing",
                )
            cost_fob = conversion.convert(detail.cost_fob) if conversion else detail.cost_fob
            total_cost = conversion.convert(detail.total_cost) if conversion else detail.total_cost
            original_fob = sum((row.source_value for row in rows), ZERO)
            if original_fob != cost_fob and not retaceo.documents_historical_fob_correction:
                error(
                    "El FOB aceptado no coincide con el costo provisional de la recepción. Revise el origen antes de aplicar.",
                    "retaceo_receipt_cost_mismatch",
                )
            total_quantity = sum((row.quantity_base for row in rows), ZERO)
            remaining = total_cost
            remaining_quantity = total_quantity
            for index, source in enumerate(rows):
                target = (
                    remaining
                    if index == len(rows) - 1
                    else amount(remaining * source.quantity_base / remaining_quantity)
                )
                remaining -= target
                remaining_quantity -= source.quantity_base
                adjustment = await self.append(
                    company_id=retaceo.company_id,
                    item_id=source.inventory_item_id,
                    kind="cost_adjustment",
                    quantity=ZERO,
                    value=target - source.source_value,
                    actor_id=actor_id,
                    key=f"retaceo:{retaceo.id}:{source.id}",
                    reference=retaceo.code,
                    original_id=source.id,
                    retaceo_id=retaceo.id,
                )
                summary.append(
                    {
                        "event_id": str(adjustment.id),
                        "purchase_detail_id": str(detail.purchase_detail_id),
                        "total_adjustment": str(adjustment.source_value),
                        "inventory_adjustment": str(adjustment.inventory_delta),
                        "issue_adjustment": str(
                            adjustment.source_value - adjustment.inventory_delta
                        ),
                        "receipt_fob": str(original_fob),
                        "documented_fob": str(cost_fob),
                        "fob_correction_reason": retaceo.notes
                        if original_fob != cost_fob
                        else None,
                    }
                )
        now = datetime.now(UTC)
        self.session.add(
            InventoryRetaceoApplicationModel(
                company_id=retaceo.company_id,
                retaceo_id=retaceo.id,
                purchase_id=retaceo.purchase_id,
                applied_at=now,
                applied_by=actor_id,
                summary={
                    "currency": setting.currency,
                    "source_currency": retaceo.currency,
                    "conversion": conversion.to_dict() if conversion else None,
                    "lines": summary,
                },
            )
        )
        model = await self.session.get(RetaceoModel, retaceo.id)
        if model is None or model.company_id != retaceo.company_id:
            error("Retaceo no encontrado.", "retaceo_not_found")
        model.applied_at = now
        model.applied_by = actor_id
        await self.session.flush()

    async def balances(self, company_id: uuid.UUID) -> list[InventoryCostAverageModel]:
        return list(
            (
                await self.session.scalars(
                    select(InventoryCostAverageModel)
                    .where(
                        InventoryCostAverageModel.company_id == company_id,
                    )
                    .order_by(InventoryCostAverageModel.inventory_item_id)
                )
            ).all()
        )

    async def ledger(
        self, company_id: uuid.UUID, item_id: uuid.UUID, *, skip: int = 0, limit: int = 100
    ) -> list[InventoryValuationEntryModel]:
        return list(
            (
                await self.session.scalars(
                    select(InventoryValuationEntryModel)
                    .where(
                        InventoryValuationEntryModel.company_id == company_id,
                        InventoryValuationEntryModel.inventory_item_id == item_id,
                    )
                    .order_by(InventoryValuationEntryModel.sequence)
                    .offset(skip)
                    .limit(limit)
                )
            ).all()
        )
