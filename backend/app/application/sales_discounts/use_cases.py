"""Escalas por volumen, topes de descuento por rol y evaluación de líneas (bloque V2c)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.application.price_lists import PriceListUseCases, today_in_el_salvador
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.price_list import PriceKey, PriceList
from app.domain.entities.sales_margin import (
    AuthorizationReason,
    DiscountPolicy,
    LineEvaluation,
    ScheduledScale,
    SuggestedDiscount,
    VolumeScale,
    effective_policy,
    evaluate_global,
    evaluate_line,
    pick_volume_discount,
    plan_scale_change,
    require_policy,
    require_volume_scale,
    suggested_discount,
)
from app.domain.entities.sales_tax import line_round
from app.domain.ports.price_list_repository import PriceListRepository
from app.domain.ports.sales_discount_repository import (
    RolePolicy,
    SalesDiscountRepository,
    VolumeDiscount,
)


@dataclass(frozen=True, slots=True)
class LineRequest:
    product_id: int
    variant_id: uuid.UUID | None
    unit_id: int
    quantity: Decimal
    discount_percent: Decimal | None = None
    """Descuento que propone el vendedor; si falta, se usa el sugerido."""


@dataclass(frozen=True, slots=True)
class EvaluatedLine:
    request: LineRequest
    price_list: PriceList | None
    found: bool
    message: str | None
    suggested: SuggestedDiscount | None
    evaluation: LineEvaluation | None


@dataclass(frozen=True, slots=True)
class Evaluation:
    policy: DiscountPolicy
    lines: tuple[EvaluatedLine, ...]
    global_discount_percent: Decimal
    global_reasons: tuple[AuthorizationReason, ...]

    @property
    def requires_authorization(self) -> bool:
        return bool(self.global_reasons) or any(
            line.evaluation is not None and line.evaluation.requires_authorization
            for line in self.lines
        )


class SalesDiscountUseCases:
    def __init__(self, repository: SalesDiscountRepository, prices: PriceListRepository) -> None:
        self._repo = repository
        self._prices_repo = prices
        self._prices = PriceListUseCases(prices)

    # --- topes por rol ---
    async def role_policies(self, company_id: uuid.UUID) -> list[RolePolicy]:
        return await self._repo.role_policies(company_id)

    async def save_policy(
        self,
        company_id: uuid.UUID,
        role_id: uuid.UUID,
        policy: DiscountPolicy,
        actor_id: uuid.UUID,
    ) -> tuple[RolePolicy, RolePolicy]:
        require_policy(policy)
        if not await self._repo.role_in_company(company_id, role_id):
            raise NotFoundError(
                "Rol no encontrado en la empresa.", code="sales_policy_role_not_found"
            )
        before = next(r for r in await self._repo.role_policies(company_id) if r.role_id == role_id)
        await self._repo.save_policy(company_id, role_id, policy, actor_id)
        after = next(r for r in await self._repo.role_policies(company_id) if r.role_id == role_id)
        return before, after

    async def user_policy(self, company_id: uuid.UUID, user_id: uuid.UUID) -> DiscountPolicy:
        is_superuser, policies = await self._repo.user_policies(company_id, user_id)
        return effective_policy(policies, is_superuser)

    # --- escalas por volumen ---
    async def volume_discounts(
        self, company_id: uuid.UUID, list_id: uuid.UUID
    ) -> list[VolumeDiscount]:
        await self._prices.get_list(company_id, list_id)
        return await self._repo.volume_discounts(company_id, list_id)

    async def add_volume_discount(
        self,
        company_id: uuid.UUID,
        list_id: uuid.UUID,
        key: PriceKey,
        min_quantity: Decimal,
        discount_percent: Decimal,
        valid_from: date | None,
        actor_id: uuid.UUID,
    ) -> VolumeDiscount:
        await self._prices.get_list(company_id, list_id)
        require_volume_scale(min_quantity, discount_percent)
        units = await self._prices_repo.sellable_units(company_id, product_id=key.product_id)
        if not any(u.variant_id == key.variant_id and u.unit_id == key.unit_id for u in units):
            raise BusinessRuleError(
                "Esa unidad no es una forma de venta del producto.", code="price_list_unit_invalid"
            )
        await self._prices_repo.lock_list(company_id, list_id)
        today = today_in_el_salvador()
        start = valid_from or today
        same = [
            s
            for s in await self._repo.volume_discounts(
                company_id,
                list_id,
                product_id=key.product_id,
                variant_id=key.variant_id,
                unit_id=key.unit_id,
            )
            if s.min_quantity == min_quantity
        ]
        close_id, close_on = plan_scale_change(
            [ScheduledScale(s.id, _as_scale(s)) for s in same], start, today
        )
        if close_id is not None:
            await self._repo.set_volume_valid_to(close_id, close_on)
        scale_id = await self._repo.insert_volume_discount(
            company_id,
            list_id,
            key.product_id,
            key.variant_id,
            key.unit_id,
            min_quantity,
            discount_percent,
            start,
            actor_id,
        )
        created = await self._repo.get_volume_discount(company_id, scale_id)
        assert created is not None
        return created

    async def _scale(self, company_id: uuid.UUID, scale_id: uuid.UUID) -> VolumeDiscount:
        scale = await self._repo.get_volume_discount(company_id, scale_id)
        if scale is None:
            raise NotFoundError("Escala no encontrada.", code="sales_volume_not_found")
        return scale

    async def remove_volume_discount(
        self, company_id: uuid.UUID, scale_id: uuid.UUID
    ) -> VolumeDiscount:
        """Anula una escala que no ha empezado o termina hoy una vigente."""

        scale = await self._scale(company_id, scale_id)
        today = today_in_el_salvador()
        await self._prices_repo.lock_list(company_id, scale.price_list_id)
        if scale.valid_from > today:
            await self._repo.delete_volume_discount(scale.id)
        elif scale.valid_to is None or scale.valid_to >= today:
            await self._repo.set_volume_valid_to(scale.id, today)
        else:
            raise BusinessRuleError("Esa escala ya no está vigente.", code="sales_volume_expired")
        return scale

    # --- evaluación ---
    async def evaluate(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        customer_id: uuid.UUID | None,
        branch_id: uuid.UUID | None,
        on: date | None,
        lines: list[LineRequest],
        global_discount_percent: Decimal,
    ) -> Evaluation:
        day = on or today_in_el_salvador()
        policy = await self.user_policy(company_id, user_id)
        customer_percent = Decimal("0")
        if customer_id is not None:
            found = await self._repo.customer_discount(company_id, customer_id)
            if found is None:
                raise NotFoundError("Cliente no encontrado.", code="sales_customer_not_found")
            customer_percent = found
        units = await self._prices_repo.sellable_units(company_id)
        costs = await self._prices_repo.unit_costs(
            company_id, {u.inventory_item_id for u in units if u.inventory_item_id}
        )
        results: list[EvaluatedLine] = []
        for line in lines:
            resolved = await self._prices.resolve(
                company_id,
                customer_id=customer_id,
                branch_id=branch_id,
                product_id=line.product_id,
                variant_id=line.variant_id,
                unit_id=line.unit_id,
                on=day,
            )
            if resolved.price_list is None or resolved.entry is None:
                results.append(
                    EvaluatedLine(
                        line,
                        resolved.price_list,
                        False,
                        "La empresa no tiene lista predeterminada."
                        if resolved.price_list is None
                        else f"Sin precio en la lista «{resolved.price_list.name}».",
                        None,
                        None,
                    )
                )
                continue
            scales = await self._repo.volume_discounts(
                company_id,
                resolved.price_list.id,
                product_id=line.product_id,
                variant_id=line.variant_id,
                unit_id=line.unit_id,
            )
            volume = pick_volume_discount([_as_scale(s) for s in scales], line.quantity, day)
            suggested = suggested_discount(customer_percent, volume)
            unit = next(
                (
                    u
                    for u in units
                    if u.product_id == line.product_id
                    and u.variant_id == line.variant_id
                    and u.unit_id == line.unit_id
                ),
                None,
            )
            cost = (
                line_round(costs[unit.inventory_item_id] * unit.factor)
                if unit and unit.inventory_item_id in costs
                else None
            )
            applied = (
                line.discount_percent if line.discount_percent is not None else suggested.percent
            )
            evaluation = evaluate_line(
                resolved.entry.price,
                resolved.price_list.prices_include_vat,
                applied,
                cost,
                policy,
            )
            results.append(
                EvaluatedLine(line, resolved.price_list, True, None, suggested, evaluation)
            )
        return Evaluation(
            policy=policy,
            lines=tuple(results),
            global_discount_percent=global_discount_percent,
            global_reasons=evaluate_global(global_discount_percent, policy),
        )


def _as_scale(scale: VolumeDiscount) -> VolumeScale:
    return VolumeScale(
        min_quantity=scale.min_quantity,
        discount_percent=scale.discount_percent,
        valid_from=scale.valid_from,
        valid_to=scale.valid_to,
    )
