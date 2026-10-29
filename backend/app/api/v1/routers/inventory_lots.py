"""Read receipt-level inventory lots and current physical placement status."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from typing import Any, Literal, TypedDict

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, exists, func, or_, select

from app.api.v1.company_access import (
    authorize_warehouse_assignment,
    effective_company_id,
    require_company_wide_scope,
    resolve_branch_scope,
)
from app.api.v1.deps import CurrentUser, SessionDep, require_permission
from app.api.v1.schemas.inventory_lots import (
    InventoryLotHandlingUnitOut,
    InventoryLotLineOut,
    InventoryLotOut,
    InventoryLotPageOut,
    LegacyInventoryStockOut,
)
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel, UnitModel
from app.infrastructure.models.inventory import (
    InventoryBalanceModel,
    InventoryHandlingUnitModel,
    InventoryItemModel,
)
from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel
from app.infrastructure.models.organization import Location, Warehouse
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.models.purchase import PurchaseModel
from app.infrastructure.models.retaceo import RetaceoModel

router = APIRouter(prefix="/inventory/lots", tags=["inventory"])


class _LotLineData(TypedDict):
    inventory_lot_detail_ids: list[uuid.UUID]
    inventory_lot_detail_id: uuid.UUID
    receipt_lot_detail_code: str
    purchase_detail_id: uuid.UUID
    inventory_item_id: uuid.UUID
    product_sku: str | None
    product_name: str | None
    base_unit_id: int
    base_unit_name: str | None
    base_unit_symbol: str | None
    accepted_quantity_base: Decimal
    placed_quantity_base: Decimal
    pending_placement_quantity_base: Decimal
    handling_units: list[InventoryLotHandlingUnitOut]


def _hu_placement_quantities(
    *,
    quantity: Decimal,
    location_type: str,
    storage_eligible: bool,
    location_active: bool,
) -> tuple[Decimal, Decimal]:
    """Return pending and placed quantities from physical location eligibility.

    Stock status alone does not indicate putaway: split estimates can remain in
    quarantine after reaching a valid storage location.
    """
    pending = quantity if location_type == "receiving" and not storage_eligible else Decimal("0")
    placed = quantity if storage_eligible and location_active else Decimal("0")
    return pending, placed


def _matches_placement_filter(
    requested: Literal["pending_placement", "partially_placed", "placed", "all"],
    actual: Literal["pending_placement", "partially_placed", "placed"],
) -> bool:
    """A pending queue must retain partially placed lots with work remaining."""
    if requested == "all":
        return True
    if requested == "pending_placement":
        return actual in {"pending_placement", "partially_placed"}
    return actual == requested


async def _authorize_scope(
    *,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    warehouse_id: uuid.UUID | None,
    purchase_id: uuid.UUID | None,
) -> uuid.UUID:
    company_id = effective_company_id(request)
    if warehouse_id is not None:
        warehouse = await session.scalar(
            select(Warehouse).where(
                Warehouse.company_id == company_id,
                Warehouse.id == warehouse_id,
                Warehouse.deleted_at.is_(None),
            )
        )
        if warehouse is None:
            raise HTTPException(404, "Bodega no encontrada.")
        if warehouse.branch_id is None:
            raise HTTPException(409, "La bodega aún no está asociada a una sucursal matriz.")
        await resolve_branch_scope(session, current, company_id, warehouse.branch_id)
        await authorize_warehouse_assignment(session, current, company_id, warehouse.id)
        return company_id

    if purchase_id is not None:
        purchase = await session.scalar(
            select(PurchaseModel).where(
                PurchaseModel.company_id == company_id,
                PurchaseModel.id == purchase_id,
            )
        )
        if purchase is None:
            raise HTTPException(404, "Recepción no encontrada.")
        warehouse = await session.scalar(
            select(Warehouse).where(
                Warehouse.company_id == company_id,
                Warehouse.id == purchase.warehouse_id,
            )
        )
        if warehouse is None:
            raise HTTPException(404, "Bodega de recepción no encontrada.")
        if warehouse.branch_id is None:
            raise HTTPException(409, "La bodega aún no está asociada a una sucursal matriz.")
        await resolve_branch_scope(session, current, company_id, warehouse.branch_id)
        await authorize_warehouse_assignment(session, current, company_id, warehouse.id)
        return company_id

    await require_company_wide_scope(session, current, company_id)
    return company_id


def _group_lot_details(
    detail_rows: Sequence[Any],
) -> dict[uuid.UUID, dict[uuid.UUID, _LotLineData]]:
    grouped_lines: dict[uuid.UUID, dict[uuid.UUID, _LotLineData]] = defaultdict(dict)
    for row in detail_rows:
        detail = row.InventoryLotDetailModel
        line = {
            "inventory_lot_detail_ids": [detail.id],
            "inventory_lot_detail_id": detail.id,
            "receipt_lot_detail_code": detail.code,
            "purchase_detail_id": detail.purchase_detail_id,
            "inventory_item_id": detail.inventory_item_id,
            "product_sku": row.product_sku,
            "product_name": row.product_name,
            "base_unit_id": row.base_unit_id,
            "base_unit_name": row.base_unit_name,
            "base_unit_symbol": row.base_unit_symbol,
            "accepted_quantity_base": detail.accepted_quantity_base,
            "placed_quantity_base": Decimal("0"),
            "pending_placement_quantity_base": Decimal("0"),
            "handling_units": [],
        }
        grouped_lines[detail.inventory_lot_id][detail.id] = line
    return grouped_lines


def _add_unit_placement_progress(
    unit_rows: Sequence[Any],
    grouped_lines: dict[uuid.UUID, dict[uuid.UUID, _LotLineData]],
) -> tuple[dict[uuid.UUID, Decimal], dict[uuid.UUID, Decimal]]:
    pending_by_lot: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    placed_by_lot: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    for unit, location in unit_rows:
        # Preparation is a separate operational queue, never existing stock.
        if getattr(unit, "inventory_posted_at", True) is None:
            continue
        line = grouped_lines[unit.inventory_lot_id].get(unit.inventory_lot_detail_id)
        if line is None:
            continue
        pending, placed = _hu_placement_quantities(
            quantity=unit.quantity_base,
            location_type=location.location_type,
            storage_eligible=location.storage_eligible,
            location_active=(
                location.deleted_at is None
                and location.is_active
                and location.lifecycle_status == "active"
            ),
        )
        hu = InventoryLotHandlingUnitOut(
            id=unit.id,
            code=unit.code,
            quantity_base=unit.quantity_base,
            stock_status=unit.stock_status,
            warehouse_id=unit.warehouse_id,
            location_id=unit.location_id,
            location_code=location.code,
            expiry_date=unit.expiry_date,
            lot_code=unit.lot_code,
            measurement_status=unit.measurement_status,
            occupied_weight_kg=(
                unit.occupied_weight_kg if unit.measurement_status != "incomplete" else None
            ),
            occupied_volume_m3=(
                unit.occupied_volume_m3 if unit.measurement_status != "incomplete" else None
            ),
            pending_placement_quantity_base=pending,
            placed_quantity_base=placed,
        )
        line["handling_units"].append(hu)
        line["placed_quantity_base"] += placed
        line["pending_placement_quantity_base"] += pending
        pending_by_lot[unit.inventory_lot_id] += pending
        placed_by_lot[unit.inventory_lot_id] += placed
    return pending_by_lot, placed_by_lot


def _lot_placement_status(
    pending: Decimal, placed: Decimal
) -> Literal["pending_placement", "partially_placed", "placed"]:
    if pending > 0 and placed > 0:
        return "partially_placed"
    if pending > 0:
        return "pending_placement"
    return "placed"


def _build_lot_page(
    *,
    header_rows: Sequence[Any],
    grouped_lines: dict[uuid.UUID, dict[uuid.UUID, _LotLineData]],
    pending_by_lot: dict[uuid.UUID, Decimal],
    placed_by_lot: dict[uuid.UUID, Decimal],
    costing_by_purchase: dict[uuid.UUID, str],
    warehouse_id: uuid.UUID | None,
    status: Literal["pending_placement", "partially_placed", "placed", "all"],
    page: int,
    size: int,
    legacy_stock: list[LegacyInventoryStockOut],
) -> InventoryLotPageOut:
    response_items: list[InventoryLotOut] = []
    for row in header_rows:
        lot = row.InventoryLotModel
        lot_status = _lot_placement_status(pending_by_lot[lot.id], placed_by_lot[lot.id])
        if not _matches_placement_filter(status, lot_status):
            continue
        lot_lines = [InventoryLotLineOut(**line) for line in grouped_lines.get(lot.id, {}).values()]
        response_items.append(
            InventoryLotOut(
                id=lot.id,
                company_id=lot.company_id,
                purchase_id=lot.purchase_id,
                purchase_code=row.purchase_code,
                warehouse_id=warehouse_id or row.purchase_warehouse_id,
                code=lot.code,
                received_at=lot.received_at,
                placement_status=lot_status,
                costing_status=costing_by_purchase.get(lot.purchase_id, "not_started"),
                lines=lot_lines,
            )
        )

    total = len(response_items)
    start = (page - 1) * size
    return InventoryLotPageOut(
        items=response_items[start : start + size],
        page=page,
        size=size,
        total=total,
        legacy_stock=legacy_stock,
    )


async def _legacy_stock_summary(
    session: SessionDep, company_id: uuid.UUID, warehouse_id: uuid.UUID | None
) -> list[LegacyInventoryStockOut]:
    """Reconcile balance projection against explicitly attributable open HUs.

    Inventory balances are the total and are never added to HU quantities. The
    residual is shown as legacy/unattributed; HUs lacking a detail reference are
    reported separately for diagnosis, not used to invent a receipt origin.
    """
    balance_filters = [
        InventoryBalanceModel.company_id == company_id,
        InventoryBalanceModel.quantity_base > 0,
    ]
    hu_filters = [
        InventoryHandlingUnitModel.company_id == company_id,
        InventoryHandlingUnitModel.inventory_posted_at.is_not(None),
        InventoryHandlingUnitModel.closed_at.is_(None),
        InventoryHandlingUnitModel.quantity_base > 0,
    ]
    if warehouse_id is not None:
        balance_filters.append(InventoryBalanceModel.warehouse_id == warehouse_id)
        hu_filters.append(InventoryHandlingUnitModel.warehouse_id == warehouse_id)

    balance_rows = (
        await session.execute(
            select(
                InventoryBalanceModel.warehouse_id,
                InventoryBalanceModel.location_id,
                InventoryBalanceModel.inventory_item_id,
                InventoryBalanceModel.stock_status,
                Location.code.label("location_code"),
                func.sum(InventoryBalanceModel.quantity_base).label("quantity"),
                func.coalesce(ProductVariantModel.sku, ProductModel.sku).label("sku"),
                func.coalesce(ProductVariantModel.name_override, ProductModel.name).label("name"),
                UnitModel.symbol.label("unit_symbol"),
            )
            .join(
                InventoryItemModel,
                and_(
                    InventoryItemModel.company_id == InventoryBalanceModel.company_id,
                    InventoryItemModel.id == InventoryBalanceModel.inventory_item_id,
                ),
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
                    ProductModel.id_product
                    == func.coalesce(InventoryItemModel.product_id, ProductVariantModel.product_id),
                ),
            )
            .outerjoin(UnitModel, UnitModel.id_unit == InventoryItemModel.base_unit_id)
            .join(
                Location,
                and_(
                    Location.id == InventoryBalanceModel.location_id,
                    Location.warehouse_id == InventoryBalanceModel.warehouse_id,
                ),
            )
            .where(*balance_filters)
            .group_by(
                InventoryBalanceModel.warehouse_id,
                InventoryBalanceModel.location_id,
                InventoryBalanceModel.inventory_item_id,
                InventoryBalanceModel.stock_status,
                Location.code,
                ProductVariantModel.sku,
                ProductModel.sku,
                ProductVariantModel.name_override,
                ProductModel.name,
                UnitModel.symbol,
            )
        )
    ).all()
    attributable_rows = (
        await session.execute(
            select(
                InventoryHandlingUnitModel.warehouse_id,
                InventoryHandlingUnitModel.location_id,
                InventoryHandlingUnitModel.inventory_item_id,
                InventoryHandlingUnitModel.stock_status,
                func.sum(InventoryHandlingUnitModel.quantity_base).label("quantity"),
            )
            .where(*hu_filters, InventoryHandlingUnitModel.inventory_lot_detail_id.is_not(None))
            .group_by(
                InventoryHandlingUnitModel.warehouse_id,
                InventoryHandlingUnitModel.location_id,
                InventoryHandlingUnitModel.inventory_item_id,
                InventoryHandlingUnitModel.stock_status,
            )
        )
    ).all()
    legacy_hu_rows = (
        await session.execute(
            select(
                InventoryHandlingUnitModel.warehouse_id,
                InventoryHandlingUnitModel.location_id,
                InventoryHandlingUnitModel.inventory_item_id,
                InventoryHandlingUnitModel.stock_status,
                func.count(InventoryHandlingUnitModel.id).label("unit_count"),
                func.sum(InventoryHandlingUnitModel.quantity_base).label("quantity"),
            )
            .where(*hu_filters, InventoryHandlingUnitModel.inventory_lot_detail_id.is_(None))
            .group_by(
                InventoryHandlingUnitModel.warehouse_id,
                InventoryHandlingUnitModel.location_id,
                InventoryHandlingUnitModel.inventory_item_id,
                InventoryHandlingUnitModel.stock_status,
            )
        )
    ).all()

    def scope_key(row: Any) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, str]:
        return row.warehouse_id, row.location_id, row.inventory_item_id, row.stock_status

    totals = {scope_key(row): (Decimal(str(row.quantity)), row) for row in balance_rows}
    attributable = {scope_key(row): Decimal(str(row.quantity)) for row in attributable_rows}
    legacy_units = {
        scope_key(row): (int(row.unit_count), Decimal(str(row.quantity))) for row in legacy_hu_rows
    }
    rows: list[LegacyInventoryStockOut] = []
    for scope in sorted(
        set(totals) | set(attributable) | set(legacy_units), key=lambda item: tuple(map(str, item))
    ):
        total, balance = totals.get(scope, (Decimal("0"), None))
        identified = attributable.get(scope, Decimal("0"))
        unit_count, unit_quantity = legacy_units.get(scope, (0, Decimal("0")))
        residual = total - identified
        legacy = max(residual, Decimal("0"))
        difference = total - identified - legacy
        if legacy <= 0 and unit_count == 0 and difference == 0:
            continue
        rows.append(
            LegacyInventoryStockOut(
                warehouse_id=scope[0],
                location_id=scope[1],
                inventory_item_id=scope[2],
                location_code=balance.location_code if balance is not None else None,
                product_sku=balance.sku if balance is not None else None,
                product_name=(balance.name or "Producto sin nombre")
                if balance is not None
                else "Producto sin nombre",
                base_unit_symbol=(balance.unit_symbol or "unidad base")
                if balance is not None
                else "unidad base",
                stock_status=scope[3],
                total_quantity_base=total,
                attributable_quantity_base=identified,
                legacy_quantity_base=legacy,
                legacy_handling_unit_count=unit_count,
                legacy_handling_unit_quantity_base=unit_quantity,
                reconciliation_difference=difference,
                reconciled=difference == 0,
            )
        )
    return rows


@router.get(
    "",
    response_model=InventoryLotPageOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_inventory_lots(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    status: Literal["pending_placement", "partially_placed", "placed", "all"] = "pending_placement",
    warehouse_id: uuid.UUID | None = None,
    purchase_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str = Query("", max_length=120),
) -> InventoryLotPageOut:
    company_id = await _authorize_scope(
        request=request,
        session=session,
        current=current,
        warehouse_id=warehouse_id,
        purchase_id=purchase_id,
    )
    legacy_stock = await _legacy_stock_summary(session, company_id, warehouse_id)
    filters = [InventoryLotModel.company_id == company_id]
    if q.strip():
        matching_product = exists(select(InventoryLotDetailModel.id)
            .join(ProductModel, and_(ProductModel.company_id == InventoryLotDetailModel.company_id,
                                    ProductModel.id_product == InventoryLotDetailModel.product_id))
            .where(InventoryLotDetailModel.company_id == company_id,
                   InventoryLotDetailModel.inventory_lot_id == InventoryLotModel.id,
                   or_(ProductModel.name.icontains(q.strip(), autoescape=True),
                       ProductModel.sku.icontains(q.strip(), autoescape=True))))
        filters.append(or_(InventoryLotModel.code.icontains(q.strip(), autoescape=True),
                           PurchaseModel.code.icontains(q.strip(), autoescape=True), matching_product))
    if purchase_id is not None:
        filters.append(InventoryLotModel.purchase_id == purchase_id)
    if warehouse_id is not None:
        has_unit_at_warehouse = exists(
            select(InventoryHandlingUnitModel.id).where(
                InventoryHandlingUnitModel.company_id == company_id,
                InventoryHandlingUnitModel.inventory_lot_id == InventoryLotModel.id,
                InventoryHandlingUnitModel.warehouse_id == warehouse_id,
                InventoryHandlingUnitModel.closed_at.is_(None),
                InventoryHandlingUnitModel.inventory_posted_at.is_not(None),
            )
        )
        filters.append(has_unit_at_warehouse)

    header_rows = (
        await session.execute(
            select(
                InventoryLotModel,
                PurchaseModel.code.label("purchase_code"),
                PurchaseModel.warehouse_id.label("purchase_warehouse_id"),
            )
            .join(
                PurchaseModel,
                and_(
                    PurchaseModel.company_id == InventoryLotModel.company_id,
                    PurchaseModel.id == InventoryLotModel.purchase_id,
                ),
            )
            .where(*filters)
            .order_by(InventoryLotModel.received_at.desc(), InventoryLotModel.id.desc())
        )
    ).all()
    if not header_rows:
        return InventoryLotPageOut(
            items=[], page=page, size=size, total=0, legacy_stock=legacy_stock
        )

    lot_ids = [row.InventoryLotModel.id for row in header_rows]
    purchase_ids = [row.InventoryLotModel.purchase_id for row in header_rows]
    detail_rows = (
        await session.execute(
            select(
                InventoryLotDetailModel,
                InventoryItemModel.base_unit_id.label("base_unit_id"),
                func.coalesce(ProductVariantModel.sku, ProductModel.sku).label("product_sku"),
                func.coalesce(ProductVariantModel.name_override, ProductModel.name).label(
                    "product_name"
                ),
                func.coalesce(CompanyUnitModel.alias, UnitModel.name).label("base_unit_name"),
                UnitModel.symbol.label("base_unit_symbol"),
            )
            .join(
                InventoryItemModel,
                and_(
                    InventoryItemModel.company_id == InventoryLotDetailModel.company_id,
                    InventoryItemModel.id == InventoryLotDetailModel.inventory_item_id,
                ),
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
                    ProductModel.id_product
                    == func.coalesce(InventoryItemModel.product_id, ProductVariantModel.product_id),
                ),
            )
            .join(
                CompanyUnitModel,
                and_(
                    CompanyUnitModel.company_id == InventoryItemModel.company_id,
                    CompanyUnitModel.unit_id == InventoryItemModel.base_unit_id,
                ),
            )
            .join(UnitModel, UnitModel.id_unit == CompanyUnitModel.unit_id)
            .where(
                InventoryLotDetailModel.company_id == company_id,
                InventoryLotDetailModel.inventory_lot_id.in_(lot_ids),
            )
            .order_by(InventoryLotDetailModel.created_at, InventoryLotDetailModel.id)
        )
    ).all()

    unit_filters = [
        InventoryHandlingUnitModel.company_id == company_id,
        InventoryHandlingUnitModel.inventory_lot_id.in_(lot_ids),
        InventoryHandlingUnitModel.closed_at.is_(None),
        InventoryHandlingUnitModel.inventory_posted_at.is_not(None),
    ]
    if warehouse_id is not None:
        unit_filters.append(InventoryHandlingUnitModel.warehouse_id == warehouse_id)
    unit_rows = (
        await session.execute(
            select(InventoryHandlingUnitModel, Location)
            .join(
                Location,
                and_(
                    Location.id == InventoryHandlingUnitModel.location_id,
                    Location.warehouse_id == InventoryHandlingUnitModel.warehouse_id,
                ),
            )
            .where(*unit_filters)
            .order_by(InventoryHandlingUnitModel.created_at, InventoryHandlingUnitModel.id)
        )
    ).all()

    retaceo_rows = (
        await session.execute(
            select(RetaceoModel.purchase_id, RetaceoModel.status, RetaceoModel.applied_at)
            .where(
                RetaceoModel.company_id == company_id,
                RetaceoModel.purchase_id.in_(purchase_ids),
            )
            .order_by(RetaceoModel.created_at.desc(), RetaceoModel.id.desc())
        )
    ).all()
    costing_by_purchase: dict[uuid.UUID, str] = {}
    for row in retaceo_rows:
        if row.purchase_id not in costing_by_purchase:
            costing_by_purchase[row.purchase_id] = (
                "applied" if row.applied_at is not None else row.status
            )

    grouped_lines = _group_lot_details(detail_rows)
    pending_by_lot, placed_by_lot = _add_unit_placement_progress(unit_rows, grouped_lines)
    return _build_lot_page(
        header_rows=header_rows,
        grouped_lines=grouped_lines,
        pending_by_lot=pending_by_lot,
        placed_by_lot=placed_by_lot,
        costing_by_purchase=costing_by_purchase,
        warehouse_id=warehouse_id,
        status=status,
        page=page,
        size=size,
        legacy_stock=legacy_stock,
    )
