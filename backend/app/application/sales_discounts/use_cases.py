"""Escalas por volumen, topes por rol, promociones por sucursal y evaluación de líneas.

Bloque V2c; las promociones por sucursal son del pedido del ingeniero (24/11/2026).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.application.price_lists import PriceListUseCases, today_in_el_salvador
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.price_list import PriceKey, PriceList
from app.domain.entities.sales_margin import (
    UNLIMITED,
    AuthorizationReason,
    BranchPromotion,
    DiscountPolicy,
    DiscountSource,
    LineEvaluation,
    ScheduledScale,
    SuggestedDiscount,
    VolumeScale,
    effective_policy,
    evaluate_global,
    evaluate_line,
    pick_volume_discount,
    plan_scale_change,
    require_no_overlap,
    require_policy,
    require_promotion,
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
    cost: Decimal | None = None
    """Costo unitario sin IVA en la unidad de la línea, aunque no haya precio de lista."""
    promotion: BranchPromotion | None = None
    """Promoción vigente del producto en la sucursal: fija el descuento de la línea."""


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
    # --- promociones por sucursal ---
    async def _active_promotions(
        self, company_id: uuid.UUID, branch_id: uuid.UUID | None, day: date
    ) -> dict[int, BranchPromotion]:
        if branch_id is None:
            return {}
        found = await self._repo.promotions(
            company_id, branch_ids=(branch_id,), include_ended=False
        )
        return {p.product_id: p for p in found if p.covers(day)}

    async def promotions(
        self,
        company_id: uuid.UUID,
        *,
        branch_ids: tuple[uuid.UUID, ...] | None,
        include_ended: bool,
    ) -> list[BranchPromotion]:
        return await self._repo.promotions(
            company_id, branch_ids=branch_ids, include_ended=include_ended
        )

    async def promotion(self, company_id: uuid.UUID, promotion_id: uuid.UUID) -> BranchPromotion:
        found = await self._repo.get_promotion(company_id, promotion_id)
        if found is None:
            raise NotFoundError("Promoción no encontrada.", code="sales_promotion_not_found")
        return found

    async def add_promotion(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        *,
        branch_id: uuid.UUID,
        product_id: int,
        discount_percent: Decimal,
        valid_from: date | None,
        valid_to: date | None,
        notes: str | None,
    ) -> BranchPromotion:
        today = today_in_el_salvador()
        start = valid_from or today
        require_promotion(discount_percent, start, valid_to, today)
        if not await self._prices_repo.branch_exists(company_id, branch_id):
            raise NotFoundError("Sucursal no encontrada.", code="sales_promotion_branch_invalid")
        units = await self._prices_repo.sellable_units(company_id, product_id=product_id)
        if not any(unit.product_id == product_id for unit in units):
            raise BusinessRuleError(
                "El producto no existe o no está marcado como vendible.",
                code="sales_promotion_product_invalid",
            )
        await self._repo.lock_promotion_scope(company_id, branch_id, product_id)
        existing = await self._repo.promotions(
            company_id, branch_ids=(branch_id,), product_id=product_id, include_ended=False
        )
        require_no_overlap(existing, start, valid_to)
        promotion_id = await self._repo.insert_promotion(
            company_id,
            branch_id,
            product_id,
            discount_percent,
            start,
            valid_to,
            (notes or "").strip() or None,
            actor_id,
        )
        return await self.promotion(company_id, promotion_id)

    async def end_promotion(
        self, company_id: uuid.UUID, actor_id: uuid.UUID, promotion_id: uuid.UUID
    ) -> tuple[BranchPromotion, BranchPromotion]:
        before = await self._repo.get_promotion(company_id, promotion_id, lock=True)
        if before is None:
            raise NotFoundError("Promoción no encontrada.", code="sales_promotion_not_found")
        if before.ended:
            raise BusinessRuleError(
                "La promoción ya está terminada.", code="sales_promotion_already_ended"
            )
        await self._repo.end_promotion(promotion_id, actor_id)
        return before, await self.promotion(company_id, promotion_id)

    async def unit_costs(
        self, company_id: uuid.UUID, inventory_item_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, Decimal]:
        """Costo promedio vigente del kardex por artículo, en su unidad base."""

        return await self._prices_repo.unit_costs(company_id, inventory_item_ids)

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
        promotions = await self._active_promotions(company_id, branch_id, day)
        if global_discount_percent > 0 and any(line.product_id in promotions for line in lines):
            raise BusinessRuleError(
                "Hay productos en promoción en esta sucursal: el documento no admite descuento "
                "global. Quita el descuento global.",
                code="sales_global_discount_with_promotion",
            )
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
                        cost,
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
            promotion = promotions.get(line.product_id)
            if promotion is not None:
                # La promoción reemplaza todo: ni cliente, ni volumen, ni el descuento del vendedor,
                # y no pasa por el tope del rol (la decidió la empresa).
                suggested = SuggestedDiscount(promotion.discount_percent, DiscountSource.PROMOTION)
                applied = promotion.discount_percent
            else:
                volume = pick_volume_discount([_as_scale(s) for s in scales], line.quantity, day)
                suggested = suggested_discount(customer_percent, volume)
                applied = (
                    line.discount_percent
                    if line.discount_percent is not None
                    else suggested.percent
                )
            evaluation = evaluate_line(
                resolved.entry.price,
                resolved.price_list.prices_include_vat,
                applied,
                cost,
                UNLIMITED if promotion is not None else policy,
            )
            results.append(
                EvaluatedLine(
                    line, resolved.price_list, True, None, suggested, evaluation, cost, promotion
                )
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
