from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, NoReturn
from zoneinfo import ZoneInfo

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.inventory import InventoryUseCases
from app.domain.entities.inventory_adjustment import InventoryAdjustmentError
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel, UnitModel
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.inventory import (
    InventoryHandlingUnitModel,
    InventoryItemModel,
    InventoryMovementLineModel,
    InventoryMovementModel,
    InventoryPackagingModel,
)
from app.infrastructure.models.inventory_adjustment import (
    InventoryAdjustmentDetailModel,
    InventoryAdjustmentDocumentModel,
    InventoryAdjustmentEventModel,
    InventoryAdjustmentModel,
)
from app.infrastructure.models.inventory_transfer import (
    InventoryTransferCommandModel,
    InventoryTransferDemandAllocationModel,
    InventoryTransferDetailModel,
    InventoryTransferIncidentModel,
    InventoryTransferModel,
)
from app.infrastructure.models.inventory_valuation import InventoryValuationEntryModel
from app.infrastructure.models.organization import Location, Warehouse
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository

MIN_REASON_LENGTH = 5


def _err(message: str, code: str, status_code: int = 409) -> NoReturn:
    raise InventoryAdjustmentError(message, code=code, status_code=status_code)


class SqlAlchemyInventoryAdjustmentRepository:
    """Company scoped adjustment document and stock application repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_options(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        q: str = "",
        limit: int | None = None,
        offset: int = 0,
        include_items: bool = True,
        include_locations: bool = True,
    ) -> dict[str, Any]:
        """Read catalog pages separately from the warehouse's locations."""
        items: list[dict[str, Any]] = []
        total: int | None = None
        if include_items:
            product_id = func.coalesce(
                InventoryItemModel.product_id, ProductVariantModel.product_id
            )
            name = func.coalesce(
                ProductVariantModel.name_override, ProductModel.name, "Artículo sin nombre"
            )
            sku = func.coalesce(ProductVariantModel.sku, ProductModel.sku)
            statement = (
                select(
                    InventoryItemModel.id,
                    name.label("product_name"),
                    sku.label("sku"),
                    InventoryItemModel.base_unit_id,
                    func.coalesce(CompanyUnitModel.alias, UnitModel.name).label("base_unit_name"),
                    UnitModel.symbol.label("base_unit_symbol"),
                )
                .outerjoin(
                    ProductVariantModel,
                    and_(
                        ProductVariantModel.company_id == InventoryItemModel.company_id,
                        ProductVariantModel.id == InventoryItemModel.variant_id,
                    ),
                )
                .outerjoin(
                    ProductModel,
                    and_(
                        ProductModel.company_id == InventoryItemModel.company_id,
                        ProductModel.id_product == product_id,
                    ),
                )
                .outerjoin(
                    CompanyUnitModel,
                    and_(
                        CompanyUnitModel.company_id == InventoryItemModel.company_id,
                        CompanyUnitModel.unit_id == InventoryItemModel.base_unit_id,
                    ),
                )
                .outerjoin(UnitModel, UnitModel.id_unit == InventoryItemModel.base_unit_id)
                .where(
                    InventoryItemModel.company_id == company_id,
                    InventoryItemModel.is_active.is_(True),
                    product_id.is_not(None),
                )
            )
            accents = str.maketrans("áéíóúüñ", "aeiouun")
            normalized = q.strip().lower().translate(accents)
            searchable_name = func.translate(func.lower(name), "áéíóúüñ", "aeiouun")
            searchable_sku = func.translate(func.lower(sku), "áéíóúüñ", "aeiouun")
            for term in normalized.split():
                statement = statement.where(
                    or_(
                        searchable_name.contains(term, autoescape=True),
                        searchable_sku.contains(term, autoescape=True),
                    )
                )
            if limit is not None or offset > 0:
                total = int(
                    await self._session.scalar(
                        select(func.count()).select_from(statement.subquery())
                    )
                    or 0
                )
            statement = statement.order_by(name, InventoryItemModel.id).offset(offset)
            if limit is not None:
                statement = statement.limit(limit)
            rows = (await self._session.execute(statement)).mappings().all()
            items = [dict(row) for row in rows]
            if total is None:
                total = len(items)
        locations: list[dict[str, Any]] = []
        if include_locations:
            rows = (
                (
                    await self._session.execute(
                        select(Location.id, Location.code, Location.location_type)
                        .join(Warehouse, Warehouse.id == Location.warehouse_id)
                        .where(
                            Warehouse.company_id == company_id,
                            Location.warehouse_id == warehouse_id,
                            Location.is_active.is_(True),
                            Location.deleted_at.is_(None),
                            Location.lifecycle_status == "active",
                            Location.storage_eligible.is_(True),
                        )
                        .order_by(Location.code, Location.id)
                    )
                )
                .mappings()
                .all()
            )
            locations = [dict(row) for row in rows]
        return {"items": items, "items_total": total, "locations": locations}

    async def _event(
        self,
        adjustment: InventoryAdjustmentModel,
        *,
        action: str,
        actor_id: uuid.UUID,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            InventoryAdjustmentEventModel(
                company_id=adjustment.company_id,
                adjustment_id=adjustment.id,
                action=action,
                actor_id=actor_id,
                occurred_at=datetime.now(UTC),
                reason=reason,
                version=adjustment.version,
                details=details or {},
            )
        )

    async def _header(
        self, company_id: uuid.UUID, adjustment_id: uuid.UUID, *, lock: bool = False
    ) -> InventoryAdjustmentModel:
        stmt = select(InventoryAdjustmentModel).where(
            InventoryAdjustmentModel.company_id == company_id,
            InventoryAdjustmentModel.id == adjustment_id,
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        row = await self._session.scalar(stmt)
        if row is None:
            _err("Ajuste no encontrado.", "adjustment_not_found", 404)
        return row

    async def _validate_line(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        line: dict[str, Any],
        transfer_id: uuid.UUID | None,
    ) -> dict[str, Any]:
        item = await self._session.scalar(
            select(InventoryItemModel).where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.id == line["inventory_item_id"],
                InventoryItemModel.is_active.is_(True),
            )
        )
        if item is None:
            _err(
                "El artículo no pertenece a esta empresa o está inactivo.",
                "adjustment_item_not_found",
                404,
            )
        if line["direction"] == "increase":
            return await self._validate_increase_line(company_id, warehouse_id, item, line)
        return await self._validate_decrease_line(company_id, warehouse_id, item, line, transfer_id)

    async def _validate_increase_line(
        self,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        item: InventoryItemModel,
        line: dict[str, Any],
    ) -> dict[str, Any]:
        location = await self._session.scalar(
            select(Location).where(
                Location.id == line["location_id"],
                Location.warehouse_id == warehouse_id,
                Location.is_active.is_(True),
                Location.deleted_at.is_(None),
                Location.lifecycle_status == "active",
            )
        )
        if location is None:
            _err(
                "La ubicación no pertenece a la bodega del ajuste o está inactiva.",
                "adjustment_location_invalid",
            )
        if line.get("inventory_lot_detail_id") is not None:
            from app.infrastructure.models.inventory_lot import InventoryLotDetailModel

            lot = await self._session.scalar(
                select(InventoryLotDetailModel).where(
                    InventoryLotDetailModel.company_id == company_id,
                    InventoryLotDetailModel.id == line["inventory_lot_detail_id"],
                    InventoryLotDetailModel.inventory_item_id == item.id,
                )
            )
            if lot is None:
                _err("El lote no corresponde al artículo del ajuste.", "adjustment_lot_mismatch")
        if line.get("packaging_definition_id") is not None:
            packaging = await self._session.scalar(
                select(InventoryPackagingModel).where(
                    InventoryPackagingModel.company_id == company_id,
                    InventoryPackagingModel.inventory_item_id == item.id,
                    InventoryPackagingModel.id == line["packaging_definition_id"],
                    InventoryPackagingModel.is_current.is_(True),
                    InventoryPackagingModel.is_active.is_(True),
                )
            )
            if packaging is None:
                _err(
                    "La presentación física seleccionada no está vigente para el artículo.",
                    "adjustment_packaging_invalid",
                )
        return line

    async def _validate_decrease_line(
        self,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        item: InventoryItemModel,
        line: dict[str, Any],
        transfer_id: uuid.UUID | None,
    ) -> dict[str, Any]:
        unit = await self._session.scalar(
            select(InventoryHandlingUnitModel)
            .where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.id == line["handling_unit_id"],
                InventoryHandlingUnitModel.inventory_item_id == item.id,
                InventoryHandlingUnitModel.closed_at.is_(None),
            )
            .with_for_update()
        )
        if unit is None:
            _err(
                "La unidad logística no está disponible en esta empresa.",
                "adjustment_handling_unit_not_found",
                404,
            )
        expected_status = (
            "in_transit"
            if transfer_id is not None and line.get("transfer_detail_id") is not None
            else line["stock_status"]
        )
        if unit.location_id != line["location_id"] or unit.stock_status != expected_status:
            _err(
                "La unidad, ubicación o estado cambió desde que se preparó el ajuste.",
                "adjustment_handling_unit_changed",
            )
        if transfer_id is None and unit.warehouse_id != warehouse_id:
            _err(
                "La unidad logística no pertenece a la bodega del ajuste.",
                "adjustment_warehouse_mismatch",
            )
        if Decimal(str(line["quantity_base"])) > Decimal(unit.quantity_base):
            _err(
                "La cantidad de salida supera el saldo de la unidad logística.",
                "adjustment_insufficient_handling_unit",
            )
        transit_link = transfer_id is not None and line.get("transfer_detail_id") is not None
        if unit.stock_status == "in_transit" and not transit_link:
            _err(
                "El tránsito solo se ajusta desde una incidencia autorizada del traslado.",
                "adjustment_transit_requires_incident",
                403,
            )
        if unit.stock_status != "in_transit" and (
            transfer_id is not None or line.get("transfer_detail_id") is not None
        ):
            _err(
                "La línea vinculada al traslado debe apuntar a la unidad en tránsito.",
                "adjustment_transfer_line_invalid",
            )
        line["packaging_definition_id"] = unit.packaging_definition_id
        line["inventory_lot_detail_id"] = unit.inventory_lot_detail_id
        line["line_warehouse_id"] = unit.warehouse_id
        location = await self._session.scalar(
            select(Location).where(
                Location.id == line["location_id"],
                Location.warehouse_id == unit.warehouse_id,
                Location.is_active.is_(True),
                Location.deleted_at.is_(None),
                Location.lifecycle_status == "active",
            )
        )
        if location is None:
            _err("La ubicación de la unidad no es válida.", "adjustment_location_invalid")
        return line

    async def _add_lines(
        self,
        adjustment: InventoryAdjustmentModel,
        lines: list[dict[str, Any]],
        actor_id: uuid.UUID,
    ) -> None:
        for index, source in enumerate(lines, start=1):
            line = dict(source)
            await self._validate_line(
                company_id=adjustment.company_id,
                warehouse_id=adjustment.warehouse_id,
                line=line,
                transfer_id=adjustment.transfer_id,
            )
            documented_unit_cost = line.get("documented_unit_cost")
            documented_total_cost = line.get("documented_total_cost")
            if line["direction"] == "increase":
                quantity = Decimal(str(line["quantity_base"]))
                if documented_unit_cost is not None and documented_total_cost is None:
                    documented_unit_cost = Decimal(str(documented_unit_cost))
                    documented_total_cost = (documented_unit_cost * quantity).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    )
                elif documented_total_cost is not None and documented_unit_cost is None:
                    documented_total_cost = Decimal(str(documented_total_cost))
                    documented_unit_cost = (documented_total_cost / quantity).quantize(
                        Decimal("0.000001"), rounding=ROUND_HALF_UP
                    )
            self._session.add(
                InventoryAdjustmentDetailModel(
                    company_id=adjustment.company_id,
                    adjustment_id=adjustment.id,
                    line_number=index,
                    warehouse_id=line.get("line_warehouse_id", adjustment.warehouse_id),
                    inventory_item_id=line["inventory_item_id"],
                    location_id=line["location_id"],
                    stock_status="in_transit" if adjustment.transfer_id else line["stock_status"],
                    direction=line["direction"],
                    quantity_base=line["quantity_base"],
                    inventory_lot_detail_id=line.get("inventory_lot_detail_id"),
                    handling_unit_id=line.get("handling_unit_id"),
                    packaging_definition_id=line.get("packaging_definition_id"),
                    documented_unit_cost=documented_unit_cost,
                    documented_total_cost=documented_total_cost,
                    actual_gross_weight_kg=line.get("actual_gross_weight_kg"),
                    actual_volume_m3=line.get("actual_volume_m3"),
                    transfer_detail_id=line.get("transfer_detail_id"),
                )
            )
        await self._session.flush()

    async def _view(self, adjustment: InventoryAdjustmentModel) -> dict[str, Any]:
        warehouse = await self._session.scalar(
            select(Warehouse).where(
                Warehouse.company_id == adjustment.company_id,
                Warehouse.id == adjustment.warehouse_id,
            )
        )
        details = list(
            (
                await self._session.scalars(
                    select(InventoryAdjustmentDetailModel)
                    .where(
                        InventoryAdjustmentDetailModel.company_id == adjustment.company_id,
                        InventoryAdjustmentDetailModel.adjustment_id == adjustment.id,
                    )
                    .order_by(InventoryAdjustmentDetailModel.line_number)
                )
            ).all()
        )
        line_outputs = []
        for detail in details:
            item = await self._session.scalar(
                select(InventoryItemModel).where(
                    InventoryItemModel.company_id == adjustment.company_id,
                    InventoryItemModel.id == detail.inventory_item_id,
                )
            )
            product = None
            variant = None
            if item and item.product_id is not None:
                product = await self._session.scalar(
                    select(ProductModel).where(
                        ProductModel.company_id == adjustment.company_id,
                        ProductModel.id_product == item.product_id,
                    )
                )
            elif item and item.variant_id is not None:
                variant = await self._session.scalar(
                    select(ProductVariantModel).where(
                        ProductVariantModel.company_id == adjustment.company_id,
                        ProductVariantModel.id == item.variant_id,
                    )
                )
                if variant:
                    product = await self._session.scalar(
                        select(ProductModel).where(
                            ProductModel.company_id == adjustment.company_id,
                            ProductModel.id_product == variant.product_id,
                        )
                    )
            unit_row = await self._session.execute(
                select(CompanyUnitModel.alias, UnitModel.name, UnitModel.symbol)
                .join(UnitModel, UnitModel.id_unit == CompanyUnitModel.unit_id)
                .where(
                    CompanyUnitModel.company_id == adjustment.company_id,
                    CompanyUnitModel.unit_id == item.base_unit_id if item else false(),
                )
            )
            unit_data = unit_row.one_or_none()
            location = await self._session.scalar(
                select(Location).where(Location.id == detail.location_id)
            )
            hu = (
                await self._session.scalar(
                    select(InventoryHandlingUnitModel).where(
                        InventoryHandlingUnitModel.company_id == adjustment.company_id,
                        InventoryHandlingUnitModel.id == detail.handling_unit_id,
                    )
                )
                if detail.handling_unit_id
                else None
            )
            line_outputs.append(
                {
                    "id": detail.id,
                    "line_number": detail.line_number,
                    "inventory_item_id": detail.inventory_item_id,
                    "product_name": (
                        variant.name_override
                        if variant and variant.name_override
                        else product.name
                        if product
                        else "Artículo no disponible"
                    ),
                    "sku": variant.sku if variant else product.sku if product else None,
                    "base_unit_id": item.base_unit_id if item else None,
                    "base_unit_name": (unit_data.alias or unit_data.name)
                    if unit_data
                    else "Unidad base",
                    "base_unit_symbol": unit_data.symbol if unit_data else None,
                    "warehouse_id": detail.warehouse_id,
                    "location_id": detail.location_id,
                    "location_code": location.code if location else None,
                    "stock_status": detail.stock_status,
                    "direction": detail.direction,
                    "quantity_base": detail.quantity_base,
                    "inventory_lot_detail_id": detail.inventory_lot_detail_id,
                    "handling_unit_id": detail.handling_unit_id,
                    "handling_unit_code": hu.code if hu else None,
                    "packaging_definition_id": detail.packaging_definition_id,
                    "documented_unit_cost": detail.documented_unit_cost,
                    "documented_total_cost": detail.documented_total_cost,
                    "actual_gross_weight_kg": detail.actual_gross_weight_kg,
                    "actual_volume_m3": detail.actual_volume_m3,
                    "transfer_detail_id": detail.transfer_detail_id,
                    "movement_id": detail.movement_id,
                    "movement_line_id": detail.movement_line_id,
                }
            )
        docs = list(
            (
                await self._session.scalars(
                    select(InventoryAdjustmentDocumentModel)
                    .where(
                        InventoryAdjustmentDocumentModel.company_id == adjustment.company_id,
                        InventoryAdjustmentDocumentModel.adjustment_id == adjustment.id,
                    )
                    .order_by(InventoryAdjustmentDocumentModel.linked_at)
                )
            ).all()
        )
        doc_outputs = []
        for link in docs:
            asset = await self._session.scalar(
                select(DocumentAssetModel).where(
                    DocumentAssetModel.company_id == adjustment.company_id,
                    DocumentAssetModel.id == link.document_id,
                )
            )
            doc_outputs.append(
                {
                    "document_id": link.document_id,
                    "original_filename": link.original_filename,
                    "checksum_sha256": link.checksum_sha256,
                    "technical_status": asset.status if asset else "deleted",
                    "upload_completed": link.upload_completed_at is not None,
                    "linked_at": link.linked_at,
                    "detached_at": link.detached_at,
                    "active": link.detached_at is None,
                }
            )
        events = list(
            (
                await self._session.scalars(
                    select(InventoryAdjustmentEventModel)
                    .where(
                        InventoryAdjustmentEventModel.company_id == adjustment.company_id,
                        InventoryAdjustmentEventModel.adjustment_id == adjustment.id,
                    )
                    .order_by(
                        InventoryAdjustmentEventModel.occurred_at, InventoryAdjustmentEventModel.id
                    )
                )
            ).all()
        )
        return {
            "id": adjustment.id,
            "company_id": adjustment.company_id,
            "code": adjustment.code,
            "warehouse_id": adjustment.warehouse_id,
            "warehouse_name": warehouse.name if warehouse else "Bodega no disponible",
            "branch_id": warehouse.branch_id if warehouse else None,
            "operational_date": adjustment.operational_date,
            "accounting_date": adjustment.accounting_date,
            "reason": adjustment.reason,
            "document_reference": adjustment.document_reference,
            "notes": adjustment.notes,
            "status": adjustment.status,
            "version": adjustment.version,
            "approved_version": adjustment.approved_version,
            "correction_of_id": adjustment.correction_of_id,
            "transfer_id": adjustment.transfer_id,
            "transfer_incident_id": adjustment.transfer_incident_id,
            "created_by_id": adjustment.created_by_id,
            "approved_by_id": adjustment.approved_by_id,
            "applied_by_id": adjustment.applied_by_id,
            "created_at": adjustment.created_at,
            "approved_at": adjustment.approved_at,
            "applied_at": adjustment.applied_at,
            "cancellation_reason": adjustment.cancellation_reason,
            "lines": line_outputs,
            "documents": doc_outputs,
            "events": [
                {
                    "action": event.action,
                    "actor_id": event.actor_id,
                    "occurred_at": event.occurred_at,
                    "reason": event.reason,
                    "version": event.version,
                    "details": event.details,
                }
                for event in events
            ],
        }

    async def create_adjustment(
        self,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        operational_date: date,
        accounting_date: date,
        reason: str,
        document_reference: str,
        notes: str | None,
        lines: list[dict[str, Any]],
        idempotency_key: str | None = None,
        correction_of_id: uuid.UUID | None = None,
        transfer_id: uuid.UUID | None = None,
        transfer_incident_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        canonical = {
            "warehouse_id": str(warehouse_id),
            "operational_date": operational_date.isoformat(),
            "accounting_date": accounting_date.isoformat(),
            "reason": reason.strip(),
            "document_reference": document_reference.strip(),
            "notes": notes.strip() if notes else None,
            "lines": lines,
            "correction_of_id": str(correction_of_id) if correction_of_id else None,
            "transfer_id": str(transfer_id) if transfer_id else None,
            "transfer_incident_id": str(transfer_incident_id) if transfer_incident_id else None,
        }
        fingerprint = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        lock_key = f"inventory-adjustment:create:{company_id}:{idempotency_key or uuid.uuid4()}"
        await self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0)))
        )
        if idempotency_key is not None:
            existing = await self._session.scalar(
                select(InventoryAdjustmentModel)
                .where(
                    InventoryAdjustmentModel.company_id == company_id,
                    InventoryAdjustmentModel.create_idempotency_key == idempotency_key,
                )
                .with_for_update()
            )
            if existing is not None:
                if existing.create_fingerprint != fingerprint:
                    _err(
                        "La clave de creación ya se usó con otro contenido.",
                        "adjustment_idempotency_conflict",
                    )
                return await self._view(existing)
        # Serialize the daily code sequence even when different idempotency keys
        # create drafts at the same time. Corrections also have their origin key.
        await self._session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended(f"inventory-adjustment:{company_id}", 0)
                )
            )
        )
        day = (
            datetime.now(UTC).astimezone(ZoneInfo("America/El_Salvador")).date().strftime("%Y%m%d")
        )
        prefix = f"AJ-{day}-"
        last = await self._session.scalar(
            select(func.max(InventoryAdjustmentModel.code)).where(
                InventoryAdjustmentModel.company_id == company_id,
                InventoryAdjustmentModel.code.like(f"{prefix}%"),
            )
        )
        sequence = int(str(last).rsplit("-", 1)[-1]) + 1 if last else 1
        now = datetime.now(UTC)
        adjustment = InventoryAdjustmentModel(
            company_id=company_id,
            code=f"{prefix}{sequence:06d}",
            warehouse_id=warehouse_id,
            operational_date=operational_date,
            accounting_date=accounting_date,
            reason=reason.strip(),
            document_reference=document_reference.strip(),
            notes=notes.strip() if notes else None,
            status="draft",
            version=1,
            correction_of_id=correction_of_id,
            transfer_id=transfer_id,
            transfer_incident_id=transfer_incident_id,
            created_by_id=actor_id,
            created_at=now,
            create_idempotency_key=idempotency_key,
            create_fingerprint=fingerprint if idempotency_key is not None else None,
        )
        self._session.add(adjustment)
        await self._session.flush()
        await self._add_lines(adjustment, lines, actor_id)
        await self._event(
            adjustment, action="created", actor_id=actor_id, details={"line_count": len(lines)}
        )
        return await self._view(adjustment)

    async def update_adjustment(
        self,
        *,
        company_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        actor_id: uuid.UUID,
        operational_date: date,
        accounting_date: date,
        reason: str,
        document_reference: str,
        notes: str | None,
        lines: list[dict[str, Any]],
        approval_revocation_reason: str | None = None,
    ) -> dict[str, Any]:
        adjustment = await self._header(company_id, adjustment_id, lock=True)
        if adjustment.status == "approved":
            if (
                not approval_revocation_reason
                or len(approval_revocation_reason.strip()) < MIN_REASON_LENGTH
            ):
                _err(
                    "Para editar un aprobado indique el motivo de revocación.",
                    "adjustment_approval_revocation_reason_required",
                    422,
                )
            await self._event(
                adjustment,
                action="approval_revoked",
                actor_id=actor_id,
                reason=approval_revocation_reason.strip(),
                details={"approved_version": adjustment.approved_version},
            )
            adjustment.status = "draft"
            adjustment.approved_by_id = None
            adjustment.approved_at = None
            adjustment.approved_version = None
            adjustment.approval_revocation_reason = approval_revocation_reason.strip()
        elif adjustment.status != "draft":
            _err(
                "Solo se puede editar un ajuste en borrador o revocar su aprobación.",
                "adjustment_not_editable",
            )
        if adjustment.transfer_id is not None or adjustment.correction_of_id is not None:
            _err(
                "Los ajustes vinculados a una incidencia o corrección no se editan; cancele el borrador y cree uno nuevo.",
                "adjustment_linked_document_immutable",
            )
        adjustment.version += 1
        adjustment.operational_date = operational_date
        adjustment.accounting_date = accounting_date
        adjustment.reason = reason.strip()
        adjustment.document_reference = document_reference.strip()
        adjustment.notes = notes.strip() if notes else None
        adjustment.updated_at = datetime.now(UTC)
        existing = list(
            (
                await self._session.scalars(
                    select(InventoryAdjustmentDetailModel).where(
                        InventoryAdjustmentDetailModel.company_id == company_id,
                        InventoryAdjustmentDetailModel.adjustment_id == adjustment.id,
                    )
                )
            ).all()
        )
        for row in existing:
            await self._session.delete(row)
        await self._session.flush()
        await self._add_lines(adjustment, lines, actor_id)
        await self._event(
            adjustment, action="updated", actor_id=actor_id, details={"line_count": len(lines)}
        )
        return await self._view(adjustment)

    async def _validate_evidence(
        self, adjustment: InventoryAdjustmentModel
    ) -> list[InventoryAdjustmentDocumentModel]:
        links = list(
            (
                await self._session.scalars(
                    select(InventoryAdjustmentDocumentModel)
                    .where(
                        InventoryAdjustmentDocumentModel.company_id == adjustment.company_id,
                        InventoryAdjustmentDocumentModel.adjustment_id == adjustment.id,
                        InventoryAdjustmentDocumentModel.detached_at.is_(None),
                    )
                    .order_by(InventoryAdjustmentDocumentModel.id)
                    .with_for_update()
                )
            ).all()
        )
        valid = []
        for link in links:
            asset = await self._session.scalar(
                select(DocumentAssetModel)
                .where(
                    DocumentAssetModel.company_id == adjustment.company_id,
                    DocumentAssetModel.id == link.document_id,
                )
                .with_for_update()
            )
            if (
                asset is not None
                and asset.deleted_at is None
                and asset.status == "active"
                and asset.checksum_sha256 == link.checksum_sha256
                and link.upload_completed_at is not None
            ):
                valid.append(link)
        if not valid:
            _err(
                "Adjunte y complete al menos un comprobante activo, validado y de la misma empresa.",
                "adjustment_evidence_required",
                422,
            )
        return valid

    async def approve_adjustment(
        self,
        *,
        company_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        actor_id: uuid.UUID,
        expected_version: int,
    ) -> dict[str, Any]:
        adjustment = await self._header(company_id, adjustment_id, lock=True)
        if adjustment.status != "draft":
            _err("Solo un borrador puede aprobarse.", "adjustment_not_approvable")
        if adjustment.version != expected_version:
            _err(
                "El borrador cambió; actualice la pantalla y vuelva a revisar.",
                "adjustment_version_conflict",
            )
        if not adjustment.reason.strip() or not adjustment.document_reference.strip():
            _err(
                "El motivo y la referencia documental son obligatorios.",
                "adjustment_reason_and_reference_required",
                422,
            )
        lines = list(
            (
                await self._session.scalars(
                    select(InventoryAdjustmentDetailModel).where(
                        InventoryAdjustmentDetailModel.company_id == company_id,
                        InventoryAdjustmentDetailModel.adjustment_id == adjustment.id,
                    )
                )
            ).all()
        )
        if not lines:
            _err("Agregue al menos una línea antes de aprobar.", "adjustment_lines_required", 422)
        await self._validate_evidence(adjustment)
        adjustment.status = "approved"
        adjustment.approved_version = adjustment.version
        adjustment.approved_by_id = actor_id
        adjustment.approved_at = datetime.now(UTC)
        adjustment.updated_at = adjustment.approved_at
        await self._event(
            adjustment,
            action="approved",
            actor_id=actor_id,
            details={"version": adjustment.version},
        )
        await self._session.flush()
        return await self._view(adjustment)

    async def cancel_adjustment(
        self, *, company_id: uuid.UUID, adjustment_id: uuid.UUID, actor_id: uuid.UUID, reason: str
    ) -> dict[str, Any]:
        adjustment = await self._header(company_id, adjustment_id, lock=True)
        if adjustment.status not in {"draft", "approved"}:
            _err("Solo se puede cancelar un ajuste no aplicado.", "adjustment_not_cancellable")
        if len(reason.strip()) < MIN_REASON_LENGTH:
            _err(
                "Indique el motivo de cancelación.", "adjustment_cancellation_reason_required", 422
            )
        adjustment.status = "cancelled"
        adjustment.cancelled_by_id = actor_id
        adjustment.cancelled_at = datetime.now(UTC)
        adjustment.cancellation_reason = reason.strip()
        adjustment.updated_at = adjustment.cancelled_at
        await self._event(adjustment, action="cancelled", actor_id=actor_id, reason=reason.strip())
        await self._session.flush()
        return await self._view(adjustment)

    async def apply_adjustment(
        self,
        *,
        company_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        actor_id: uuid.UUID,
        idempotency_key: str,
    ) -> dict[str, Any]:
        adjustment = await self._header(company_id, adjustment_id, lock=True)
        fingerprint = hashlib.sha256(
            json.dumps(
                {"adjustment": str(adjustment.id), "version": adjustment.version}, sort_keys=True
            ).encode()
        ).hexdigest()
        if adjustment.status == "applied":
            if adjustment.apply_idempotency_key == idempotency_key:
                return await self._view(adjustment)
            _err(
                "El ajuste ya fue aplicado con otra clave de idempotencia.",
                "adjustment_already_applied",
            )
        if adjustment.status != "approved" or adjustment.approved_version != adjustment.version:
            _err("Aplique solo la versión actualmente aprobada.", "adjustment_approval_stale")
        await self._validate_evidence(adjustment)
        lines = list(
            (
                await self._session.scalars(
                    select(InventoryAdjustmentDetailModel)
                    .where(
                        InventoryAdjustmentDetailModel.company_id == company_id,
                        InventoryAdjustmentDetailModel.adjustment_id == adjustment.id,
                    )
                    .order_by(InventoryAdjustmentDetailModel.line_number)
                    .with_for_update()
                )
            ).all()
        )
        if not lines:
            _err("El ajuste no contiene líneas.", "adjustment_lines_required")
        if adjustment.transfer_id:
            await self._lock_transfer_incident(adjustment, lines[0])
        inventory = InventoryUseCases(SqlAlchemyInventoryRepository(self._session))
        movement_refs = []
        for detail in lines:
            quantity = Decimal(detail.quantity_base)
            movement = await self._post_adjustment_movement(
                adjustment=adjustment,
                detail=detail,
                actor_id=actor_id,
                inventory=inventory,
            )
            if not movement.get("lines"):
                _err(
                    "El motor no devolvió la línea de movimiento creada.",
                    "adjustment_movement_missing",
                    500,
                )
            movement_line_out = movement["lines"][0]
            detail.movement_id = movement["id"]
            detail.movement_line_id = movement_line_out["id"]
            movement_refs.append(
                {
                    "line_id": str(detail.id),
                    "movement_id": str(movement["id"]),
                    "movement_line_id": str(movement_line_out["id"]),
                }
            )
            if detail.transfer_detail_id is not None:
                await self._apply_transfer_loss(
                    adjustment, detail, quantity, actor_id, idempotency_key
                )
        adjustment.status = "applied"
        adjustment.applied_by_id = actor_id
        adjustment.applied_at = datetime.now(UTC)
        adjustment.updated_at = adjustment.applied_at
        adjustment.apply_idempotency_key = idempotency_key
        adjustment.apply_fingerprint = fingerprint
        adjustment.applied_movements = movement_refs
        await self._event(
            adjustment, action="applied", actor_id=actor_id, details={"movements": movement_refs}
        )
        await self._session.flush()
        return await self._view(adjustment)

    async def _post_adjustment_movement(
        self,
        *,
        adjustment: InventoryAdjustmentModel,
        detail: InventoryAdjustmentDetailModel,
        actor_id: uuid.UUID,
        inventory: InventoryUseCases,
    ) -> dict[str, Any]:
        quantity = Decimal(detail.quantity_base)
        source_ref = f"adjustment:{adjustment.code}:{detail.line_number}"
        line_key = f"adj:{adjustment.id}:{detail.id}"
        if detail.direction == "increase":
            documented_total = detail.documented_total_cost
            if documented_total is None and detail.documented_unit_cost is not None:
                documented_total = Decimal(detail.documented_unit_cost) * quantity
            movement_line = {
                "inventory_item_id": detail.inventory_item_id,
                "quantity_base": quantity,
                "from_location_id": None,
                "to_location_id": detail.location_id,
                "to_stock_status": "quarantine",
                "inventory_lot_detail_id": detail.inventory_lot_detail_id,
                "packaging_definition_id": detail.packaging_definition_id,
                "actual_measures": (
                    {
                        "gross_weight_kg": detail.actual_gross_weight_kg,
                        "length_m": None,
                        "width_m": None,
                        "height_m": None,
                        "volume_m3": detail.actual_volume_m3,
                    }
                    if detail.actual_gross_weight_kg is not None
                    else None
                ),
                "valuation_kind": "adjustment_in",
                "valuation_value": documented_total,
                "valuation_currency": None,
                "operational_date": adjustment.operational_date,
                "accounting_date": adjustment.accounting_date,
            }
            movement_type = "adjustment_in"
        else:
            if detail.stock_status == "in_transit":
                await self._lock_transfer_incident(adjustment, detail)
            movement_line = {
                "inventory_item_id": detail.inventory_item_id,
                "handling_unit_id": detail.handling_unit_id,
                "quantity_base": quantity,
                "from_location_id": detail.location_id,
                "from_stock_status": detail.stock_status,
                "to_location_id": None,
                "valuation_kind": "adjustment_out",
                "operational_date": adjustment.operational_date,
                "accounting_date": adjustment.accounting_date,
            }
            movement_type = "adjustment_out"
        return await inventory.post_movement(
            company_id=adjustment.company_id,
            idempotency_key=line_key,
            movement_type=movement_type,
            source_reference=source_ref,
            lines=[movement_line],
            actor_id=actor_id,
        )

    async def _lock_transfer_incident(
        self, adjustment: InventoryAdjustmentModel, detail: InventoryAdjustmentDetailModel
    ) -> None:
        if not adjustment.transfer_id or not adjustment.transfer_incident_id:
            _err(
                "La pérdida de tránsito requiere una incidencia vinculada.",
                "adjustment_transit_requires_incident",
                403,
            )
        transfer = await self._session.scalar(
            select(InventoryTransferModel)
            .where(
                InventoryTransferModel.company_id == adjustment.company_id,
                InventoryTransferModel.id == adjustment.transfer_id,
            )
            .with_for_update()
        )
        incident = await self._session.scalar(
            select(InventoryTransferIncidentModel)
            .where(
                InventoryTransferIncidentModel.company_id == adjustment.company_id,
                InventoryTransferIncidentModel.transfer_id == adjustment.transfer_id,
                InventoryTransferIncidentModel.id == adjustment.transfer_incident_id,
            )
            .with_for_update()
        )
        if (
            transfer is None
            or incident is None
            or transfer.status != "incident"
            or incident.status != "open"
        ):
            _err(
                "La incidencia ya se resolvió o el traslado no está en incidencia.",
                "transfer_incident_not_open",
            )
        transfer_detail = await self._session.scalar(
            select(InventoryTransferDetailModel)
            .where(
                InventoryTransferDetailModel.company_id == adjustment.company_id,
                InventoryTransferDetailModel.transfer_id == adjustment.transfer_id,
                InventoryTransferDetailModel.id == detail.transfer_detail_id,
            )
            .with_for_update()
        )
        if (
            transfer_detail is None
            or transfer_detail.transit_handling_unit_id != detail.handling_unit_id
        ):
            _err(
                "La unidad ya no coincide con el detalle real del tránsito.",
                "transfer_transit_unit_mismatch",
            )
        remaining = (
            Decimal(transfer_detail.quantity_dispatched)
            - Decimal(transfer_detail.quantity_received)
            - Decimal(transfer_detail.quantity_returned)
            - Decimal(transfer_detail.quantity_adjusted_out)
        )
        if Decimal(detail.quantity_base) > remaining:
            _err(
                "La cantidad perdida supera el remanente no recibido del traslado.",
                "transfer_adjustment_exceeds_transit",
            )

    async def _apply_transfer_loss(
        self,
        adjustment: InventoryAdjustmentModel,
        detail: InventoryAdjustmentDetailModel,
        quantity: Decimal,
        actor_id: uuid.UUID,
        idempotency_key: str,
    ) -> None:
        await self._lock_transfer_incident(adjustment, detail)
        transfer_detail = await self._session.scalar(
            select(InventoryTransferDetailModel)
            .where(
                InventoryTransferDetailModel.company_id == adjustment.company_id,
                InventoryTransferDetailModel.id == detail.transfer_detail_id,
            )
            .with_for_update()
        )
        if transfer_detail is None:
            _err("Detalle de traslado no encontrado.", "transfer_transit_unit_mismatch")
        transfer_detail.quantity_adjusted_out = (
            Decimal(transfer_detail.quantity_adjusted_out) + quantity
        )
        allocations = list(
            (
                await self._session.scalars(
                    select(InventoryTransferDemandAllocationModel)
                    .where(
                        InventoryTransferDemandAllocationModel.company_id == adjustment.company_id,
                        InventoryTransferDemandAllocationModel.transfer_detail_id
                        == transfer_detail.id,
                    )
                    .order_by(InventoryTransferDemandAllocationModel.id)
                    .with_for_update()
                )
            ).all()
        )
        unallocated = quantity
        for allocation in allocations:
            pending = (
                Decimal(allocation.quantity_dispatched)
                - Decimal(allocation.quantity_received)
                - Decimal(allocation.quantity_adjusted_out)
            )
            amount = min(unallocated, pending)
            if amount > 0:
                allocation.quantity_adjusted_out = (
                    Decimal(allocation.quantity_adjusted_out) + amount
                )
                unallocated -= amount
            if unallocated <= 0:
                break
        remaining = (
            Decimal(transfer_detail.quantity_dispatched)
            - Decimal(transfer_detail.quantity_received)
            - Decimal(transfer_detail.quantity_returned)
            - Decimal(transfer_detail.quantity_adjusted_out)
        )
        if remaining <= 0:
            transfer_detail.transit_handling_unit_id = None
        all_details = list(
            (
                await self._session.scalars(
                    select(InventoryTransferDetailModel)
                    .where(
                        InventoryTransferDetailModel.company_id == adjustment.company_id,
                        InventoryTransferDetailModel.transfer_id == adjustment.transfer_id,
                    )
                    .order_by(InventoryTransferDetailModel.id)
                    .with_for_update()
                )
            ).all()
        )
        all_resolved = all(
            Decimal(row.quantity_dispatched)
            <= Decimal(row.quantity_received)
            + Decimal(row.quantity_returned)
            + Decimal(row.quantity_adjusted_out)
            for row in all_details
        )
        has_loss = any(Decimal(row.quantity_adjusted_out) > 0 for row in all_details)
        incident = await self._session.scalar(
            select(InventoryTransferIncidentModel)
            .where(
                InventoryTransferIncidentModel.company_id == adjustment.company_id,
                InventoryTransferIncidentModel.id == adjustment.transfer_incident_id,
            )
            .with_for_update()
        )
        if all_resolved and has_loss:
            transfer = await self._session.scalar(
                select(InventoryTransferModel)
                .where(
                    InventoryTransferModel.company_id == adjustment.company_id,
                    InventoryTransferModel.id == adjustment.transfer_id,
                )
                .with_for_update()
            )
            if transfer is None or incident is None:
                _err("Incidencia de traslado no encontrada.", "transfer_incident_not_open")
            transfer.status = "closed_with_adjustment"
            incident.status = "resolved"
            incident.resolution = "close_with_adjustment"
            incident.resolution_notes = (
                f"Cierre automático por ajuste autorizado {adjustment.code}."
            )
            incident.resolved_by_id = actor_id
            incident.resolved_at = datetime.now(UTC)
            now = datetime.now(UTC)
            self._session.add(
                InventoryTransferCommandModel(
                    company_id=adjustment.company_id,
                    transfer_id=adjustment.transfer_id,
                    action="resolve_adjustment",
                    idempotency_key=f"adj-loss:{idempotency_key}",
                    request_fingerprint=hashlib.sha256(
                        f"{adjustment.id}:{detail.id}:{quantity}".encode()
                    ).hexdigest(),
                    result={
                        "adjustment_id": str(adjustment.id),
                        "detail_id": str(detail.transfer_detail_id),
                        "quantity_adjusted_out": str(quantity),
                    },
                    actor_id=actor_id,
                    created_at=now,
                )
            )
        await self._session.flush()

    async def create_correction(
        self,
        *,
        company_id: uuid.UUID,
        adjustment_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str,
        document_reference: str,
        operational_date: date,
        accounting_date: date,
    ) -> dict[str, Any]:
        original = await self._header(company_id, adjustment_id, lock=True)
        if original.status != "applied" or original.transfer_id is not None:
            _err(
                "Solo se admite corregir un ajuste ordinario aplicado.",
                "adjustment_correction_not_supported",
            )
        original_lines = list(
            (
                await self._session.scalars(
                    select(InventoryAdjustmentDetailModel)
                    .where(
                        InventoryAdjustmentDetailModel.company_id == company_id,
                        InventoryAdjustmentDetailModel.adjustment_id == original.id,
                    )
                    .order_by(InventoryAdjustmentDetailModel.line_number)
                    .with_for_update()
                )
            ).all()
        )
        if (
            len(original_lines) != 1
            or original_lines[0].direction != "decrease"
            or original_lines[0].movement_line_id is None
        ):
            _err(
                "Solo se admite corregir la cantidad completa de un ajuste ordinario negativo de una línea.",
                "adjustment_correction_shape_not_supported",
            )
        source = original_lines[0]
        source_entry = await self._session.scalar(
            select(InventoryValuationEntryModel)
            .where(
                InventoryValuationEntryModel.company_id == company_id,
                InventoryValuationEntryModel.movement_line_id == source.movement_line_id,
                InventoryValuationEntryModel.kind == "adjustment_out",
            )
            .with_for_update()
        )
        if source_entry is None or source_entry.inventory_delta >= 0:
            _err(
                "No se puede justificar el valor del movimiento original para compensarlo.",
                "adjustment_correction_value_unavailable",
            )
        later = await self._session.scalar(
            select(InventoryValuationEntryModel.id)
            .where(
                InventoryValuationEntryModel.company_id == company_id,
                InventoryValuationEntryModel.inventory_item_id == source.inventory_item_id,
                InventoryValuationEntryModel.sequence > source_entry.sequence,
            )
            .limit(1)
        )
        if later is not None:
            _err(
                "No se puede compensar automáticamente: el artículo tiene movimientos valorizados posteriores.",
                "adjustment_correction_later_operations",
            )
        source_movement = await self._session.scalar(
            select(InventoryMovementModel)
            .join(
                InventoryMovementLineModel,
                and_(
                    InventoryMovementLineModel.company_id == InventoryMovementModel.company_id,
                    InventoryMovementLineModel.movement_id == InventoryMovementModel.id,
                ),
            )
            .where(
                InventoryMovementLineModel.company_id == company_id,
                InventoryMovementLineModel.id == source.movement_line_id,
            )
        )
        if source_movement is None:
            _err(
                "No se encontró el movimiento físico original para respaldar la corrección.",
                "adjustment_correction_movement_unavailable",
            )
        later_physical = await self._session.scalar(
            select(InventoryMovementLineModel.id)
            .join(
                InventoryMovementModel,
                and_(
                    InventoryMovementModel.company_id == InventoryMovementLineModel.company_id,
                    InventoryMovementModel.id == InventoryMovementLineModel.movement_id,
                ),
            )
            .where(
                InventoryMovementLineModel.company_id == company_id,
                InventoryMovementLineModel.inventory_item_id == source.inventory_item_id,
                InventoryMovementLineModel.id != source.movement_line_id,
                or_(
                    InventoryMovementModel.posted_at > source_movement.posted_at,
                    and_(
                        InventoryMovementModel.posted_at == source_movement.posted_at,
                        InventoryMovementModel.id > source_movement.id,
                    ),
                ),
            )
            .limit(1)
        )
        if later_physical is not None:
            _err(
                "No se puede compensar automáticamente: el artículo tiene movimientos físicos posteriores.",
                "adjustment_correction_later_physical_operations",
            )
        unit = await self._session.scalar(
            select(InventoryHandlingUnitModel).where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.id == source.handling_unit_id,
            )
        )
        if unit is None or unit.packaging_definition_id is None:
            _err(
                "La corrección requiere una presentación física vigente para crear una unidad en cuarentena.",
                "adjustment_correction_physical_evidence_required",
            )
        line = {
            "line_number": 1,
            "inventory_item_id": source.inventory_item_id,
            "location_id": source.location_id,
            "direction": "increase",
            "quantity_base": source.quantity_base,
            "stock_status": "quarantine",
            "inventory_lot_detail_id": source.inventory_lot_detail_id,
            "packaging_definition_id": unit.packaging_definition_id,
            "documented_total_cost": abs(Decimal(source_entry.inventory_delta)),
            "documented_unit_cost": None,
        }
        return await self.create_adjustment(
            company_id=company_id,
            actor_id=actor_id,
            warehouse_id=source.warehouse_id,
            operational_date=operational_date,
            accounting_date=accounting_date,
            reason=f"Corrección de {original.code}: {reason.strip()}",
            document_reference=document_reference,
            notes=f"Corrige al ajuste aplicado {original.code}.",
            lines=[line],
            correction_of_id=original.id,
        )

    async def get_adjustment(
        self, company_id: uuid.UUID, adjustment_id: uuid.UUID
    ) -> dict[str, Any] | None:
        row = await self._session.scalar(
            select(InventoryAdjustmentModel).where(
                InventoryAdjustmentModel.company_id == company_id,
                InventoryAdjustmentModel.id == adjustment_id,
            )
        )
        return await self._view(row) if row else None

    async def list_adjustments(
        self,
        *,
        company_id: uuid.UUID,
        warehouse_id: uuid.UUID | None = None,
        allowed_warehouse_ids: list[uuid.UUID] | None = None,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        filters = [InventoryAdjustmentModel.company_id == company_id]
        if warehouse_id:
            filters.append(InventoryAdjustmentModel.warehouse_id == warehouse_id)
        if allowed_warehouse_ids is not None:
            filters.append(
                InventoryAdjustmentModel.warehouse_id.in_(allowed_warehouse_ids)
                if allowed_warehouse_ids
                else false()
            )
        if status:
            filters.append(InventoryAdjustmentModel.status == status)
        if date_from:
            filters.append(InventoryAdjustmentModel.operational_date >= date_from)
        if date_to:
            filters.append(InventoryAdjustmentModel.operational_date <= date_to)
        total = int(
            await self._session.scalar(
                select(func.count(InventoryAdjustmentModel.id)).where(*filters)
            )
            or 0
        )
        rows = list(
            (
                await self._session.scalars(
                    select(InventoryAdjustmentModel)
                    .where(*filters)
                    .order_by(
                        InventoryAdjustmentModel.created_at.desc(), InventoryAdjustmentModel.id
                    )
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return [await self._view(row) for row in rows], total
