"""Listas de precios de demostración de Grupo Lorena.

- «Mostrador» (predeterminada, con IVA): precio por unidad base de cada producto vendible.
- «Mayoreo» (sin IVA): 10 % menos que mostrador antes de IVA, y precio por empaque.
- Roosevelt tiene precio propio de mostrador para el café, para mostrar el precio por sucursal.
- Los clientes contribuyentes CLI-00001 y CLI-00002 usan Mayoreo.

Los precios de mostrador dejan al menos 35 % de margen sobre el costo de la operación de
demostración (costo ÷ 0.65, con IVA).

Solo agrega lo que falta y no cambia precios que alguien haya tocado. Si un precio vigente
todavía es el de la primera versión de la semilla (que en varios productos quedaba bajo el
margen o bajo el costo), programa el precio corregido desde mañana.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.application.price_lists import PriceListUseCases, today_in_el_salvador
from app.domain.entities.price_list import PriceKey, PriceList, PriceListDraft, SellableUnit
from app.infrastructure.db.session import session_scope
from app.infrastructure.models.organization import Branch
from app.infrastructure.models.sales import SalesCustomerModel
from app.infrastructure.models.user import User
from app.infrastructure.repositories.price_list_repository import SqlAlchemyPriceListRepository
from sqlalchemy import select, update

from seed.seed_grupo_lorena import COMPANY_ID, SUPER_ADMIN_USERNAME

COUNTER = PriceListDraft(
    code="MOSTRADOR",
    name="Mostrador",
    description="Precios al público, con IVA incluido.",
    prices_include_vat=True,
    is_default=True,
)
WHOLESALE = PriceListDraft(
    code="MAYOREO",
    name="Mayoreo",
    description="Negocios que compran por caja; precios sin IVA.",
    prices_include_vat=False,
)
#: Precio de mostrador, con IVA, por unidad base.
COUNTER_PRICES: dict[str, Decimal] = {
    "PRD-HAR-001": Decimal("42.60"),
    "PRD-LAC-002": Decimal("103.60"),
    "PRD-HAR-003": Decimal("1.45"),
    "PRD-AZU-004": Decimal("2.25"),
    "PRD-LEV-005": Decimal("4.25"),
    "PRD-CHO-006": Decimal("12.10"),
    "PRD-REL-007": Decimal("7.10"),
    "PRD-MAR-008": Decimal("3.60"),
    "PRD-EMP-009": Decimal("0.95"),
    "PRD-EMP-010": Decimal("0.12"),
    "PRD-CAF-011": Decimal("19.85"),
    "PRD-JAR-012": Decimal("6.75"),
}
#: Precios de la primera versión de la semilla que se corrigen si siguen sin tocar.
PREVIOUS_COUNTER_PRICES: dict[str, Decimal] = {
    "PRD-HAR-001": Decimal("38.50"),
    "PRD-LAC-002": Decimal("62.00"),
    "PRD-AZU-004": Decimal("2.10"),
    "PRD-CHO-006": Decimal("9.80"),
    "PRD-REL-007": Decimal("3.60"),
    "PRD-MAR-008": Decimal("3.15"),
    "PRD-CAF-011": Decimal("11.50"),
}
ROOSEVELT_CODE = "LOR-SM-01"
ROOSEVELT_COFFEE = Decimal("20.50")
PREVIOUS_ROOSEVELT_COFFEE = Decimal("12.25")
WHOLESALE_CUSTOMERS = ("CLI-00001", "CLI-00002")
CENT = Decimal("0.01")


def wholesale_price(counter_price: Decimal, factor: Decimal) -> Decimal:
    """10 % menos que mostrador, sin IVA, multiplicado por el contenido del empaque."""

    return (counter_price / Decimal("1.13") * Decimal("0.90") * factor).quantize(
        CENT, rounding=ROUND_HALF_UP
    )


async def _ensure_list(
    prices: PriceListUseCases, existing: list[PriceList], draft: PriceListDraft, actor: uuid.UUID
) -> PriceList:
    found = next((item for item in existing if item.code == draft.code), None)
    if found is not None:
        return found
    return await prices.create_list(COMPANY_ID, draft, actor)


async def _set_missing(
    prices: PriceListUseCases,
    price_list: PriceList,
    unit: SellableUnit,
    price: Decimal,
    actor: uuid.UUID,
    branch_id: uuid.UUID | None = None,
) -> None:
    key = PriceKey(unit.product_id, unit.variant_id, unit.unit_id, branch_id)
    history = await prices.history(
        COMPANY_ID, price_list.id, unit.product_id, unit.variant_id, unit.unit_id
    )
    if any(entry.key == key for entry in history):
        return
    await prices.set_price(COMPANY_ID, price_list.id, key, price, today_in_el_salvador(), actor)


async def _correct_if_untouched(
    prices: PriceListUseCases,
    price_list: PriceList,
    unit: SellableUnit,
    previous: Decimal,
    corrected: Decimal,
    actor: uuid.UUID,
    branch_id: uuid.UUID | None = None,
) -> None:
    """Programa el precio corregido desde mañana si el vigente sigue siendo el anterior."""
    if previous == corrected:
        return
    today = today_in_el_salvador()
    mine = [
        entry
        for entry in await prices.history(
            COMPANY_ID, price_list.id, unit.product_id, unit.variant_id, unit.unit_id
        )
        if entry.key.branch_id == branch_id
    ]
    current = next((e for e in mine if e.covers(today)), None)
    if current is None or current.valid_to is not None or current.price != previous:
        return
    if any(e.valid_from > today for e in mine):
        return
    key = PriceKey(unit.product_id, unit.variant_id, unit.unit_id, branch_id)
    await prices.set_price(
        COMPANY_ID, price_list.id, key, corrected, today + timedelta(days=1), actor
    )


async def seed() -> bool:
    async with session_scope() as session:
        actor = await session.scalar(select(User.id).where(User.username == SUPER_ADMIN_USERNAME))
        if actor is None:
            print("[seed] Listas de precios: falta el superadministrador; se reintenta después.")
            return False
        prices = PriceListUseCases(SqlAlchemyPriceListRepository(session))
        existing = await prices.list_lists(COMPANY_ID)
        counter = await _ensure_list(prices, existing, COUNTER, actor)
        wholesale = await _ensure_list(prices, existing, WHOLESALE, actor)

        units = await prices.sellable_units(COMPANY_ID, None)
        base_prices = {u.sku: COUNTER_PRICES[u.sku] for u in units if u.sku in COUNTER_PRICES}
        for unit in units:
            base = base_prices.get(unit.sku)
            if base is None:
                continue
            if unit.is_base:
                await _set_missing(prices, counter, unit, base, actor)
            await _set_missing(prices, wholesale, unit, wholesale_price(base, unit.factor), actor)

        for unit in units:
            previous = PREVIOUS_COUNTER_PRICES.get(unit.sku)
            corrected = base_prices.get(unit.sku)
            if previous is None or corrected is None:
                continue
            if unit.is_base:
                await _correct_if_untouched(prices, counter, unit, previous, corrected, actor)
            await _correct_if_untouched(
                prices,
                wholesale,
                unit,
                wholesale_price(previous, unit.factor),
                wholesale_price(corrected, unit.factor),
                actor,
            )

        roosevelt = await session.scalar(
            select(Branch.id).where(Branch.company_id == COMPANY_ID, Branch.code == ROOSEVELT_CODE)
        )
        coffee = next((u for u in units if u.sku == "PRD-CAF-011" and u.is_base), None)
        if roosevelt is not None and coffee is not None:
            await _set_missing(prices, counter, coffee, ROOSEVELT_COFFEE, actor, roosevelt)
            await _correct_if_untouched(
                prices,
                counter,
                coffee,
                PREVIOUS_ROOSEVELT_COFFEE,
                ROOSEVELT_COFFEE,
                actor,
                roosevelt,
            )

        await session.execute(
            update(SalesCustomerModel)
            .where(
                SalesCustomerModel.company_id == COMPANY_ID,
                SalesCustomerModel.code.in_(WHOLESALE_CUSTOMERS),
                SalesCustomerModel.price_list_id.is_(None),
            )
            .values(price_list_id=wholesale.id)
        )
    return True
