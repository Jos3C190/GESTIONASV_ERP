"""Company-scoped inventory label preview and append-only print history."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from typing import cast as type_cast
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.domain.entities.inventory_label import (
    LabelPrintLayout,
    normalize_label_notes,
    print_fingerprint,
    validate_print_reason,
)
from app.domain.entities.purchase import PurchaseInventoryWorkflow
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel, UnitModel
from app.infrastructure.models.inventory import InventoryHandlingUnitModel, InventoryItemModel
from app.infrastructure.models.inventory_label import InventoryLabelPrintModel
from app.infrastructure.models.inventory_label_confirmation import (
    InventoryLabelConfirmationModel,
)
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.models.purchase import PurchaseModel
from app.infrastructure.repositories.retaceo_readiness import purchase_retaceo_readiness_error


def _presentation_equivalence(
    packaging_snapshot: dict[str, Any] | None, quantity_base: Any, base_unit_symbol: str
) -> str | None:
    if not packaging_snapshot:
        return None
    try:
        base_per_package = Decimal(str(packaging_snapshot.get("base_quantity")))
        quantity = Decimal(str(quantity_base))
    except (ArithmeticError, TypeError, ValueError):
        return None
    if base_per_package <= 0 or quantity <= 0:
        return None

    package_name = {
        "piece": "pieza",
        "box": "caja",
        "bag": "saco/bolsa",
        "package": "paquete",
        "roll": "rollo",
        "drum": "tambor",
        "container": "contenedor",
        "loose_other": "unidad de empaque",
    }.get(str(packaging_snapshot.get("packaging_type")), "unidad de empaque")
    package_count = quantity / base_per_package

    def display(value: Decimal) -> str:
        return format(value.normalize(), "f")

    plural = package_name if package_count == Decimal("1") else f"{package_name}s"
    return (
        f"{display(package_count)} {plural} × {display(base_per_package)} {base_unit_symbol}"  # noqa: RUF001
        f" = {display(quantity)} {base_unit_symbol}"
    )


class SqlAlchemyInventoryLabelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_key(
        self, company_id: uuid.UUID, idempotency_key: str
    ) -> InventoryLabelPrintModel | None:
        return type_cast(
            InventoryLabelPrintModel | None,
            await self.session.scalar(
                select(InventoryLabelPrintModel).where(
                    InventoryLabelPrintModel.company_id == company_id,
                    InventoryLabelPrintModel.idempotency_key == idempotency_key,
                )
            ),
        )

    async def preview(
        self,
        *,
        company_id: uuid.UUID,
        inventory_lot_detail_id: uuid.UUID | None = None,
        handling_unit_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        if (inventory_lot_detail_id is None) == (handling_unit_id is None):
            raise ValueError("Seleccione exactamente un destino de etiqueta.")

        target = await self._resolve_target(
            company_id=company_id,
            inventory_lot_detail_id=inventory_lot_detail_id,
            handling_unit_id=handling_unit_id,
        )
        lot = target["lot"]
        item = target["item"]
        product = target["product"]
        variant = target["variant"]
        unit = target["unit"]
        company_unit = target["company_unit"]
        purchase = target["purchase"]

        if not item.is_active:
            raise ConflictError(
                "El producto de inventario está inactivo y no admite nuevas etiquetas.",
                code="inventory_label_item_inactive",
            )
        if purchase.status not in {"verified", "closed"}:
            raise ConflictError(
                "La recepción debe estar verificada antes de imprimir etiquetas.",
                code="inventory_label_receipt_not_verified",
            )
        await self._ensure_retaceo_final(
            company_id,
            lot.purchase_id,
            lot.received_at,
            require_closed=getattr(purchase, "inventory_workflow", None)
            in {PurchaseInventoryWorkflow.AFTER_RETACEO, PurchaseInventoryWorkflow.AFTER_PLACEMENT},
            require_applied=not target.get("pending_entry", False),
        )

        product_code = (
            variant.sku if variant is not None else (product.internal_code or product.sku)
        )
        product_name = variant.name_override if variant and variant.name_override else product.name
        base_unit_symbol = (
            company_unit.alias if company_unit and company_unit.alias else unit.symbol
        )
        received_on = lot.received_at.astimezone(ZoneInfo("America/El_Salvador")).date()
        print_count = int(
            await self.session.scalar(
                select(func.count(InventoryLabelPrintModel.id)).where(
                    InventoryLabelPrintModel.company_id == company_id,
                    target["print_filter"],
                )
            )
            or 0
        )
        current_print = await self._current_label_print(company_id, target)
        label_revision = target.get("label_revision")
        label_confirmed = False
        if unit is not None and target["handling_unit_id"] is not None:
            label_confirmed = (
                await self.session.scalar(
                    select(InventoryLabelConfirmationModel.id).where(
                        InventoryLabelConfirmationModel.company_id == company_id,
                        InventoryLabelConfirmationModel.handling_unit_id
                        == target["handling_unit_id"],
                        InventoryLabelConfirmationModel.handling_unit_code
                        == target["handling_unit_code"],
                        InventoryLabelConfirmationModel.label_revision == label_revision,
                        InventoryLabelConfirmationModel.quantity_base == target["quantity"],
                    )
                )
                is not None
            )
        return {
            "inventory_lot_id": lot.id,
            "inventory_lot_detail_id": target["inventory_lot_detail_id"],
            "handling_unit_id": target["handling_unit_id"],
            "handling_unit_code": target["handling_unit_code"],
            "inventory_item_id": item.id,
            "product_internal_code": product_code,
            "product_name": product_name,
            "receipt_lot_code": target["receipt_lot_code"],
            "receipt_lot_header_code": target["receipt_lot_header_code"],
            "manufacturer_lot_code": target["manufacturer_lot_code"],
            "received_on": received_on,
            "quantity_base": target["quantity"],
            "base_unit_symbol": base_unit_symbol,
            "expiry_date": target["expiry_date"],
            "stock_status": target["stock_status"],
            "print_count": print_count,
            "has_initial_print": print_count > 0,
            "label_revision": label_revision,
            "label_print_id": current_print.id if current_print is not None else None,
            "label_confirmation_required": lot.label_confirmation_required,
            "label_confirmed": label_confirmed,
            "presentation_equivalence": _presentation_equivalence(
                target.get("packaging_snapshot"), target["quantity"], base_unit_symbol
            ),
        }

    async def _resolve_target(
        self,
        *,
        company_id: uuid.UUID,
        inventory_lot_detail_id: uuid.UUID | None,
        handling_unit_id: uuid.UUID | None,
    ) -> dict[str, Any]:
        if inventory_lot_detail_id is not None:
            row = await self._lot_detail_row(company_id, inventory_lot_detail_id)
            if row is None:
                raise NotFoundError("El detalle del lote no existe en esta empresa.")
            lot, detail, item, product, variant, unit, company_unit, purchase = row
            quantity = detail.accepted_quantity_base
            if quantity is None or quantity <= 0:
                raise ConflictError(
                    "El detalle del lote no tiene cantidad aceptada para etiquetar.",
                    code="inventory_label_quantity_unavailable",
                )
            if detail.product_id != product.id_product or detail.base_unit_id != item.base_unit_id:
                raise ConflictError(
                    "El producto o la unidad del detalle no coincide con su artículo de inventario.",
                    code="inventory_label_target_mismatch",
                )
            return {
                "lot": lot,
                "receipt_lot_code": detail.code,
                "receipt_lot_header_code": lot.code,
                "item": item,
                "product": product,
                "variant": variant,
                "unit": unit,
                "company_unit": company_unit,
                "purchase": purchase,
                "quantity": quantity,
                "stock_status": "pending_placement",
                "inventory_lot_detail_id": detail.id,
                "handling_unit_id": None,
                "handling_unit_code": None,
                "manufacturer_lot_code": None,
                "expiry_date": None,
                "packaging_snapshot": None,
                "label_revision": None,
                "pending_entry": purchase.inventory_workflow
                == PurchaseInventoryWorkflow.AFTER_PLACEMENT,
                "print_filter": InventoryLabelPrintModel.inventory_lot_detail_id == detail.id,
            }

        assert handling_unit_id is not None
        row = await self._handling_unit_row(company_id, handling_unit_id)
        if row is None:
            unit_without_receipt_lot = await self.session.scalar(
                select(InventoryHandlingUnitModel.id).where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.id == handling_unit_id,
                    InventoryHandlingUnitModel.inventory_lot_id.is_(None),
                )
            )
            if unit_without_receipt_lot is not None:
                raise ConflictError(
                    "La unidad existe, pero no está vinculada a un lote de recepción y no puede usarse para imprimir una etiqueta de recepción.",
                    code="inventory_label_receipt_lot_required",
                )
            unit_without_line = await self.session.scalar(
                select(InventoryHandlingUnitModel.id).where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.id == handling_unit_id,
                    InventoryHandlingUnitModel.inventory_lot_id.is_not(None),
                    InventoryHandlingUnitModel.inventory_lot_detail_id.is_(None),
                )
            )
            if unit_without_line is not None:
                raise ConflictError(
                    "La unidad conserva la recepción, pero no una línea de producto verificable; no se generará una etiqueta con origen ambiguo.",
                    code="inventory_label_receipt_line_required",
                )
            raise NotFoundError("La unidad logística no existe en esta empresa.")
        lot, handling_unit, detail, item, product, variant, unit, company_unit, purchase = row
        if handling_unit.closed_at is not None or handling_unit.quantity_base <= 0:
            raise ConflictError(
                "La unidad logística está cerrada o ya no tiene cantidad para etiquetar.",
                code="inventory_label_target_closed",
            )
        if handling_unit.stock_status not in {"quarantine", "available"}:
            raise ConflictError(
                "Solo se pueden etiquetar unidades en cuarentena o disponibles.",
                code="inventory_label_target_state_invalid",
            )
        return {
            "lot": lot,
            "receipt_lot_code": detail.code,
            "receipt_lot_header_code": lot.code,
            "item": item,
            "product": product,
            "variant": variant,
            "unit": unit,
            "company_unit": company_unit,
            "purchase": purchase,
            "quantity": handling_unit.quantity_base,
            "stock_status": handling_unit.stock_status,
            "inventory_lot_detail_id": None,
            "handling_unit_id": handling_unit.id,
            "handling_unit_code": handling_unit.code,
            "manufacturer_lot_code": handling_unit.lot_code,
            "expiry_date": handling_unit.expiry_date,
            "packaging_snapshot": handling_unit.packaging_snapshot,
            "label_revision": handling_unit.label_revision,
            "pending_entry": getattr(handling_unit, "inventory_posted_at", True) is None,
            "print_filter": InventoryLabelPrintModel.handling_unit_id == handling_unit.id,
        }

    async def _current_label_print(
        self, company_id: uuid.UUID, target: dict[str, Any]
    ) -> InventoryLabelPrintModel | None:
        prints = list(
            await self.session.scalars(
                select(InventoryLabelPrintModel)
                .where(InventoryLabelPrintModel.company_id == company_id, target["print_filter"])
                .order_by(
                    InventoryLabelPrintModel.printed_at.desc(), InventoryLabelPrintModel.id.desc()
                )
            )
        )
        for entry in prints:
            snapshot = entry.label_snapshot
            if (
                snapshot.get("handling_unit_code") == target["handling_unit_code"]
                and snapshot.get("label_revision") == target.get("label_revision")
                and snapshot.get("quantity_base") == str(target["quantity"])
            ):
                return entry
        return None

    async def register_print(
        self,
        *,
        company_id: uuid.UUID,
        inventory_lot_detail_id: uuid.UUID | None,
        handling_unit_id: uuid.UUID | None,
        idempotency_key: str,
        quantity_printed: int,
        print_date: date,
        reason: str,
        actor_id: uuid.UUID,
        layout: LabelPrintLayout | None = None,
        notes: str | None = None,
    ) -> tuple[InventoryLabelPrintModel, bool]:
        if (inventory_lot_detail_id is None) == (handling_unit_id is None):
            raise ValueError("Seleccione exactamente un destino de etiqueta.")
        target_id = inventory_lot_detail_id or handling_unit_id
        assert target_id is not None
        target_kind = "lot-detail" if inventory_lot_detail_id is not None else "handling-unit"
        from app.infrastructure.repositories.inventory_valuation_repository import (
            SqlAlchemyInventoryValuationRepository,
        )

        await SqlAlchemyInventoryValuationRepository(self.session).lock(company_id)
        await self._lock_target(company_id, target_kind, target_id)

        payload: dict[str, object] = {
            "inventory_lot_detail_id": str(inventory_lot_detail_id)
            if inventory_lot_detail_id
            else None,
            "handling_unit_id": str(handling_unit_id) if handling_unit_id else None,
            "quantity_printed": quantity_printed,
            "print_date": print_date.isoformat(),
            "reason": reason,
        }
        if layout is not None:
            payload["layout"] = layout.to_dict()
        notes = normalize_label_notes(notes)
        if notes:
            payload["notes"] = notes
        fingerprint = print_fingerprint(payload)
        existing = await self.get_by_key(company_id, idempotency_key)
        if existing is not None:
            if existing.fingerprint != fingerprint:
                raise ConflictError(
                    "La clave de impresión ya se usó con otros datos.",
                    code="inventory_label_idempotency_conflict",
                )
            return existing, False

        preview = await self.preview(
            company_id=company_id,
            inventory_lot_detail_id=inventory_lot_detail_id,
            handling_unit_id=handling_unit_id,
        )
        validate_print_reason(reason, int(preview["print_count"]))  # type: ignore[arg-type]
        if layout is not None:
            try:
                layout.validate_product_code(preview["product_internal_code"])
            except ValueError as exc:
                raise ConflictError(str(exc), code="inventory_label_layout_invalid") from exc
        snapshot = {
            "product_internal_code": preview["product_internal_code"],
            "product_name": preview["product_name"],
            "receipt_lot_code": preview["receipt_lot_code"],
            "receipt_lot_header_code": preview["receipt_lot_header_code"],
            "manufacturer_lot_code": preview["manufacturer_lot_code"],
            "received_on": preview["received_on"].isoformat(),
            "quantity_base": str(preview["quantity_base"]),
            "base_unit_symbol": preview["base_unit_symbol"],
            "expiry_date": preview["expiry_date"].isoformat() if preview["expiry_date"] else None,
            "handling_unit_code": preview["handling_unit_code"],
            "label_revision": preview["label_revision"],
            "presentation_equivalence": preview["presentation_equivalence"],
            "stock_status": preview["stock_status"],
        }
        if layout is not None:
            snapshot["print_layout"] = layout.to_dict()
        if notes:
            snapshot["notes"] = notes
        entry = InventoryLabelPrintModel(
            company_id=company_id,
            inventory_item_id=preview["inventory_item_id"],
            inventory_lot_id=preview["inventory_lot_id"],
            inventory_lot_detail_id=inventory_lot_detail_id,
            handling_unit_id=handling_unit_id,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            quantity_printed=quantity_printed,
            print_date=print_date,
            reason=reason,
            label_snapshot=snapshot,
            printed_by=actor_id,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry, True

    async def confirm_handling_unit_label(
        self,
        *,
        company_id: uuid.UUID,
        handling_unit_id: uuid.UUID,
        handling_unit_code: str,
        label_print_id: uuid.UUID,
        idempotency_key: str,
        actor_id: uuid.UUID,
    ) -> tuple[InventoryLabelConfirmationModel, bool]:
        from app.infrastructure.repositories.inventory_valuation_repository import (
            SqlAlchemyInventoryValuationRepository,
        )

        await SqlAlchemyInventoryValuationRepository(self.session).lock(company_id)
        await self._lock_target(company_id, "label-confirmation", handling_unit_id)
        payload: dict[str, object] = {
            "handling_unit_id": str(handling_unit_id),
            "handling_unit_code": handling_unit_code,
            "label_print_id": str(label_print_id),
        }
        request_fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        existing = await self.session.scalar(
            select(InventoryLabelConfirmationModel).where(
                InventoryLabelConfirmationModel.company_id == company_id,
                InventoryLabelConfirmationModel.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.request_fingerprint != request_fingerprint:
                raise ConflictError(
                    "La clave de confirmación ya se usó con otros datos.",
                    code="inventory_label_confirmation_idempotency_conflict",
                )
            return existing, False

        unit = await self.session.scalar(
            select(InventoryHandlingUnitModel)
            .where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.id == handling_unit_id,
            )
            .with_for_update()
        )
        if (
            unit is None
            or unit.closed_at is not None
            or unit.code != handling_unit_code
            or unit.quantity_base <= 0
        ):
            raise ConflictError(
                "La unidad cambió o ya no está disponible; recarga su etiqueta.",
                code="inventory_label_confirmation_unit_changed",
            )

        label_print = await self.session.scalar(
            select(InventoryLabelPrintModel).where(
                InventoryLabelPrintModel.company_id == company_id,
                InventoryLabelPrintModel.id == label_print_id,
                InventoryLabelPrintModel.handling_unit_id == handling_unit_id,
            )
        )
        if label_print is None:
            raise ConflictError(
                "Registra una impresión para la etiqueta vigente antes de confirmar su colocación.",
                code="inventory_label_print_required",
            )
        snapshot = label_print.label_snapshot
        if (
            snapshot.get("handling_unit_code") != unit.code
            or snapshot.get("label_revision") != unit.label_revision
            or snapshot.get("quantity_base") != str(unit.quantity_base)
        ):
            raise ConflictError(
                "La impresión pertenece a una versión anterior de la unidad; vuelve a imprimirla.",
                code="inventory_label_print_stale",
            )

        same_revision = await self.session.scalar(
            select(InventoryLabelConfirmationModel).where(
                InventoryLabelConfirmationModel.company_id == company_id,
                InventoryLabelConfirmationModel.handling_unit_id == handling_unit_id,
                InventoryLabelConfirmationModel.label_revision == unit.label_revision,
            )
        )
        if same_revision is not None:
            if (
                same_revision.handling_unit_code != unit.code
                or same_revision.quantity_base != unit.quantity_base
            ):
                raise ConflictError(
                    "La confirmación guardada no coincide con la versión vigente de la unidad.",
                    code="inventory_label_confirmation_state_conflict",
                )
            return same_revision, False

        label_fingerprint = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        confirmation = InventoryLabelConfirmationModel(
            company_id=company_id,
            handling_unit_id=unit.id,
            label_print_id=label_print.id,
            handling_unit_code=unit.code,
            label_revision=unit.label_revision,
            quantity_base=unit.quantity_base,
            label_fingerprint=label_fingerprint,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            confirmed_by=actor_id,
            confirmed_at=datetime.now(UTC),
        )
        self.session.add(confirmation)
        await self.session.flush()
        return confirmation, True

    async def _lot_detail_row(self, company_id: uuid.UUID, detail_id: uuid.UUID) -> Any:
        # Receipt labels identify persisted stock, even after its product/unit
        # leaves the catalogue. Keep the company/receipt joins and stock checks;
        # this read must not restore catalogue records or rewrite their history.
        return (
            await self.session.execute(
                select(
                    InventoryLotModel,
                    InventoryLotDetailModel,
                    InventoryItemModel,
                    ProductModel,
                    ProductVariantModel,
                    UnitModel,
                    CompanyUnitModel,
                    PurchaseModel,
                )
                .select_from(InventoryLotDetailModel)
                .join(
                    InventoryLotModel,
                    (InventoryLotModel.id == InventoryLotDetailModel.inventory_lot_id)
                    & (InventoryLotModel.company_id == InventoryLotDetailModel.company_id),
                )
                .join(
                    InventoryItemModel,
                    (InventoryItemModel.id == InventoryLotDetailModel.inventory_item_id)
                    & (InventoryItemModel.company_id == InventoryLotDetailModel.company_id),
                )
                .outerjoin(
                    ProductVariantModel,
                    (ProductVariantModel.id == InventoryItemModel.variant_id)
                    & (ProductVariantModel.company_id == InventoryItemModel.company_id),
                )
                .join(
                    ProductModel,
                    (
                        ProductModel.id_product
                        == func.coalesce(
                            InventoryItemModel.product_id, ProductVariantModel.product_id
                        )
                    )
                    & (ProductModel.company_id == InventoryItemModel.company_id),
                )
                .join(UnitModel, UnitModel.id_unit == InventoryItemModel.base_unit_id)
                .outerjoin(
                    CompanyUnitModel,
                    (CompanyUnitModel.company_id == InventoryItemModel.company_id)
                    & (CompanyUnitModel.unit_id == InventoryItemModel.base_unit_id),
                )
                .join(
                    PurchaseModel,
                    (PurchaseModel.id == InventoryLotModel.purchase_id)
                    & (PurchaseModel.company_id == InventoryLotModel.company_id),
                )
                .where(
                    InventoryLotDetailModel.company_id == company_id,
                    InventoryLotDetailModel.id == detail_id,
                )
                .execution_options(include_deleted=True)
            )
        ).one_or_none()

    async def _handling_unit_row(self, company_id: uuid.UUID, handling_unit_id: uuid.UUID) -> Any:
        # Archived catalogue metadata remains the identity of this existing HU.
        # All ownership/receipt relationships are still resolved by persisted ID.
        return (
            await self.session.execute(
                select(
                    InventoryLotModel,
                    InventoryHandlingUnitModel,
                    InventoryLotDetailModel,
                    InventoryItemModel,
                    ProductModel,
                    ProductVariantModel,
                    UnitModel,
                    CompanyUnitModel,
                    PurchaseModel,
                )
                .select_from(InventoryHandlingUnitModel)
                .join(
                    InventoryLotModel,
                    (InventoryLotModel.id == InventoryHandlingUnitModel.inventory_lot_id)
                    & (InventoryLotModel.company_id == InventoryHandlingUnitModel.company_id),
                )
                .join(
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
                .join(
                    InventoryItemModel,
                    (InventoryItemModel.id == InventoryHandlingUnitModel.inventory_item_id)
                    & (InventoryItemModel.company_id == InventoryHandlingUnitModel.company_id),
                )
                .outerjoin(
                    ProductVariantModel,
                    (ProductVariantModel.id == InventoryItemModel.variant_id)
                    & (ProductVariantModel.company_id == InventoryItemModel.company_id),
                )
                .join(
                    ProductModel,
                    (
                        ProductModel.id_product
                        == func.coalesce(
                            InventoryItemModel.product_id, ProductVariantModel.product_id
                        )
                    )
                    & (ProductModel.company_id == InventoryItemModel.company_id),
                )
                .join(UnitModel, UnitModel.id_unit == InventoryItemModel.base_unit_id)
                .outerjoin(
                    CompanyUnitModel,
                    (CompanyUnitModel.company_id == InventoryItemModel.company_id)
                    & (CompanyUnitModel.unit_id == InventoryItemModel.base_unit_id),
                )
                .join(
                    PurchaseModel,
                    (PurchaseModel.id == InventoryLotModel.purchase_id)
                    & (PurchaseModel.company_id == InventoryLotModel.company_id),
                )
                .where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.id == handling_unit_id,
                    InventoryHandlingUnitModel.inventory_lot_id.is_not(None),
                )
                .execution_options(include_deleted=True)
            )
        ).one_or_none()

    async def _ensure_retaceo_final(
        self,
        company_id: uuid.UUID,
        purchase_id: uuid.UUID,
        received_at: datetime,
        *,
        require_closed: bool = False,
        require_applied: bool = True,
    ) -> None:
        readiness_error = await purchase_retaceo_readiness_error(
            self.session,
            company_id=company_id,
            purchase_id=purchase_id,
            received_at=received_at,
            require_closed=require_closed,
            require_applied=require_applied,
        )
        if readiness_error == "not_final":
            raise ConflictError(
                "Verifica y cierra el retaceo vigente antes de imprimir la etiqueta.",
                code="inventory_label_retaceo_not_final",
            )
        if readiness_error == "cost_unapplied":
            raise ConflictError(
                "El retaceo no se ha aplicado al costo del inventario.",
                code="inventory_label_retaceo_cost_unapplied",
            )

    async def _lock_target(
        self, company_id: uuid.UUID, target_kind: str, target_id: uuid.UUID
    ) -> None:
        await self.session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtext(f"inventory-label:{company_id}:{target_kind}:{target_id}")
                )
            )
        )


__all__ = ["SqlAlchemyInventoryLabelRepository"]
