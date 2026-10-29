"""Exact cost allocation for a staged receipt; no persistence or HTTP dependencies."""

from decimal import Decimal

from app.domain.entities.inventory_valuation import amount


def placement_value(
    *,
    total_quantity: Decimal,
    total_value: Decimal,
    posted_quantity: Decimal,
    posted_value: Decimal,
    quantity: Decimal,
) -> Decimal:
    values = (total_quantity, total_value, posted_quantity, posted_value, quantity)
    if not all(value.is_finite() for value in values):
        raise ValueError("La cantidad o el costo de recepción no son válidos.")
    remaining = total_quantity - posted_quantity
    if total_quantity <= 0 or quantity <= 0 or quantity > remaining:
        raise ValueError("La cantidad supera lo pendiente de ingresar de esta recepción.")
    if min(total_value, posted_quantity, posted_value) < 0 or posted_value > total_value:
        raise ValueError("El costo registrado no coincide con el costo aceptado.")
    return (
        total_value - posted_value
        if quantity == remaining
        else amount((total_value - posted_value) * quantity / remaining)
    )
