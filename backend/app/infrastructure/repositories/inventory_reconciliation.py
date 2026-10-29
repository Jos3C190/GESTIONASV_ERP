"""Consistent physical/financial reconciliation, current or by registration day."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import Numeric, and_, case, cast, column, func, literal, or_, select, union_all
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.inventory_kardex import LOCAL_TZ
from app.infrastructure.models.catalog import ProductModel, UnitModel
from app.infrastructure.models.inventory import (
    InventoryBalanceModel,
    InventoryItemModel,
    InventoryMovementLineModel,
    InventoryMovementModel,
)
from app.infrastructure.models.inventory_valuation import (
    InventoryCostAverageModel,
    InventoryValuationEntryModel,
)
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.repositories.inventory_valuation_repository import (
    SqlAlchemyInventoryValuationRepository,
)

ZERO = Decimal("0")


def _physical_at(setting, company_id, cutoff):
    snapshot = func.jsonb_array_elements(
        literal(setting.physical_snapshot, type_=JSONB)
    ).table_valued(column("value", JSONB))
    baseline = select(
        cast(snapshot.c.value["inventory_item_id"].astext, UUID).label("inventory_item_id"),
        cast(snapshot.c.value["quantity_base"].astext, Numeric(24, 6)).label("quantity"),
    )
    line, movement = InventoryMovementLineModel, InventoryMovementModel
    incoming = case(
        (
            and_(line.from_warehouse_id.is_(None), line.to_warehouse_id.is_not(None)),
            line.quantity_base,
        ),
        else_=ZERO,
    )
    outgoing = case(
        (
            and_(line.to_warehouse_id.is_(None), line.from_warehouse_id.is_not(None)),
            line.quantity_base,
        ),
        else_=ZERO,
    )
    changes = (
        select(line.inventory_item_id, (incoming - outgoing).label("quantity"))
        .join(
            movement, and_(movement.company_id == line.company_id, movement.id == line.movement_id)
        )
        .where(
            line.company_id == company_id,
            movement.posted_at >= setting.opened_at,
            movement.posted_at < cutoff,
        )
    )
    quantities = union_all(baseline, changes).subquery("cut_quantities")
    return (
        select(
            quantities.c.inventory_item_id,
            func.sum(quantities.c.quantity).label("physical_quantity"),
        )
        .group_by(quantities.c.inventory_item_id)
        .subquery("physical_totals")
    )


def _values_at(company_id, cutoff):
    entry = InventoryValuationEntryModel
    ranked = (
        select(
            entry.inventory_item_id,
            entry.balance_quantity.label("valued_quantity"),
            entry.balance_value.label("inventory_value"),
            entry.average_unit_cost,
            func.row_number()
            .over(partition_by=entry.inventory_item_id, order_by=entry.sequence.desc())
            .label("position"),
        )
        .where(entry.company_id == company_id, entry.posted_at < cutoff)
        .subquery("ranked_values")
    )
    return select(ranked).where(ranked.c.position == 1).subquery("value_totals")


async def reconciliation(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    page: int,
    page_size: int,
    as_of: date | None = None,
    query: str = "",
    difference_only: bool = False,
):
    valuation = SqlAlchemyInventoryValuationRepository(session)
    await valuation.lock(company_id)
    setting = await valuation.settings(company_id)
    cutoff = (
        datetime.combine(as_of + timedelta(days=1), time.min, tzinfo=LOCAL_TZ) if as_of else None
    )
    known = cutoff is None or (setting is not None and cutoff > setting.opened_at)
    if cutoff and setting and known:
        physical, values = _physical_at(setting, company_id, cutoff), _values_at(company_id, cutoff)
    else:
        physical = (
            select(
                InventoryBalanceModel.inventory_item_id,
                func.sum(InventoryBalanceModel.quantity_base).label("physical_quantity"),
            )
            .where(InventoryBalanceModel.company_id == company_id)
            .group_by(InventoryBalanceModel.inventory_item_id)
            .subquery("physical_totals")
        )
        values = (
            select(
                InventoryCostAverageModel.inventory_item_id,
                InventoryCostAverageModel.quantity_base.label("valued_quantity"),
                InventoryCostAverageModel.inventory_value,
                InventoryCostAverageModel.average_unit_cost,
            )
            .where(InventoryCostAverageModel.company_id == company_id)
            .subquery("value_totals")
        )
    name = func.coalesce(
        ProductVariantModel.name_override, ProductModel.name, "Producto sin nombre"
    )
    sku = func.coalesce(ProductVariantModel.sku, ProductModel.sku)
    quantity = (
        func.coalesce(physical.c.physical_quantity, ZERO)
        if known
        else literal(None, Numeric(24, 6))
    )
    valued_quantity = (
        values.c.valued_quantity if setting and known else literal(None, Numeric(24, 6))
    )
    amount = values.c.inventory_value if setting and known else literal(None, Numeric(24, 6))
    average = values.c.average_unit_cost if setting and known else literal(None, Numeric(24, 6))
    base = (
        select(
            InventoryItemModel.id.label("inventory_item_id"),
            name.label("product_name"),
            sku.label("sku"),
            func.coalesce(UnitModel.symbol, "unidad base").label("base_unit_symbol"),
            quantity.label("physical_quantity"),
            valued_quantity.label("valued_quantity"),
            (quantity - valued_quantity).label("quantity_difference"),
            amount.label("inventory_value"),
            average.label("average_unit_cost"),
        )
        .select_from(InventoryItemModel)
        .outerjoin(
            ProductVariantModel,
            and_(
                ProductVariantModel.company_id == company_id,
                ProductVariantModel.id == InventoryItemModel.variant_id,
            ),
        )
    )
    base = base.outerjoin(
        ProductModel,
        and_(
            ProductModel.company_id == company_id,
            ProductModel.id_product
            == func.coalesce(InventoryItemModel.product_id, ProductVariantModel.product_id),
        ),
    )
    base = (
        base.join(UnitModel, UnitModel.id_unit == InventoryItemModel.base_unit_id)
        .outerjoin(physical, physical.c.inventory_item_id == InventoryItemModel.id)
        .outerjoin(values, values.c.inventory_item_id == InventoryItemModel.id)
        .where(InventoryItemModel.company_id == company_id)
    )
    if query.strip():
        base = base.where(
            or_(
                name.icontains(query.strip(), autoescape=True),
                sku.icontains(query.strip(), autoescape=True),
            )
        )
    source = base.subquery("reconciliation_source")
    if difference_only:
        source = (
            select(source)
            .where(
                or_(source.c.quantity_difference.is_(None), source.c.quantity_difference != ZERO)
            )
            .subquery("reconciliation_filtered")
        )
    unknown = source.c.quantity_difference.is_(None)
    summary = (
        (
            await session.execute(
                select(
                    func.count().label("total"),
                    func.coalesce(func.sum(source.c.inventory_value), ZERO).label(
                        "inventory_value"
                    ),
                    func.count()
                    .filter(source.c.quantity_difference == ZERO)
                    .label("reconciled_items"),
                    func.count()
                    .filter(source.c.quantity_difference != ZERO)
                    .label("discrepant_items"),
                    func.count().filter(unknown).label("unvalued_items"),
                ).select_from(source)
            )
        )
        .mappings()
        .one()
    )
    rows = (
        (
            await session.execute(
                select(source)
                .order_by(source.c.product_name, source.c.inventory_item_id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .mappings()
        .all()
    )
    return {
        **summary,
        "inventory_value": summary["inventory_value"] if setting and known else None,
        "valuation_enabled": setting is not None,
        "currency": setting.currency if setting else None,
        "as_of": as_of,
        "generated_at": datetime.now(UTC),
        "balance_known": known,
        "items": [dict(row) for row in rows],
        "page": page,
        "page_size": page_size,
    }
