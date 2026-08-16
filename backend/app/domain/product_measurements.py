"""Fixed measurement options and deterministic product measurement helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Final, Literal

DimensionUnit = Literal["mm", "cm", "m", "in", "ft"]
WeightUnit = Literal["mg", "g", "kg", "t", "oz", "lb"]

DIMENSION_UNITS: Final[dict[str, str]] = {
    "mm": "Milímetro (mm)",
    "cm": "Centímetro (cm)",
    "m": "Metro (m)",
    "in": "Pulgada (in)",
    "ft": "Pie (ft)",
}
WEIGHT_UNITS: Final[dict[str, str]] = {
    "mg": "Miligramo (mg)",
    "g": "Gramo (g)",
    "kg": "Kilogramo (kg)",
    "t": "Tonelada (t)",
    "oz": "Onza (oz)",
    "lb": "Libra (lb)",
}
DIMENSION_TO_METERS: Final[dict[str, Decimal]] = {
    "mm": Decimal("0.001"),
    "cm": Decimal("0.01"),
    "m": Decimal("1"),
    "in": Decimal("0.0254"),
    "ft": Decimal("0.3048"),
}
WEIGHT_TO_KILOGRAMS: Final[dict[str, Decimal]] = {
    "mg": Decimal("0.000001"),
    "g": Decimal("0.001"),
    "kg": Decimal("1"),
    "t": Decimal("1000"),
    "oz": Decimal("0.028349523125"),
    "lb": Decimal("0.45359237"),
}
MAX_DECIMAL_PLACES: Final[int] = 3


def decimal_value(value: object, *, field: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} debe ser un número válido.") from exc
    if not decimal.is_finite() or decimal < 0:
        raise ValueError(f"{field} debe ser un número no negativo.")
    if decimal.as_tuple().exponent < -MAX_DECIMAL_PLACES:
        raise ValueError(f"{field} admite como máximo tres decimales.")
    return decimal


def validate_measurements(
    *,
    dimension_length: object = None,
    dimension_width: object = None,
    dimension_height: object = None,
    dimension_unit: str | None = None,
    weight: object = None,
    weight_unit: str | None = None,
) -> tuple[Decimal | None, Decimal | None, Decimal | None, Decimal | None]:
    length = decimal_value(dimension_length, field="El largo")
    width = decimal_value(dimension_width, field="El ancho")
    height = decimal_value(dimension_height, field="El alto")
    product_weight = decimal_value(weight, field="El peso")
    has_dimension = any(value is not None for value in (length, width, height))
    if has_dimension and dimension_unit not in DIMENSION_UNITS:
        raise ValueError("Seleccione una unidad de dimensión válida.")
    if not has_dimension and dimension_unit is not None:
        raise ValueError("No puede indicar unidad de dimensión sin medidas.")
    if product_weight is not None and weight_unit not in WEIGHT_UNITS:
        raise ValueError("Seleccione una unidad de peso válida.")
    if product_weight is None and weight_unit is not None:
        raise ValueError("No puede indicar unidad de peso sin peso.")
    return length, width, height, product_weight


def calculate_volume(
    length: Decimal | None,
    width: Decimal | None,
    height: Decimal | None,
    unit: str | None,
) -> Decimal | None:
    if length is None or width is None or height is None or unit not in DIMENSION_TO_METERS:
        return None
    factor = DIMENSION_TO_METERS[unit]
    return length * factor * width * factor * height * factor


def format_dimension_summary(
    length: Decimal | None,
    width: Decimal | None,
    height: Decimal | None,
    unit: str | None,
) -> str | None:
    values = (length, width, height)
    if not any(value is not None for value in values) or unit not in DIMENSION_UNITS:
        return None

    def display(value: Decimal | None) -> str:
        if value is None:
            return "—"
        return format(value.normalize(), "f")

    separator = "\u00d7"
    return f"{display(length)} {separator} {display(width)} {separator} {display(height)} {unit}"
