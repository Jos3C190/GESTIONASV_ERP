"""Clasificación fiscal de productos y unidades para las líneas del DTE.

Fuentes: Catálogos de Hacienda v1.1 (CAT-011 tipo de ítem, CAT-014 unidad de medida,
CAT-015 tributos) y el cuerpo del documento de los esquemas oficiales.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum

from app.core.exceptions import BusinessRuleError


class TaxTreatment(StrEnum):
    TAXED = "taxed"
    EXEMPT = "exempt"
    NOT_SUBJECT = "not_subject"


class DteItemType(StrEnum):
    """CAT-011. El 4 («otros tributos por ítem») no es un producto."""

    GOODS = "1"
    SERVICES = "2"
    BOTH = "3"


#: El IVA lo decide el tipo de venta y de documento, no el producto.
IVA_TAX_CODES = frozenset({"20", "C3"})
OTHER_UNIT = "99"

#: CAT-014 sugerido según el código de la unidad en el ERP; las demás van como «Otra».
SUGGESTED_UNIT_CODES: dict[str, str] = {
    "UNIT": "59",
    "KILOGRAM": "34",
    "GRAM": "39",
    "POUND": "36",
    "LITER": "23",
    "MILLILITER": "26",
    "GALLON": "22",
    "METER": "1",
}


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


def suggested_unit_code(unit_code: str) -> str:
    return SUGGESTED_UNIT_CODES.get(unit_code.strip().upper(), OTHER_UNIT)


def effective_item_type(override: DteItemType | None, product_kind: str) -> DteItemType:
    if override is not None:
        return override
    return DteItemType.SERVICES if product_kind == "service" else DteItemType.GOODS


def validate_tax_codes(
    treatment: TaxTreatment, codes: list[str], known: frozenset[str]
) -> tuple[str, ...]:
    """Tributos adicionales normalizados: sin repetir, en mayúsculas y conocidos."""
    normalized = tuple(dict.fromkeys(code.strip().upper() for code in codes if code.strip()))
    if normalized and treatment != TaxTreatment.TAXED:
        raise _rule(
            "Los tributos adicionales solo aplican a productos gravados.",
            "product_fiscal_taxes_require_taxed",
        )
    iva = [code for code in normalized if code in IVA_TAX_CODES]
    if iva:
        raise _rule(
            "El IVA no se registra en el producto: lo determina el tipo de venta.",
            "product_fiscal_tax_is_iva",
        )
    unknown = [code for code in normalized if code not in known]
    if unknown:
        raise _rule(
            "Estos tributos no están en el catálogo de Hacienda: " + ", ".join(unknown) + ".",
            "product_fiscal_tax_unknown",
        )
    return normalized


def validate_unit_code(code: str, known: frozenset[str]) -> str:
    normalized = code.strip()
    if normalized not in known:
        raise _rule(
            "Ese código no está en el catálogo de unidades de medida de Hacienda.",
            "fiscal_unit_code_unknown",
        )
    return normalized


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class UnitFiscal:
    unit_id: int
    code: str
    name: str
    symbol: str
    is_enabled: bool
    hacienda_unit_code: str | None
    hacienda_unit_name: str | None

    @property
    def suggested_code(self) -> str:
        return suggested_unit_code(self.code)

    @property
    def effective_code(self) -> str:
        return self.hacienda_unit_code or self.suggested_code


@dataclass(frozen=True, slots=True)
class ProductFiscal:
    product_id: int
    product_uuid: uuid.UUID
    sku: str
    name: str
    product_kind: str
    can_sell: bool
    tax_treatment: TaxTreatment
    dte_item_type: DteItemType | None
    additional_taxes: tuple[CatalogEntry, ...]
    sale_unit: UnitFiscal | None

    @property
    def effective_item_type(self) -> DteItemType:
        return effective_item_type(self.dte_item_type, self.product_kind)

    @property
    def billing_issues(self) -> list[str]:
        return billing_issues(self)


def billing_issues(product: ProductFiscal) -> list[str]:
    """Lo que impide facturar el producto, en español. Vacío si no se vende."""
    if not product.can_sell:
        return []
    issues: list[str] = []
    unit = product.sale_unit
    if unit is None or not unit.is_enabled:
        issues.append("La unidad de venta no está habilitada en la empresa.")
    elif unit.hacienda_unit_name is None:
        issues.append("La unidad de venta no tiene un código válido de Hacienda.")
    return issues
