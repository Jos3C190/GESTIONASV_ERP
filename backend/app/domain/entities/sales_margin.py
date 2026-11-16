"""Margen, precio sugerido, descuentos y topes por rol (bloque V2c).

El margen se mide sobre el precio sin IVA: (precio - costo) / precio. El costo es el costo
promedio de inventario, que ya incluye el retaceo. Un precio de una lista con IVA se lleva a
sin IVA antes de comparar.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.core.exceptions import BusinessRuleError, ConflictError
from app.domain.entities.sales_tax import VAT_FACTOR, line_round

HUNDRED = Decimal("100")
CENT = Decimal("0.01")
ZERO = Decimal("0")
MAX_TARGET_MARGIN = Decimal("95")


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


def percent_round(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def without_vat(price: Decimal, includes_vat: bool) -> Decimal:
    return line_round(price / VAT_FACTOR) if includes_vat else price


def margin_percent(price: Decimal, includes_vat: bool, cost: Decimal | None) -> Decimal | None:
    """Margen % sobre el precio sin IVA, o ``None`` si no hay costo o el precio es cero."""

    if cost is None:
        return None
    net = without_vat(price, includes_vat)
    if net <= ZERO:
        return None
    return percent_round((net - cost) / net * HUNDRED)


def require_target_margin(value: Decimal | None) -> None:
    if value is not None and not ZERO <= value <= MAX_TARGET_MARGIN:
        raise _rule("El margen objetivo va de 0 % a 95 %.", "sales_margin_target_invalid")


def suggested_price(cost: Decimal, target_margin: Decimal, includes_vat: bool) -> Decimal:
    """Precio que deja ``target_margin`` % sobre el precio sin IVA, redondeado al centavo."""

    require_target_margin(target_margin)
    net = cost / (1 - target_margin / HUNDRED)
    price = net * VAT_FACTOR if includes_vat else net
    return price.quantize(CENT, rounding=ROUND_HALF_UP)


def target_margin_for(
    list_margin: Decimal | None, category_margins: dict[int, Decimal], category_id: int | None
) -> Decimal | None:
    """El margen de la categoría gana al de la lista."""

    if category_id is not None and category_id in category_margins:
        return category_margins[category_id]
    return list_margin


@dataclass(frozen=True, slots=True)
class VolumeScale:
    min_quantity: Decimal
    discount_percent: Decimal
    valid_from: date
    valid_to: date | None

    def covers(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)


def require_volume_scale(min_quantity: Decimal, discount_percent: Decimal) -> None:
    if min_quantity <= ZERO:
        raise _rule("La cantidad mínima debe ser mayor que cero.", "sales_volume_quantity_invalid")
    if not ZERO < discount_percent <= HUNDRED:
        raise _rule(
            "El descuento por volumen va de más de 0 % hasta 100 %.",
            "sales_volume_percent_invalid",
        )


def pick_volume_discount(
    scales: list[VolumeScale], quantity: Decimal, day: date
) -> VolumeScale | None:
    """La escala vigente de mayor cantidad mínima que la cantidad alcanza."""

    reached = [s for s in scales if s.covers(day) and quantity >= s.min_quantity]
    return max(reached, key=lambda s: s.min_quantity, default=None)


class DiscountSource(StrEnum):
    NONE = "none"
    CUSTOMER = "customer"
    VOLUME = "volume"


@dataclass(frozen=True, slots=True)
class SuggestedDiscount:
    percent: Decimal
    source: DiscountSource


def suggested_discount(customer_percent: Decimal, volume: VolumeScale | None) -> SuggestedDiscount:
    """El mayor entre el descuento del cliente y el de volumen; no se suman."""

    volume_percent = volume.discount_percent if volume else ZERO
    if volume_percent > customer_percent:
        return SuggestedDiscount(volume_percent, DiscountSource.VOLUME)
    if customer_percent > ZERO:
        return SuggestedDiscount(customer_percent, DiscountSource.CUSTOMER)
    return SuggestedDiscount(ZERO, DiscountSource.NONE)


def require_customer_discount(value: Decimal) -> None:
    if not ZERO <= value <= HUNDRED:
        raise _rule("El descuento del cliente va de 0 % a 100 %.", "customer_discount_invalid")


@dataclass(frozen=True, slots=True)
class DiscountPolicy:
    """Topes de descuento. Para un usuario se combinan los de todos sus roles."""

    max_line_percent: Decimal
    max_global_percent: Decimal
    can_sell_below_cost: bool


UNLIMITED = DiscountPolicy(HUNDRED, HUNDRED, True)
NONE_ALLOWED = DiscountPolicy(ZERO, ZERO, False)


def require_policy(policy: DiscountPolicy) -> None:
    for value in (policy.max_line_percent, policy.max_global_percent):
        if not ZERO <= value <= HUNDRED:
            raise _rule("Los topes de descuento van de 0 % a 100 %.", "sales_policy_invalid")


def effective_policy(policies: list[DiscountPolicy], is_superuser: bool) -> DiscountPolicy:
    """El máximo de cada valor entre los roles; sin políticas, no hay descuento permitido."""

    if is_superuser:
        return UNLIMITED
    if not policies:
        return NONE_ALLOWED
    return DiscountPolicy(
        max_line_percent=max(p.max_line_percent for p in policies),
        max_global_percent=max(p.max_global_percent for p in policies),
        can_sell_below_cost=any(p.can_sell_below_cost for p in policies),
    )


class AuthorizationReason(StrEnum):
    DISCOUNT_ABOVE_LIMIT = "discount_above_limit"
    BELOW_COST = "below_cost"
    GLOBAL_DISCOUNT_ABOVE_LIMIT = "global_discount_above_limit"


REASON_TEXT: dict[AuthorizationReason, str] = {
    AuthorizationReason.DISCOUNT_ABOVE_LIMIT: "El descuento supera el tope de tu rol.",
    AuthorizationReason.BELOW_COST: "El precio queda por debajo del costo.",
    AuthorizationReason.GLOBAL_DISCOUNT_ABOVE_LIMIT: "El descuento global supera el tope de tu rol.",
}


@dataclass(frozen=True, slots=True)
class LineEvaluation:
    list_price: Decimal
    discount_percent: Decimal
    net_price: Decimal
    """Precio con el descuento, en la misma forma (con o sin IVA) que la lista."""
    cost: Decimal | None
    margin_percent: Decimal | None
    reasons: tuple[AuthorizationReason, ...]

    @property
    def requires_authorization(self) -> bool:
        return bool(self.reasons)


def evaluate_line(
    list_price: Decimal,
    includes_vat: bool,
    discount_percent: Decimal,
    cost: Decimal | None,
    policy: DiscountPolicy,
) -> LineEvaluation:
    if not ZERO <= discount_percent <= HUNDRED:
        raise _rule("El descuento va de 0 % a 100 %.", "sales_discount_percent_invalid")
    net = line_round(list_price * (1 - discount_percent / HUNDRED))
    reasons: list[AuthorizationReason] = []
    if discount_percent > policy.max_line_percent:
        reasons.append(AuthorizationReason.DISCOUNT_ABOVE_LIMIT)
    if (
        cost is not None
        and without_vat(net, includes_vat) < cost
        and not policy.can_sell_below_cost
    ):
        reasons.append(AuthorizationReason.BELOW_COST)
    return LineEvaluation(
        list_price=list_price,
        discount_percent=discount_percent,
        net_price=net,
        cost=cost,
        margin_percent=margin_percent(net, includes_vat, cost),
        reasons=tuple(reasons),
    )


def evaluate_global(
    discount_percent: Decimal, policy: DiscountPolicy
) -> tuple[AuthorizationReason, ...]:
    if not ZERO <= discount_percent <= HUNDRED:
        raise _rule("El descuento va de 0 % a 100 %.", "sales_discount_percent_invalid")
    if discount_percent > policy.max_global_percent:
        return (AuthorizationReason.GLOBAL_DISCOUNT_ABOVE_LIMIT,)
    return ()


@dataclass(frozen=True, slots=True)
class ScheduledScale:
    """Una escala guardada, con su identificador, para planificar cambios."""

    id: uuid.UUID
    scale: VolumeScale


def plan_scale_change(
    existing: list[ScheduledScale], valid_from: date, today: date
) -> tuple[uuid.UUID | None, date | None]:
    """Igual que un precio: la escala nueva cierra la vigente el día anterior.

    ``existing`` son las escalas de la misma lista, producto, unidad y cantidad mínima.
    """

    if valid_from < today:
        raise _rule("Una escala rige desde hoy o desde una fecha futura.", "sales_volume_backdated")
    later = [s for s in existing if s.scale.valid_from >= valid_from]
    if later:
        first = min(later, key=lambda s: s.scale.valid_from)
        raise ConflictError(
            f"Ya hay una escala para esa cantidad que rige desde el "
            f"{first.scale.valid_from:%d/%m/%Y}. Anúlala antes de crear otra.",
            code="sales_volume_future_exists",
        )
    covering = next((s for s in existing if s.scale.covers(valid_from)), None)
    if covering is None:
        return None, None
    return covering.id, valid_from - timedelta(days=1)
