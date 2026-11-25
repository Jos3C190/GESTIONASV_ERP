"""Margen objetivo, escalas, descuento de cliente y topes por rol de Grupo Lorena (bloque V2c).

- Mostrador busca 35 % de margen y Mayoreo 20 %.
- En Mayoreo, las bolsas por caja tienen escalas: desde 10 cajas 3 %, desde 50 cajas 6 %.
- Cafetería El Trigal (CLI-00001) tiene 3 % de descuento fijo.
- GERENTE DE SUCURSAL puede dar hasta 10 % por línea y 5 % global; EMPLEADO hasta 3 % por línea.

Solo agrega lo que falta: no cambia márgenes, escalas, descuentos ni topes ya guardados.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from app.application.price_lists import PriceListUseCases
from app.application.sales_discounts import SalesDiscountUseCases
from app.domain.entities.price_list import PriceKey, PriceListDraft
from app.domain.entities.sales_margin import DiscountPolicy
from app.infrastructure.db.session import session_scope
from app.infrastructure.models.sales import SalesCustomerModel
from app.infrastructure.models.user import User
from app.infrastructure.repositories.price_list_repository import SqlAlchemyPriceListRepository
from app.infrastructure.repositories.sales_discount_repository import (
    SqlAlchemySalesDiscountRepository,
)
from sqlalchemy import select, update

from seed.seed_grupo_lorena import COMPANY_ID, SUPER_ADMIN_USERNAME

TARGET_MARGINS = {"MOSTRADOR": Decimal("35"), "MAYOREO": Decimal("20")}
WHOLESALE_SCALES_SKU = "PRD-EMP-010"
WHOLESALE_SCALES = ((Decimal("10"), Decimal("3")), (Decimal("50"), Decimal("6")))
CUSTOMER_DISCOUNT = ("CLI-00001", Decimal("3"))
ROLE_POLICIES = {
    "GERENTE DE SUCURSAL": DiscountPolicy(Decimal("10"), Decimal("5")),
    "EMPLEADO": DiscountPolicy(Decimal("3"), Decimal("0")),
}


async def seed() -> bool:
    async with session_scope() as session:
        actor = await session.scalar(select(User.id).where(User.username == SUPER_ADMIN_USERNAME))
        if actor is None:
            print("[seed] Descuentos: falta el superadministrador; se reintenta después.")
            return False
        price_repo = SqlAlchemyPriceListRepository(session)
        prices = PriceListUseCases(price_repo)
        discounts = SalesDiscountUseCases(SqlAlchemySalesDiscountRepository(session), price_repo)
        lists = {item.code: item for item in await prices.list_lists(COMPANY_ID)}
        if not {"MOSTRADOR", "MAYOREO"} <= set(lists):
            print("[seed] Descuentos: faltan las listas de precios; se reintenta después.")
            return False

        for code, margin in TARGET_MARGINS.items():
            item = lists[code]
            if item.target_margin_percent is None:
                draft = PriceListDraft(
                    code=item.code,
                    name=item.name,
                    prices_include_vat=item.prices_include_vat,
                    description=item.description,
                    is_default=item.is_default,
                    is_active=item.is_active,
                )
                await prices.update_list(
                    COMPANY_ID, item.id, replace(draft, target_margin_percent=margin), actor
                )

        wholesale = lists["MAYOREO"]
        if not await discounts.volume_discounts(COMPANY_ID, wholesale.id):
            box = next(
                (
                    u
                    for u in await prices.sellable_units(COMPANY_ID, None)
                    if u.sku == WHOLESALE_SCALES_SKU and not u.is_base
                ),
                None,
            )
            if box is not None:
                key = PriceKey(box.product_id, box.variant_id, box.unit_id, None)
                for quantity, percent in WHOLESALE_SCALES:
                    await discounts.add_volume_discount(
                        COMPANY_ID, wholesale.id, key, quantity, percent, None, actor
                    )

        code, percent = CUSTOMER_DISCOUNT
        await session.execute(
            update(SalesCustomerModel)
            .where(
                SalesCustomerModel.company_id == COMPANY_ID,
                SalesCustomerModel.code == code,
                SalesCustomerModel.discount_percent == 0,
            )
            .values(discount_percent=percent)
        )

        for role in await discounts.role_policies(COMPANY_ID):
            policy = ROLE_POLICIES.get(role.role_name)
            if policy is not None and role.policy is None:
                await discounts.save_policy(COMPANY_ID, role.role_id, policy, actor)
    return True
