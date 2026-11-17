"""Pure commercial document rules shared by API and persistence services."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum

QUANTITY_QUANTUM = Decimal("0.000001")
PRICE_QUANTUM = Decimal("0.000001")
MONEY_QUANTUM = Decimal("0.01")


class SaleStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


def normalize_quantity(value: Decimal) -> Decimal:
    if not value.is_finite() or value <= 0:
        raise ValueError("La cantidad debe ser un número finito mayor que cero.")
    try:
        result = value.quantize(QUANTITY_QUANTUM)
    except InvalidOperation as exc:
        raise ValueError("La cantidad excede la precisión permitida.") from exc
    if result != value:
        raise ValueError("La cantidad admite hasta seis decimales.")
    return result


def normalize_price(value: Decimal) -> Decimal:
    if not value.is_finite() or value < 0:
        raise ValueError("El precio debe ser un número finito igual o mayor que cero.")
    try:
        result = value.quantize(PRICE_QUANTUM)
    except InvalidOperation as exc:
        raise ValueError("El precio excede la precisión permitida.") from exc
    if result != value:
        raise ValueError("El precio admite hasta seis decimales.")
    return result


def quantity_in_base(quantity: Decimal, factor: Decimal) -> Decimal:
    exact = quantity * factor
    result = exact.quantize(QUANTITY_QUANTUM)
    if result != exact:
        raise ValueError("La equivalencia produce más de seis decimales de unidad base.")
    return result


def line_amount(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return (quantity * unit_price).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
