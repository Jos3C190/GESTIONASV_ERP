"""Pedido de venta: estados, entrega, condición de pago y reserva comercial (bloque V2e).

El pedido es el compromiso con el cliente: qué se entrega, cuándo y dónde. Al confirmarlo
aparta existencias de la sucursal (reserva comercial): no mueve unidades físicas, solo baja el
«disponible para vender» hasta que la entrega las consume o el pedido se cancela.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from app.core.exceptions import BusinessRuleError

ZERO = Decimal("0")
MAX_CREDIT_DAYS = 365


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


class OrderStatus(StrEnum):
    DRAFT = "draft"
    PENDING_AUTHORIZATION = "pending_authorization"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


STATUS_TEXT: dict[OrderStatus, str] = {
    OrderStatus.DRAFT: "Borrador",
    OrderStatus.PENDING_AUTHORIZATION: "Por autorizar",
    OrderStatus.CONFIRMED: "Confirmado",
    OrderStatus.CANCELLED: "Cancelado",
}


class DeliveryMode(StrEnum):
    PICKUP = "pickup"
    DELIVERY = "delivery"


class PaymentTerms(StrEnum):
    CASH = "cash"
    CREDIT = "credit"


# --- Estados ---------------------------------------------------------------------------------


def _require(status: OrderStatus, allowed: tuple[OrderStatus, ...], action: str) -> None:
    if status not in allowed:
        raise _rule(
            f"No se puede {action} un pedido en estado {STATUS_TEXT[status]}.",
            "sales_order_status_invalid",
        )


def require_editable(status: OrderStatus) -> None:
    _require(status, (OrderStatus.DRAFT,), "editar")


def confirm_target(status: OrderStatus, requires_authorization: bool) -> OrderStatus:
    """Confirmar un borrador: va a autorización si algo pasa el tope; si no, queda confirmado."""

    _require(status, (OrderStatus.DRAFT,), "confirmar")
    if requires_authorization:
        return OrderStatus.PENDING_AUTHORIZATION
    return OrderStatus.CONFIRMED


def require_pending_authorization(status: OrderStatus) -> None:
    _require(status, (OrderStatus.PENDING_AUTHORIZATION,), "autorizar o devolver")


def require_cancellable(status: OrderStatus, delivered_any: bool) -> None:
    _require(
        status,
        (OrderStatus.DRAFT, OrderStatus.PENDING_AUTHORIZATION, OrderStatus.CONFIRMED),
        "cancelar",
    )
    if delivered_any:
        raise _rule(
            "El pedido ya tiene entregas confirmadas y no se puede cancelar.",
            "sales_order_has_deliveries",
        )


# --- Entrega y pago --------------------------------------------------------------------------


def require_promised_date(promised: date, today: date) -> None:
    if promised < today:
        raise _rule(
            "La fecha comprometida no puede quedar en el pasado.",
            "sales_order_promised_date_past",
        )


def require_delivery_place(mode: DeliveryMode, has_address: bool) -> None:
    if mode is DeliveryMode.DELIVERY and not has_address:
        raise _rule("Elige la dirección de entrega del cliente.", "sales_order_address_required")
    if mode is DeliveryMode.PICKUP and has_address:
        raise _rule(
            "Un pedido con retiro en sucursal no lleva dirección de entrega.",
            "sales_order_address_not_allowed",
        )


@dataclass(frozen=True, slots=True)
class PaymentCondition:
    terms: PaymentTerms
    credit_days: int


def payment_condition(customer_credit_days: int) -> PaymentCondition:
    """La condición de pago del pedido sale del cliente: crédito si tiene días de crédito."""

    days = max(0, min(customer_credit_days, MAX_CREDIT_DAYS))
    if days == 0:
        return PaymentCondition(PaymentTerms.CASH, 0)
    return PaymentCondition(PaymentTerms.CREDIT, days)


# --- Reserva comercial -----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Shortage:
    inventory_item_id: uuid.UUID
    required: Decimal
    available: Decimal


def shortages(
    required: Mapping[uuid.UUID, Decimal], available: Mapping[uuid.UUID, Decimal]
) -> list[Shortage]:
    """Artículos cuyo disponible para vender no alcanza para lo que el pedido aparta."""

    missing = []
    for item, quantity in required.items():
        free = max(ZERO, available.get(item, ZERO))
        if quantity > free:
            missing.append(Shortage(item, quantity, free))
    return missing


def available_to_sell(on_hand: Decimal, reserved: Decimal) -> Decimal:
    """Unidades disponibles en las bodegas de la sucursal menos lo apartado por otros pedidos."""

    return max(ZERO, on_hand - reserved)


def pending_to_deliver(ordered: Decimal, delivered: Decimal) -> Decimal:
    """Lo que un pedido confirmado sigue apartando: lo pedido menos lo ya entregado."""

    return max(ZERO, ordered - delivered)
