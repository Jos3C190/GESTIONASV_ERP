"""Transactional staging and placement; physical and valued stock commit together."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.domain.entities.inventory_preparation import placement_value
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.models.inventory import InventoryHandlingUnitModel
from app.infrastructure.models.inventory_label_confirmation import InventoryLabelConfirmationModel
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from app.infrastructure.models.inventory_preparation import InventoryPreparationActionModel
from app.infrastructure.models.inventory_trace_capability import InventoryTraceCapabilityModel
from app.infrastructure.models.inventory_valuation import InventoryValuationEntryModel
from app.infrastructure.models.organization import Location
from app.infrastructure.models.purchase import PurchaseModel
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from app.infrastructure.repositories.inventory_valuation_repository import (
    SqlAlchemyInventoryValuationRepository,
)
from app.infrastructure.repositories.purchase_inventory_gateway import (
    SqlAlchemyPurchaseInventoryGateway,
)
from app.infrastructure.repositories.purchase_repository import SqlAlchemyPurchaseRepository


class SqlAlchemyInventoryPreparationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.inventory = SqlAlchemyInventoryRepository(session)

    async def list_pending(
        self,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        search: str = "",
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = [
            InventoryHandlingUnitModel.company_id == company_id,
            InventoryHandlingUnitModel.warehouse_id == warehouse_id,
            InventoryHandlingUnitModel.inventory_posted_at.is_(None),
            InventoryHandlingUnitModel.closed_at.is_(None),
        ]
        if search:
            term = f"%{search}%"
            conditions.append(
                or_(
                    InventoryHandlingUnitModel.code.ilike(term),
                    InventoryHandlingUnitModel.inventory_lot_detail_id.in_(
                        select(InventoryLotDetailModel.id).where(
                            InventoryLotDetailModel.company_id == company_id,
                            InventoryLotDetailModel.code.ilike(term),
                        )
                    ),
                )
            )
        total = await self.session.scalar(
            select(func.count()).select_from(InventoryHandlingUnitModel).where(*conditions)
        )
        units = list(
            await self.session.scalars(
                select(InventoryHandlingUnitModel)
                .where(*conditions)
                .order_by(InventoryHandlingUnitModel.created_at, InventoryHandlingUnitModel.id)
                .offset(skip)
                .limit(limit)
            )
        )
        projected = await self.inventory._handling_units_with_release_metadata(
            company_id=company_id, rows=units
        )
        result = []
        for unit, row in zip(units, projected, strict=True):
            confirmed = await self._label_confirmed(unit)
            phase = (
                "measure"
                if unit.measurement_status != "verified"
                else "place"
                if confirmed
                else "label"
            )
            result.append(
                {
                    **row,
                    "inventory_lot_detail_id": unit.inventory_lot_detail_id,
                    "label_confirmed": confirmed,
                    "phase": phase,
                    "release_requirements": []
                    if phase == "place"
                    else [
                        "measurement_verification_required"
                        if phase == "measure"
                        else "label_confirmation_required"
                    ],
                }
            )
        return result, int(total or 0)

    async def _label_confirmed(self, unit: InventoryHandlingUnitModel) -> bool:
        return (
            await self.session.scalar(
                select(InventoryLabelConfirmationModel.id).where(
                    InventoryLabelConfirmationModel.company_id == unit.company_id,
                    InventoryLabelConfirmationModel.handling_unit_id == unit.id,
                    InventoryLabelConfirmationModel.handling_unit_code == unit.code,
                    InventoryLabelConfirmationModel.label_revision == unit.label_revision,
                    InventoryLabelConfirmationModel.quantity_base == unit.quantity_base,
                )
            )
            is not None
        )

    async def _scan_matches(self, unit: InventoryHandlingUnitModel, scan: str) -> bool:
        detail = await self.session.get(InventoryLotDetailModel, unit.inventory_lot_detail_id)
        if detail is None:
            raise NotFoundError("Detalle de recepción no encontrado.")
        product = await self.session.scalar(
            select(ProductModel)
            .where(
                ProductModel.company_id == unit.company_id,
                ProductModel.id_product == detail.product_id,
            )
            .execution_options(include_deleted=True)
        )
        if product is None:
            raise NotFoundError("Producto de recepción no encontrado.")
        if scan.strip().upper() in {
            value.upper()
            for value in (unit.code, detail.code, product.sku, product.internal_code)
            if value
        }:
            return True
        try:
            parsed = urlsplit(scan.strip())
        except ValueError:
            return False
        if parsed.path.endswith("/inventory/trace") and parsed.fragment:
            token = unquote(parsed.fragment)
            if not token.isascii():
                return False
            return (
                await self.session.scalar(
                    select(InventoryTraceCapabilityModel.id).where(
                        InventoryTraceCapabilityModel.company_id == unit.company_id,
                        InventoryTraceCapabilityModel.handling_unit_id == unit.id,
                        InventoryTraceCapabilityModel.token_digest
                        == hashlib.sha256(token.encode("ascii")).hexdigest(),
                        InventoryTraceCapabilityModel.revoked_at.is_(None),
                    )
                )
                is not None
            )
        return False

    async def execute(
        self,
        *,
        company_id: uuid.UUID,
        unit_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: str,
        command: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        await SqlAlchemyInventoryValuationRepository(self.session).lock(company_id)
        payload = {"unit_id": str(unit_id), "action": action, **command}
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        previous = await self.session.scalar(
            select(InventoryPreparationActionModel).where(
                InventoryPreparationActionModel.company_id == company_id,
                InventoryPreparationActionModel.idempotency_key == command["idempotency_key"],
            )
        )
        if previous:
            if previous.fingerprint != fingerprint:
                raise ConflictError(
                    "La clave ya se usó con otros datos de preparación.",
                    code="preparation_idempotency_conflict",
                )
            return previous.result, False
        unit = await self.session.scalar(
            select(InventoryHandlingUnitModel)
            .where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.id == unit_id,
            )
            .with_for_update()
        )
        if unit is None:
            raise NotFoundError("Unidad de preparación no encontrada.")
        if unit.inventory_posted_at is not None or unit.closed_at is not None:
            raise ConflictError(
                "La unidad ya ingresó o cambió; actualiza los pendientes.",
                code="preparation_unit_changed",
            )
        if not await self._scan_matches(unit, command["unit_scan"]):
            raise ConflictError(
                "El código leído no coincide con la unidad seleccionada.",
                code="preparation_scan_mismatch",
            )
        quantity = Decimal(command["quantity_base"])
        if action == "split":
            result = await self._split(unit, quantity)
        else:
            result = await self._place(unit, quantity, command, actor_id)
        self.session.add(
            InventoryPreparationActionModel(
                company_id=company_id,
                handling_unit_id=unit.id,
                idempotency_key=command["idempotency_key"],
                fingerprint=fingerprint,
                action=action,
                result=result,
                created_by=actor_id,
            )
        )
        await self.session.flush()
        return result, True

    @staticmethod
    def _clear_measurement(unit: InventoryHandlingUnitModel) -> None:
        for field in (
            "actual_gross_weight_kg",
            "actual_length_m",
            "actual_width_m",
            "actual_height_m",
            "actual_volume_m3",
        ):
            setattr(unit, field, None)
        unit.occupied_weight_kg = Decimal("0")
        unit.occupied_volume_m3 = Decimal("0")
        unit.measurement_status = "incomplete"
        unit.measurement_source = "split_estimate"

    async def _split(self, unit: InventoryHandlingUnitModel, quantity: Decimal) -> dict[str, Any]:
        if quantity <= 0 or quantity >= unit.quantity_base:
            raise ConflictError(
                "La porción debe ser menor que la cantidad pendiente.",
                code="preparation_split_quantity",
            )
        child = InventoryHandlingUnitModel(
            company_id=unit.company_id,
            warehouse_id=unit.warehouse_id,
            location_id=unit.location_id,
            inventory_item_id=unit.inventory_item_id,
            inventory_lot_id=unit.inventory_lot_id,
            inventory_lot_detail_id=unit.inventory_lot_detail_id,
            packaging_definition_id=unit.packaging_definition_id,
            origin_handling_unit_id=unit.id,
            code=f"HU-{uuid.uuid4().hex[:16].upper()}",
            quantity_base=quantity,
            lot_code=unit.lot_code,
            expiry_date=unit.expiry_date,
            stock_status="quarantine",
            packaging_snapshot=unit.packaging_snapshot,
            inventory_posted_at=None,
        )
        self._clear_measurement(child)
        self._clear_measurement(unit)
        unit.quantity_base -= quantity
        unit.label_revision += 1
        self.session.add(child)
        await self.session.flush()
        return {
            "action": "split",
            "handling_unit_id": str(unit.id),
            "prepared_unit_id": str(child.id),
            "quantity_base": str(quantity),
            "movement_id": None,
        }

    async def _place(
        self,
        unit: InventoryHandlingUnitModel,
        quantity: Decimal,
        command: dict[str, Any],
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        await self._validate_placement_unit(unit, quantity)
        destination = await self.session.scalar(
            select(Location).where(
                Location.warehouse_id == unit.warehouse_id,
                func.upper(Location.code) == command["location_scan"].strip().upper(),
                Location.is_active.is_(True),
                Location.lifecycle_status == "active",
                Location.storage_eligible.is_(True),
            )
        )
        if destination is None:
            raise ConflictError(
                "La ubicación leída no está activa para almacenamiento en esta bodega.",
                code="preparation_destination_invalid",
            )
        detail = await self.session.scalar(
            select(InventoryLotDetailModel)
            .where(
                InventoryLotDetailModel.company_id == unit.company_id,
                InventoryLotDetailModel.id == unit.inventory_lot_detail_id,
            )
            .with_for_update()
        )
        if detail is None or detail.entry_value is None or detail.entry_currency is None:
            raise ConflictError(
                "La recepción no tiene un costo de ingreso confirmado.",
                code="preparation_cost_required",
            )
        lot = await self.session.get(InventoryLotModel, unit.inventory_lot_id)
        if lot is None:
            raise NotFoundError("Lote de recepción no encontrado.")
        purchase = await SqlAlchemyPurchaseRepository(self.session).get_purchase(
            unit.company_id, lot.purchase_id
        )
        if purchase is None:
            raise NotFoundError("Compra de recepción no encontrada.")
        gateway = SqlAlchemyPurchaseInventoryGateway(self.session)
        retaceo, _ = await gateway._final_receipt_costs(purchase)
        posted_qty, posted_value = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(InventoryValuationEntryModel.quantity_base), 0),
                    func.coalesce(func.sum(InventoryValuationEntryModel.inventory_delta), 0),
                ).where(
                    InventoryValuationEntryModel.company_id == unit.company_id,
                    InventoryValuationEntryModel.purchase_detail_id == detail.purchase_detail_id,
                    InventoryValuationEntryModel.kind == "receipt",
                )
            )
        ).one()
        try:
            value = placement_value(
                total_quantity=detail.accepted_quantity_base,
                total_value=detail.entry_value,
                posted_quantity=posted_qty,
                posted_value=posted_value,
                quantity=quantity,
            )
        except ValueError as exc:
            raise ConflictError(str(exc), code="preparation_cost_inconsistent") from exc
        movement = await self.inventory.post_movement(
            company_id=unit.company_id,
            idempotency_key=f"placement:{hashlib.sha256(command['idempotency_key'].encode()).hexdigest()}",
            movement_type="receipt",
            source_reference=f"purchase-receipt:{purchase.id}",
            actor_id=actor_id,
            receipt_placement=True,
            lines=[
                {
                    "handling_unit_id": unit.id,
                    "inventory_item_id": unit.inventory_item_id,
                    "inventory_lot_id": unit.inventory_lot_id,
                    "inventory_lot_detail_id": detail.id,
                    "packaging_definition_id": unit.packaging_definition_id,
                    "to_location_id": destination.id,
                    "to_stock_status": "available",
                    "quantity_base": quantity,
                    "lot_code": unit.lot_code,
                    "expiry_date": unit.expiry_date,
                    "actual_measures": {
                        "gross_weight_kg": unit.actual_gross_weight_kg,
                        "length_m": None,
                        "width_m": None,
                        "height_m": None,
                        "volume_m3": unit.actual_volume_m3,
                    },
                    "purchase_detail_id": detail.purchase_detail_id,
                    "valuation_currency": detail.entry_currency,
                    "valuation_value": value,
                }
            ],
        )
        await gateway._record_initial_retaceo(
            purchase, retaceo, movement["id"], actor_id, detail.entry_currency, {}
        )
        model = await self.session.get(PurchaseModel, purchase.id)
        if model is None:
            raise NotFoundError("Compra de recepción no encontrada.")
        if model.inventory_movement_id is None:
            model.inventory_movement_id = movement["id"]
        return {
            "action": "place",
            "handling_unit_id": str(unit.id),
            "prepared_unit_id": str(unit.id),
            "quantity_base": str(quantity),
            "movement_id": str(movement["id"]),
        }

    async def _validate_placement_unit(
        self, unit: InventoryHandlingUnitModel, quantity: Decimal
    ) -> None:
        if quantity != unit.quantity_base:
            raise ConflictError(
                "Prepara y etiqueta la porción antes de colocar una cantidad parcial.",
                code="preparation_whole_unit_required",
            )
        if unit.measurement_status != "verified" or not await self._label_confirmed(unit):
            raise ConflictError(
                "Verifica las medidas y confirma la etiqueta colocada antes de ingresar.",
                code="preparation_review_required",
            )
        if (
            unit.expiry_date
            and unit.expiry_date
            < datetime.now(UTC).astimezone(ZoneInfo("America/El_Salvador")).date()
        ):
            raise ConflictError(
                "El lote está vencido y requiere revisión; no se ingresará como disponible.",
                code="preparation_expired",
            )
