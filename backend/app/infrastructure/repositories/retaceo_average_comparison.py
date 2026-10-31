"""Read-only comparison of a future receipt or its immutable posted valuation."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, NoReturn

from sqlalchemy import select

from app.domain.entities.inventory import InventoryItem, InventoryOperationError
from app.domain.entities.inventory_valuation import ZERO, ValuationEvent, amount, project
from app.domain.entities.purchase_conversion import PurchaseValuationConversion
from app.domain.entities.retaceo import Retaceo
from app.domain.ports.inventory_valuation import RetaceoAverageComparison, RetaceoAverageLine
from app.infrastructure.models.inventory import InventoryItemModel
from app.infrastructure.models.inventory_valuation import (
    InventoryCostAverageModel,
    InventoryValuationEntryModel,
)
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository

if TYPE_CHECKING:
    from app.infrastructure.repositories.inventory_valuation_repository import (
        SqlAlchemyInventoryValuationRepository,
    )


async def compare_average(
    valuation: SqlAlchemyInventoryValuationRepository, retaceo: Retaceo
) -> RetaceoAverageComparison:
    setting = await valuation.settings(retaceo.company_id)
    if setting is None:
        valuation_error(
            "Apruebe el saldo inicial antes de comparar el costo promedio.",
            "valuation_opening_required",
        )
    if retaceo.applied_at is not None:
        return await _posted_comparison(valuation, retaceo, setting.currency)
    conversion = await valuation._retaceo_conversion(retaceo, setting.currency)
    if await valuation.receipt_is_valued(retaceo.company_id, retaceo.purchase_id):
        return await _existing_receipt_comparison(valuation, retaceo, setting.currency, conversion)
    inventory = SqlAlchemyInventoryRepository(valuation.session)
    grouped: dict[int, tuple[InventoryItem, Decimal, Decimal]] = {}
    for detail in retaceo.details:
        item = await inventory.get_item_by_target(
            company_id=retaceo.company_id, product_id=detail.product_id, variant_id=None
        )
        if item is None or not item.is_active:
            valuation_error(
                "Configure la unidad base de todos los productos antes de comparar el promedio.",
                "purchase_receipt_inventory_item_missing",
            )
        factor = Decimal("1")
        if item.base_unit_id != detail.unit_id:
            packages = [
                row
                for row in await inventory.list_packaging(retaceo.company_id, item.id)
                if row.is_active and row.is_current and row.packaging_unit_id == detail.unit_id
            ]
            if len(packages) != 1:
                valuation_error(
                    "Registre una única equivalencia vigente para cada unidad de compra.",
                    "purchase_receipt_unit_conversion_missing",
                )
            factor = packages[0].base_quantity
        quantity = detail.quantity * factor
        if quantity != amount(quantity):
            valuation_error(
                "La equivalencia produce más de seis decimales de unidad base.",
                "purchase_receipt_unit_conversion_precision",
            )
        value = conversion.convert(detail.total_cost) if conversion else detail.total_cost
        _, old_quantity, old_value = grouped.get(detail.product_id, (item, ZERO, ZERO))
        grouped[detail.product_id] = (item, old_quantity + quantity, old_value + value)
    result = []
    for product_id, (item, planned_quantity, planned_value) in grouped.items():
        quantity, value = planned_quantity, planned_value
        balance = await valuation.session.get(
            InventoryCostAverageModel, (retaceo.company_id, item.id)
        )
        previous_quantity = balance.quantity_base if balance else ZERO
        previous_value = balance.inventory_value if balance else ZERO
        resulting_quantity = previous_quantity + quantity
        resulting_value = previous_value + value
        result.append(
            RetaceoAverageLine(
                product_id=product_id,
                inventory_item_id=item.id,
                base_unit_id=item.base_unit_id,
                previous_quantity=previous_quantity,
                previous_value=previous_value,
                previous_average=amount(previous_value / previous_quantity)
                if previous_quantity
                else ZERO,
                incoming_quantity=quantity,
                incoming_value=value,
                resulting_quantity=resulting_quantity,
                resulting_value=resulting_value,
                resulting_average=amount(resulting_value / resulting_quantity)
                if resulting_quantity
                else ZERO,
            )
        )
    return RetaceoAverageComparison(currency=setting.currency, mode="preview", lines=tuple(result))


async def _existing_receipt_comparison(
    valuation: SqlAlchemyInventoryValuationRepository,
    retaceo: Retaceo,
    currency: str,
    conversion: PurchaseValuationConversion | None,
) -> RetaceoAverageComparison:
    """Simulate the same append-only adjustments used by application, without adding stock."""
    detail_ids = {detail.purchase_detail_id for detail in retaceo.details}
    sources = list(
        (
            await valuation.session.scalars(
                select(InventoryValuationEntryModel)
                .where(
                    InventoryValuationEntryModel.company_id == retaceo.company_id,
                    InventoryValuationEntryModel.purchase_detail_id.in_(detail_ids),
                    InventoryValuationEntryModel.kind == "receipt",
                )
                .order_by(InventoryValuationEntryModel.sequence)
            )
        ).all()
    )
    changes: dict[uuid.UUID, list[ValuationEvent]] = {}
    for detail in retaceo.details:
        rows = [row for row in sources if row.purchase_detail_id == detail.purchase_detail_id]
        if not rows:
            valuation_error(
                "La recepción no tiene valoración vinculada.", "retaceo_receipt_valuation_missing"
            )
        remaining = conversion.convert(detail.total_cost) if conversion else detail.total_cost
        quantity = sum((row.quantity_base for row in rows), ZERO)
        for index, source in enumerate(rows):
            target = (
                remaining
                if index == len(rows) - 1
                else amount(remaining * source.quantity_base / quantity)
            )
            remaining -= target
            quantity -= source.quantity_base
            changes.setdefault(source.inventory_item_id, []).append(
                ValuationEvent(
                    uuid.uuid4(), "cost_adjustment", ZERO, target - source.source_value, source.id
                )
            )
    result = []
    for item_id, adjustments in changes.items():
        item = await valuation.session.get(InventoryItemModel, item_id)
        if item is None or item.product_id is None:
            valuation_error(
                "El producto de valoración no está disponible.", "valuation_item_not_found"
            )
        events = [
            valuation._event(row) for row in await valuation._rows(retaceo.company_id, item_id)
        ]
        previous, revised = project(events), project(events + adjustments)
        result.append(
            RetaceoAverageLine(
                product_id=item.product_id,
                inventory_item_id=item_id,
                base_unit_id=item.base_unit_id,
                previous_quantity=previous.quantity,
                previous_value=previous.value,
                previous_average=previous.average,
                incoming_quantity=ZERO,
                incoming_value=revised.value - previous.value,
                resulting_quantity=revised.quantity,
                resulting_value=revised.value,
                resulting_average=revised.average,
            )
        )
    return RetaceoAverageComparison(
        currency=currency, mode="preview", lines=tuple(result), value_only=True
    )


def valuation_error(message: str, code: str) -> NoReturn:
    raise InventoryOperationError(message, code=code, status_code=409)


async def _posted_comparison(
    valuation: SqlAlchemyInventoryValuationRepository, retaceo: Retaceo, currency: str
) -> RetaceoAverageComparison:
    rows = list(
        (
            await valuation.session.execute(
                select(InventoryValuationEntryModel, InventoryItemModel)
                .join(
                    InventoryItemModel,
                    (InventoryItemModel.company_id == InventoryValuationEntryModel.company_id)
                    & (InventoryItemModel.id == InventoryValuationEntryModel.inventory_item_id),
                )
                .where(
                    InventoryValuationEntryModel.company_id == retaceo.company_id,
                    InventoryValuationEntryModel.retaceo_id == retaceo.id,
                    InventoryValuationEntryModel.kind.in_(("receipt", "cost_adjustment")),
                )
                .order_by(InventoryValuationEntryModel.sequence)
            )
        ).all()
    )
    grouped: dict[uuid.UUID, tuple[InventoryItemModel, list[InventoryValuationEntryModel]]] = {}
    for entry, item in rows:
        grouped.setdefault(item.id, (item, []))[1].append(entry)
    result = []
    for item, entries in grouped.values():
        if item.product_id is None:
            valuation_error(
                "El producto de valoración no está disponible.", "valuation_item_not_found"
            )
        first, last = entries[0], entries[-1]
        quantity = first.balance_quantity - first.quantity_base
        value = first.balance_value - first.inventory_delta
        result.append(
            RetaceoAverageLine(
                product_id=item.product_id,
                inventory_item_id=item.id,
                base_unit_id=item.base_unit_id,
                previous_quantity=quantity,
                previous_value=value,
                previous_average=amount(value / quantity) if quantity else ZERO,
                incoming_quantity=sum((entry.quantity_base for entry in entries), ZERO),
                incoming_value=sum((entry.inventory_delta for entry in entries), ZERO),
                resulting_quantity=last.balance_quantity,
                resulting_value=last.balance_value,
                resulting_average=last.average_unit_cost,
            )
        )
    return RetaceoAverageComparison(
        currency=currency,
        mode="posted",
        lines=tuple(result),
        value_only=bool(rows) and all(entry.kind == "cost_adjustment" for entry, _ in rows),
    )
