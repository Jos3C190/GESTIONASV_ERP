"""Deterministic import-tax arithmetic; rates are supplied by the operator."""

from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Literal

CalculationMode = Literal["automatic", "manual"]
MONEY_QUANTUM = Decimal("0.000001")
MAX_TAX_RATE = Decimal("1000")
MAX_MONEY_AMOUNT = Decimal("999999999999.999999")


def validate_tax_rate(value: Decimal | None) -> Decimal:
    if value is None or not value.is_finite() or not 0 <= value <= MAX_TAX_RATE:
        raise ValueError("Ingrese un porcentaje válido de DAI e IVA, entre 0 y 1000.")
    return value


def calculate_import_taxes(
    total_fob: Decimal, freight: Decimal, dai_rate: Decimal | None, vat_rate: Decimal | None
) -> tuple[Decimal, Decimal]:
    """Freight includes insurance; IVA applies to the customs basis plus DAI."""
    dai_rate, vat_rate = validate_tax_rate(dai_rate), validate_tax_rate(vat_rate)
    if not total_fob.is_finite() or total_fob <= 0:
        raise ValueError("La compra debe tener un FOB neto mayor que cero.")
    if not freight.is_finite() or freight < 0:
        raise ValueError("El flete y seguro deben ser un importe válido mayor o igual a cero.")
    with localcontext() as context:
        context.prec = 42
        basis = total_fob + freight
        dai = (basis * dai_rate / 100).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        vat = ((basis + dai) * vat_rate / 100).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        if max(dai, vat, basis + dai) > MAX_MONEY_AMOUNT:
            raise ValueError("Los importes calculados superan el máximo permitido para el retaceo.")
    return dai, vat
