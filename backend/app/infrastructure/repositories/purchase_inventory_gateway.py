"""Bridge verified supplier receipts into the inventory movement ledger."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.inventory import InventoryItem, InventoryOperationError
from app.domain.entities.inventory_valuation import amount
from app.domain.entities.purchase import (
    Purchase,
    PurchaseDetail,
    PurchaseInventoryWorkflow,
    PurchaseVerificationLine,
)
from app.domain.ports.purchase_inventory import PurchaseInventoryGateway, PurchaseReceiptReadiness
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.models.inventory import InventoryHandlingUnitModel
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from app.infrastructure.models.inventory_valuation import (
    InventoryRetaceoApplicationModel,
    InventoryValuationSettingModel,
)
from app.infrastructure.models.organization import Branch, Location, Warehouse
from app.infrastructure.models.retaceo import RetaceoDetailModel, RetaceoModel
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository


def _attach_lot_detail_origins(
    movement_lines: list[dict[str, object]],
    lot_id: uuid.UUID,
    lot_details: list[InventoryLotDetailModel],
) -> None:
    lot_detail_by_purchase_detail = {detail.purchase_detail_id: detail.id for detail in lot_details}
    for movement_line in movement_lines:
        movement_line["inventory_lot_id"] = lot_id
        purchase_detail_id = movement_line["purchase_detail_id"]
        lot_detail_id = lot_detail_by_purchase_detail.get(purchase_detail_id)
        if lot_detail_id is None:
            raise InventoryOperationError(
                "No se pudo vincular la unidad logística con su línea de recepción.",
                code="purchase_receipt_lot_detail_missing",
                status_code=409,
            )
        movement_line["inventory_lot_detail_id"] = lot_detail_id


class SqlAlchemyPurchaseInventoryGateway(PurchaseInventoryGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._inventory = SqlAlchemyInventoryRepository(session)

    async def receipt_readiness(self, purchase: Purchase) -> PurchaseReceiptReadiness:
        if purchase.inventory_workflow is PurchaseInventoryWorkflow.LEGACY:
            return PurchaseReceiptReadiness(required=False, ready=True)
        active = list(
            await self._session.scalars(
                select(RetaceoModel).where(
                    RetaceoModel.company_id == purchase.company_id,
                    RetaceoModel.purchase_id == purchase.id,
                    RetaceoModel.status != "cancelled",
                )
            )
        )
        if len(active) != 1:
            return PurchaseReceiptReadiness(required=True, ready=False)
        item = active[0]
        return PurchaseReceiptReadiness(
            required=True,
            ready=item.status == "closed",
            retaceo_id=item.id,
            retaceo_code=item.code,
            retaceo_status=item.status,
        )

    async def valuation_currency(self, company_id: uuid.UUID) -> str | None:
        return await self._session.scalar(
            select(InventoryValuationSettingModel.currency).where(
                InventoryValuationSettingModel.company_id == company_id,
            )
        )

    async def _receipt_valuation_currency(self, purchase: Purchase) -> str:
        target = await self.valuation_currency(purchase.company_id)
        conversion = purchase.valuation_conversion
        if target is None:
            if conversion is not None:
                raise InventoryOperationError(
                    "Active la valoración antes de documentar una conversión de moneda.",
                    code="valuation_opening_required",
                    status_code=409,
                )
            return purchase.currency
        if target == purchase.currency:
            if conversion is not None:
                raise InventoryOperationError(
                    "La compra y la valoración ya usan la misma moneda; quite la conversión.",
                    code="purchase_valuation_conversion_unnecessary",
                    status_code=409,
                )
            return target
        if conversion is None:
            raise InventoryOperationError(
                f"La compra está en {purchase.currency} y el inventario se valora en {target}. "
                "Registre el tipo de cambio, fecha y referencia en la verificación.",
                code="purchase_valuation_conversion_required",
                status_code=409,
            )
        if conversion.currency != target:
            raise InventoryOperationError(
                "La moneda de valoración cambió; consulte de nuevo la conversión antes de registrar.",
                code="purchase_valuation_currency_changed",
                status_code=409,
            )
        return target

    async def _product_label(self, company_id: uuid.UUID, product_id: int) -> str:
        label = await self._session.scalar(
            select(ProductModel.sku + " — " + ProductModel.name).where(
                ProductModel.company_id == company_id,
                ProductModel.id_product == product_id,
            )
        )
        return label or f"Producto #{product_id}"

    async def _quantity_in_base_unit(
        self,
        *,
        company_id: uuid.UUID,
        product_id: int,
        received_unit_id: int,
        item: InventoryItem,
        accepted_quantity: Decimal,
    ) -> tuple[Decimal, uuid.UUID | None]:
        if item.base_unit_id == received_unit_id:
            return accepted_quantity, None

        conversions = [
            packaging
            for packaging in await self._inventory.list_packaging(company_id, item.id)
            if packaging.packaging_unit_id == received_unit_id
            and packaging.is_current
            and packaging.is_active
        ]
        if not conversions:
            label = await self._product_label(company_id, product_id)
            raise InventoryOperationError(
                f"{label}: falta la equivalencia entre la unidad recibida y la unidad base. "
                "En Productos → Empaques y presentaciones de inventario, registre una "
                "presentación vigente para la unidad de compra. Después vuelva a intentar "
                "la verificación con las mismas cantidades recibidas.",
                code="purchase_receipt_unit_conversion_missing",
                status_code=409,
            )
        if len(conversions) != 1:
            label = await self._product_label(company_id, product_id)
            raise InventoryOperationError(
                f"{label}: hay más de una equivalencia vigente para la unidad recibida. "
                "Revise sus presentaciones en Productos y deje una sola conversión activa.",
                code="purchase_receipt_unit_conversion_ambiguous",
                status_code=409,
            )

        conversion = conversions[0]
        exact_quantity = accepted_quantity * conversion.base_quantity
        quantity_base = exact_quantity.quantize(Decimal("0.000001"))
        if quantity_base != exact_quantity:
            label = await self._product_label(company_id, product_id)
            raise InventoryOperationError(
                f"{label}: la conversión produce más de seis decimales de unidad base. "
                "Revise la equivalencia en Productos → Empaques y presentaciones de inventario.",
                code="purchase_receipt_unit_conversion_precision",
                status_code=409,
            )
        return quantity_base, conversion.id

    async def _get_or_create_receipt_lot(
        self,
        *,
        purchase: Purchase,
        actor_id: uuid.UUID,
        accepted_totals: dict[uuid.UUID, Decimal],
        accepted_base_by_detail: dict[uuid.UUID, Decimal],
        items_by_detail: dict[uuid.UUID, InventoryItem],
        details_by_id: dict[uuid.UUID, PurchaseDetail],
    ) -> InventoryLotModel:
        lot = await self._session.scalar(
            select(InventoryLotModel)
            .where(
                InventoryLotModel.company_id == purchase.company_id,
                InventoryLotModel.purchase_id == purchase.id,
            )
            .with_for_update()
        )
        if lot is None:
            lot = InventoryLotModel(
                company_id=purchase.company_id,
                purchase_id=purchase.id,
                code=f"LOT-{purchase.code}",
                received_at=datetime.now(UTC),
                created_by_id=actor_id,
                label_confirmation_required=True,
            )
            self._session.add(lot)
            await self._session.flush()
            for detail_id, accepted_quantity in accepted_totals.items():
                detail = details_by_id[detail_id]
                item = items_by_detail[detail_id]
                persisted_id = uuid.uuid4()
                self._session.add(
                    InventoryLotDetailModel(
                        id=persisted_id,
                        company_id=purchase.company_id,
                        inventory_lot_id=lot.id,
                        code=f"{lot.code}-D{persisted_id.hex.upper()}",
                        purchase_detail_id=detail_id,
                        inventory_item_id=item.id,
                        product_id=detail.product_id,
                        base_unit_id=item.base_unit_id,
                        quantity_received=detail.quantity_received,
                        quantity_accepted=accepted_quantity,
                        accepted_quantity_base=accepted_base_by_detail[detail_id],
                    )
                )
            await self._session.flush()
            return lot

        persisted_details = list(
            await self._session.scalars(
                select(InventoryLotDetailModel).where(
                    InventoryLotDetailModel.company_id == purchase.company_id,
                    InventoryLotDetailModel.inventory_lot_id == lot.id,
                )
            )
        )
        persisted_by_purchase_detail = {
            detail.purchase_detail_id: detail for detail in persisted_details
        }
        if set(persisted_by_purchase_detail) != set(accepted_totals) or any(
            persisted_by_purchase_detail[detail_id].quantity_accepted != quantity
            or persisted_by_purchase_detail[detail_id].accepted_quantity_base
            != accepted_base_by_detail[detail_id]
            for detail_id, quantity in accepted_totals.items()
        ):
            raise InventoryOperationError(
                "La recepción ya tiene un lote con cantidades distintas a la verificación actual.",
                code="purchase_receipt_lot_conflict",
                status_code=409,
            )
        return lot

    @staticmethod
    def _convert_receipt_values(
        purchase: Purchase, values: dict[uuid.UUID, Decimal]
    ) -> dict[uuid.UUID, Decimal]:
        if purchase.valuation_conversion is None:
            return values
        try:
            return {
                detail_id: purchase.valuation_conversion.convert(value)
                for detail_id, value in values.items()
            }
        except ValueError as exc:
            raise InventoryOperationError(
                str(exc),
                code="purchase_valuation_conversion_invalid",
                status_code=409,
            ) from exc

    async def post_verified_receipt(  # noqa: C901
        self,
        *,
        purchase: Purchase,
        lines: tuple[PurchaseVerificationLine, ...],
        actor_id: uuid.UUID,
    ) -> uuid.UUID | None:
        final_retaceo, final_values = await self._final_receipt_costs(purchase)
        accepted = [line for line in lines if line.quantity_accepted > 0]
        if not accepted:
            if purchase.inventory_workflow is PurchaseInventoryWorkflow.AFTER_PLACEMENT:
                return None
            await self._record_initial_retaceo(
                purchase, final_retaceo, None, actor_id, purchase.currency, {}
            )
            return None

        valuation_currency = await self._receipt_valuation_currency(purchase)

        details_by_id = {detail.id: detail for detail in purchase.details}
        accepted_totals: dict[uuid.UUID, Decimal] = {}
        for verification in accepted:
            detail_id = verification.purchase_detail_id
            accepted_totals[detail_id] = (
                accepted_totals.get(detail_id, Decimal("0")) + verification.quantity_accepted
            )
        remaining_values = {
            detail_id: amount(
                final_values.get(
                    detail_id, details_by_id[detail_id].subtotal - details_by_id[detail_id].discount
                )
                * quantity
                / details_by_id[detail_id].quantity_received
            )
            for detail_id, quantity in accepted_totals.items()
        }
        remaining_values = self._convert_receipt_values(purchase, remaining_values)
        remaining_quantities = dict(accepted_totals)
        movement_lines: list[dict[str, object]] = []
        accepted_base_by_detail: dict[uuid.UUID, Decimal] = {}
        items_by_detail: dict[uuid.UUID, InventoryItem] = {}
        for verification in accepted:
            detail = details_by_id[verification.purchase_detail_id]
            location_id = verification.inventory_location_id
            if location_id is None:
                raise InventoryOperationError(
                    "Seleccione la ubicación de destino para cada cantidad aceptada.",
                    code="purchase_receipt_location_required",
                )

            location_exists = await self._session.scalar(
                select(Location.id)
                .join(Warehouse, Warehouse.id == Location.warehouse_id)
                .outerjoin(
                    Branch,
                    and_(
                        Branch.id == Warehouse.branch_id,
                        Branch.company_id == Warehouse.company_id,
                    ),
                )
                .where(
                    Location.id == location_id,
                    Location.warehouse_id == purchase.warehouse_id,
                    Location.is_active.is_(True),
                    Location.lifecycle_status == "active",
                    Location.deleted_at.is_(None),
                    or_(
                        purchase.inventory_workflow
                        is not PurchaseInventoryWorkflow.AFTER_PLACEMENT,
                        Location.location_type == "receiving",
                    ),
                    Warehouse.is_active.is_(True),
                    Warehouse.operational_status == "active",
                    Warehouse.company_id == purchase.company_id,
                    or_(
                        and_(
                            Warehouse.branch_id == purchase.branch_id,
                            Branch.is_active.is_(True),
                            Branch.operational_status == "active",
                        ),
                        and_(
                            Warehouse.is_central.is_(True),
                            Branch.is_headquarters.is_(True),
                            Branch.is_active.is_(True),
                            Branch.operational_status == "active",
                            Branch.deleted_at.is_(None),
                        ),
                    ),
                )
            )
            if location_exists is None:
                raise InventoryOperationError(
                    "La ubicación debe estar activa y pertenecer al almacén de esta compra.",
                    code="purchase_receipt_location_invalid",
                    status_code=409,
                )

            item = await self._inventory.get_item_by_target(
                company_id=purchase.company_id,
                product_id=detail.product_id,
                variant_id=None,
            )
            if item is None or not item.is_active:
                label = await self._product_label(purchase.company_id, detail.product_id)
                raise InventoryOperationError(
                    f"{label}: falta su configuración activa de inventario. Abra Productos → "
                    "Empaques y presentaciones de inventario y registre la unidad base "
                    "antes de verificar la recepción.",
                    code="purchase_receipt_inventory_item_missing",
                    status_code=409,
                )

            quantity_base, packaging_id = await self._quantity_in_base_unit(
                company_id=purchase.company_id,
                product_id=detail.product_id,
                received_unit_id=detail.unit_id,
                item=item,
                accepted_quantity=verification.quantity_accepted,
            )
            items_by_detail[detail.id] = item
            accepted_base_by_detail[detail.id] = (
                accepted_base_by_detail.get(detail.id, Decimal("0")) + quantity_base
            )

            quantity_left = remaining_quantities[detail.id]
            # Preserve the total accepted FOB exactly when a receipt is split
            # into several handling units (including packaging conversions).
            provisional_cost = (
                remaining_values[detail.id]
                if quantity_left == verification.quantity_accepted
                else amount(
                    remaining_values[detail.id] * verification.quantity_accepted / quantity_left
                )
            )
            remaining_values[detail.id] -= provisional_cost
            remaining_quantities[detail.id] -= verification.quantity_accepted
            movement_lines.append(
                {
                    "inventory_item_id": item.id,
                    "inventory_lot_id": None,
                    "packaging_definition_id": packaging_id,
                    "to_location_id": location_id,
                    "to_stock_status": "quarantine",
                    "quantity_base": quantity_base,
                    "actual_measures": None,
                    "purchase_detail_id": detail.id,
                    "valuation_currency": valuation_currency,
                    "valuation_value": provisional_cost,
                }
            )

        async with self._session.begin_nested():
            lot = await self._get_or_create_receipt_lot(
                purchase=purchase,
                actor_id=actor_id,
                accepted_totals=accepted_totals,
                accepted_base_by_detail=accepted_base_by_detail,
                items_by_detail=items_by_detail,
                details_by_id=details_by_id,
            )

            lot_details = list(
                await self._session.scalars(
                    select(InventoryLotDetailModel).where(
                        InventoryLotDetailModel.company_id == purchase.company_id,
                        InventoryLotDetailModel.inventory_lot_id == lot.id,
                    )
                )
            )
            _attach_lot_detail_origins(movement_lines, lot.id, lot_details)

            if purchase.inventory_workflow is PurchaseInventoryWorkflow.AFTER_PLACEMENT:
                await self._stage_receipt_units(
                    purchase, lot, lot_details, movement_lines, valuation_currency
                )
                return None

            movement = await self._inventory.post_movement(
                company_id=purchase.company_id,
                idempotency_key=f"purchase-receipt:{purchase.id}",
                movement_type="receipt",
                source_reference=f"purchase-receipt:{purchase.id}",
                lines=movement_lines,
                actor_id=actor_id,
            )
            movement_id = movement.get("id")
            if not isinstance(movement_id, uuid.UUID):
                raise InventoryOperationError(
                    "El inventario no devolvió una referencia válida para la recepción.",
                    code="purchase_receipt_movement_invalid",
                    status_code=409,
                )
            posted_at = movement.get("posted_at")
            if isinstance(posted_at, datetime):
                lot.received_at = posted_at
                await self._session.flush()
            await self._record_initial_retaceo(
                purchase, final_retaceo, movement_id, actor_id, valuation_currency, accepted_totals
            )
        return movement_id

    async def _stage_receipt_units(
        self, purchase, lot, lot_details, movement_lines, valuation_currency
    ):
        by_id = {detail.id: detail for detail in lot_details}
        for detail in lot_details:
            detail.entry_value = sum(
                (
                    Decimal(str(line["valuation_value"]))
                    for line in movement_lines
                    if line["inventory_lot_detail_id"] == detail.id
                ),
                Decimal("0"),
            )
            detail.entry_currency = valuation_currency
        for line in movement_lines:
            physical = await self._inventory._resolve_physical(
                company_id=purchase.company_id,
                item_id=line["inventory_item_id"],
                packaging_id=line["packaging_definition_id"],
                quantity_base=line["quantity_base"],
                actual_measures=None,
            )
            detail = by_id[line["inventory_lot_detail_id"]]
            self._session.add(
                InventoryHandlingUnitModel(
                    company_id=purchase.company_id,
                    warehouse_id=purchase.warehouse_id,
                    location_id=line["to_location_id"],
                    inventory_item_id=detail.inventory_item_id,
                    inventory_lot_id=lot.id,
                    inventory_lot_detail_id=detail.id,
                    packaging_definition_id=line["packaging_definition_id"],
                    code=f"HU-{uuid.uuid4().hex[:16].upper()}",
                    quantity_base=line["quantity_base"],
                    lot_code=line.get("lot_code"),
                    expiry_date=line.get("expiry_date"),
                    stock_status="quarantine",
                    measurement_status="complete"
                    if physical.measures.is_complete
                    else "incomplete",
                    measurement_source=physical.source.value,
                    occupied_weight_kg=physical.consumption.weight_kg
                    if physical.consumption
                    else Decimal("0"),
                    occupied_volume_m3=physical.consumption.volume_m3
                    if physical.consumption
                    else Decimal("0"),
                    packaging_snapshot=physical.snapshot,
                    inventory_posted_at=None,
                )
            )
        await self._session.flush()

    async def _final_receipt_costs(
        self,
        purchase: Purchase,
    ) -> tuple[RetaceoModel | None, dict[uuid.UUID, Decimal]]:
        if purchase.inventory_workflow is PurchaseInventoryWorkflow.LEGACY:
            return None, {}
        if await self.valuation_currency(purchase.company_id) is None:
            raise InventoryOperationError(
                "Apruebe el saldo inicial de valoración de la empresa antes de registrar una recepción con el nuevo flujo de retaceo.",
                code="valuation_opening_required",
                status_code=409,
            )
        active = list(
            await self._session.scalars(
                select(RetaceoModel).where(
                    RetaceoModel.company_id == purchase.company_id,
                    RetaceoModel.purchase_id == purchase.id,
                    RetaceoModel.status != "cancelled",
                )
            )
        )
        if len(active) != 1 or active[0].status != "closed":
            raise InventoryOperationError(
                "Cierre el retaceo de esta compra antes de verificar y registrar existencias.",
                code="purchase_receipt_retaceo_required",
                status_code=409,
            )
        retaceo = active[0]
        details = list(
            await self._session.scalars(
                select(RetaceoDetailModel).where(
                    RetaceoDetailModel.company_id == purchase.company_id,
                    RetaceoDetailModel.retaceo_id == retaceo.id,
                )
            )
        )
        sources = {detail.id: detail for detail in purchase.details}
        if {detail.purchase_detail_id for detail in details} != set(sources) or any(
            detail.quantity != sources[detail.purchase_detail_id].quantity_received
            for detail in details
        ):
            raise InventoryOperationError(
                "Las cantidades del retaceo no coinciden con el documento de recepción.",
                code="purchase_retaceo_quantity_mismatch",
                status_code=409,
            )
        return retaceo, {detail.purchase_detail_id: detail.total_cost for detail in details}

    async def _record_initial_retaceo(
        self,
        purchase: Purchase,
        retaceo: RetaceoModel | None,
        movement_id: uuid.UUID | None,
        actor_id: uuid.UUID,
        currency: str,
        accepted: dict[uuid.UUID, Decimal],
    ) -> None:
        if retaceo is None:
            return
        previous = await self._session.scalar(
            select(InventoryRetaceoApplicationModel).where(
                InventoryRetaceoApplicationModel.company_id == purchase.company_id,
                InventoryRetaceoApplicationModel.purchase_id == purchase.id,
            )
        )
        if previous is not None:
            if previous.retaceo_id != retaceo.id:
                raise InventoryOperationError(
                    "La recepción ya tiene otro retaceo aplicado.",
                    code="retaceo_application_conflict",
                    status_code=409,
                )
            return
        applied_at = datetime.now(UTC)
        self._session.add(
            InventoryRetaceoApplicationModel(
                company_id=purchase.company_id,
                purchase_id=purchase.id,
                retaceo_id=retaceo.id,
                applied_at=applied_at,
                applied_by=actor_id,
                summary={
                    "mode": "initial_receipt",
                    "movement_id": str(movement_id) if movement_id else None,
                    "currency": currency,
                    "conversion": purchase.valuation_conversion.to_dict()
                    if purchase.valuation_conversion
                    else None,
                    "accepted_quantities": {
                        str(key): str(value) for key, value in accepted.items()
                    },
                },
            )
        )
        retaceo.applied_at = applied_at
        retaceo.applied_by = actor_id
        await self._session.flush()
