"""Margen, precio sugerido, descuentos y topes por rol (bloque V2c).

El margen se mide sobre el precio sin IVA: (precio - costo) / precio. El costo es el costo
promedio de inventario, que ya incluye el retaceo. Un precio de una lista con IVA se lleva a
sin IVA antes de comparar.

Nunca se vende por debajo del costo (pedido del ingeniero, 24/11/2026): no es un motivo de
autorización sino un bloqueo, sin excepción por rol.
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
    PROMOTION = "promotion"
    """Promoción de la sucursal: reemplaza a los demás descuentos y el vendedor no la cambia."""


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


UNLIMITED = DiscountPolicy(HUNDRED, HUNDRED)
NONE_ALLOWED = DiscountPolicy(ZERO, ZERO)


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
    )


class AuthorizationReason(StrEnum):
    DISCOUNT_ABOVE_LIMIT = "discount_above_limit"
    BELOW_COST = "below_cost"
    """Ya no se genera: vender bajo costo se bloquea. Queda para leer documentos anteriores."""
    GLOBAL_DISCOUNT_ABOVE_LIMIT = "global_discount_above_limit"
    # Crédito (V5b): los autoriza quien tiene ``sales_credit:authorize``.
    CREDIT_LIMIT_EXCEEDED = "credit_limit_exceeded"
    CUSTOMER_OVERDUE = "customer_overdue"
    CUSTOMER_BLOCKED = "customer_blocked"


REASON_TEXT: dict[AuthorizationReason, str] = {
    AuthorizationReason.DISCOUNT_ABOVE_LIMIT: "El descuento supera el tope de tu rol.",
    AuthorizationReason.BELOW_COST: "Queda por debajo del costo: no se puede vender así.",
    AuthorizationReason.GLOBAL_DISCOUNT_ABOVE_LIMIT: "El descuento global supera el tope de tu rol.",
    AuthorizationReason.CREDIT_LIMIT_EXCEEDED: "El pedido pasa el límite de crédito del cliente.",
    AuthorizationReason.CUSTOMER_OVERDUE: "El cliente tiene saldos vencidos.",
    AuthorizationReason.CUSTOMER_BLOCKED: "El crédito del cliente está bloqueado.",
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
    below_cost: bool = False
    """El precio neto sin IVA queda por debajo del costo: no se puede vender así."""

    @property
    def requires_authorization(self) -> bool:
        return bool(self.reasons)


def is_below_cost(net_without_vat: Decimal, cost: Decimal | None) -> bool:
    return cost is not None and net_without_vat < cost


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
    return LineEvaluation(
        list_price=list_price,
        discount_percent=discount_percent,
        net_price=net,
        cost=cost,
        margin_percent=margin_percent(net, includes_vat, cost),
        reasons=tuple(reasons),
        below_cost=is_below_cost(without_vat(net, includes_vat), cost),
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


# --- promociones por sucursal (pedido del ingeniero, 24/11/2026) ------------------------------


@dataclass(frozen=True, slots=True)
class BranchPromotion:
    """Porcentaje de descuento de un producto en una sucursal, con vigencia."""

    id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID
    product_id: int
    discount_percent: Decimal
    valid_from: date
    valid_to: date | None
    notes: str | None = None
    ended: bool = False
    branch_name: str | None = None
    product_name: str | None = None
    product_sku: str | None = None

    def covers(self, day: date) -> bool:
        return (
            not self.ended
            and self.valid_from <= day
            and (self.valid_to is None or day <= self.valid_to)
        )

    def overlaps(self, valid_from: date, valid_to: date | None) -> bool:
        if self.ended:
            return False
        starts_before_other_ends = valid_to is None or self.valid_from <= valid_to
        ends_after_other_starts = self.valid_to is None or valid_from <= self.valid_to
        return starts_before_other_ends and ends_after_other_starts


def require_promotion(
    discount_percent: Decimal, valid_from: date, valid_to: date | None, today: date
) -> None:
    if not ZERO < discount_percent < HUNDRED:
        raise _rule(
            "El descuento de la promoción va de más de 0 % a menos de 100 %.",
            "sales_promotion_percent_invalid",
        )
    if valid_from < today:
        raise _rule(
            "Una promoción rige desde hoy o desde una fecha futura.", "sales_promotion_backdated"
        )
    if valid_to is not None and valid_to < valid_from:
        raise _rule(
            "La promoción no puede terminar antes de empezar.", "sales_promotion_validity_invalid"
        )


def require_no_overlap(
    existing: list[BranchPromotion], valid_from: date, valid_to: date | None
) -> None:
    """Un producto tiene a lo sumo una promoción vigente por sucursal en cada día."""

    clash = next((p for p in existing if p.overlaps(valid_from, valid_to)), None)
    if clash is not None:
        until = f" hasta el {clash.valid_to:%d/%m/%Y}" if clash.valid_to else " sin fecha de fin"
        raise ConflictError(
            f"Ese producto ya tiene una promoción del {clash.discount_percent.normalize()} % en esa "
            f"sucursal desde el {clash.valid_from:%d/%m/%Y}{until}. Termínala antes de crear otra.",
            code="sales_promotion_overlap",
        )
