"""Documented conversion: source-currency units per one valuation-currency unit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

ISO_CURRENCY_LENGTH = 3
MIN_REFERENCE_LENGTH = 3
MAX_REFERENCE_LENGTH = 500


@dataclass(frozen=True, slots=True)
class PurchaseValuationConversion:
    currency: str
    rate: Decimal
    effective_date: date
    reference: str

    def __post_init__(self) -> None:
        if (
            len(self.currency) != ISO_CURRENCY_LENGTH
            or not self.currency.isascii()
            or not self.currency.isupper()
        ):
            raise ValueError("La moneda de valoración debe ser un código ISO de tres letras.")
        if not self.currency.isalpha():
            raise ValueError("La moneda de valoración debe ser un código ISO de tres letras.")
        if not self.rate.is_finite() or self.rate <= 0 or self.rate >= Decimal("1e12"):
            raise ValueError(
                "El tipo de cambio debe ser positivo y tener hasta doce dígitos enteros."
            )
        if self.rate != self.rate.quantize(Decimal("0.000000000001")):
            raise ValueError("El tipo de cambio admite hasta doce decimales.")
        if not isinstance(self.effective_date, date):
            raise TypeError("Indique la fecha del tipo de cambio.")
        if not MIN_REFERENCE_LENGTH <= len(self.reference.strip()) <= MAX_REFERENCE_LENGTH:
            raise ValueError("Indique una referencia del tipo de cambio de 3 a 500 caracteres.")

    def convert(self, source_value: Decimal) -> Decimal:
        with localcontext() as context:
            context.prec = 50
            converted = (source_value / self.rate).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            )
        if not converted.is_finite() or abs(converted) >= Decimal("1e18"):
            raise ValueError("El importe convertido supera el máximo admitido por inventario.")
        return converted

    def to_dict(self) -> dict[str, str]:
        return {
            "currency": self.currency,
            "rate": str(self.rate),
            "effective_date": self.effective_date.isoformat(),
            "reference": self.reference.strip(),
        }

    @classmethod
    def from_dict(cls, value: dict[str, str]) -> PurchaseValuationConversion:
        return cls(
            currency=value["currency"],
            rate=Decimal(value["rate"]),
            effective_date=date.fromisoformat(value["effective_date"]),
            reference=value["reference"],
        )
