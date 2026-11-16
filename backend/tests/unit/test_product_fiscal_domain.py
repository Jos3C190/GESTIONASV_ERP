"""Reglas puras de la clasificación fiscal de productos y unidades."""

from __future__ import annotations

import uuid

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.product_fiscal import (
    CatalogEntry,
    DteItemType,
    ProductFiscal,
    TaxTreatment,
    UnitFiscal,
    effective_item_type,
    suggested_unit_code,
    validate_tax_codes,
    validate_unit_code,
)

KNOWN_TAXES = frozenset({"20", "C3", "D1", "C8", "A8", "54"})
KNOWN_UNITS = frozenset({"59", "34", "99"})


def _unit(
    code: str = "UNIT", hacienda: str | None = None, name: str | None = "Unidad"
) -> UnitFiscal:
    return UnitFiscal(1, code, "Unidad", "u", True, hacienda, name)


def _product(**changes: object) -> ProductFiscal:
    values: dict[str, object] = {
        "product_id": 1,
        "product_uuid": uuid.uuid4(),
        "sku": "PAN-01",
        "name": "Pan francés",
        "product_kind": "goods",
        "can_sell": True,
        "tax_treatment": TaxTreatment.TAXED,
        "dte_item_type": None,
        "additional_taxes": (),
        "sale_unit": _unit(),
    }
    values.update(changes)
    return ProductFiscal(**values)  # type: ignore[arg-type]


def test_suggested_unit_codes_follow_cat_014() -> None:
    assert suggested_unit_code("unit") == "59"
    assert suggested_unit_code("KILOGRAM") == "34"
    assert suggested_unit_code("BOX") == "99"
    assert _unit("BOX").effective_code == "99"
    assert _unit("BOX", hacienda="59").effective_code == "59"


def test_item_type_is_derived_unless_overridden() -> None:
    assert effective_item_type(None, "goods") == DteItemType.GOODS
    assert effective_item_type(None, "service") == DteItemType.SERVICES
    assert effective_item_type(DteItemType.BOTH, "goods") == DteItemType.BOTH


def test_tax_codes_are_normalized() -> None:
    assert validate_tax_codes(TaxTreatment.TAXED, [" d1", "C8", "D1", ""], KNOWN_TAXES) == (
        "D1",
        "C8",
    )


@pytest.mark.parametrize(
    ("treatment", "codes", "error"),
    [
        (TaxTreatment.EXEMPT, ["D1"], "product_fiscal_taxes_require_taxed"),
        (TaxTreatment.TAXED, ["20"], "product_fiscal_tax_is_iva"),
        (TaxTreatment.TAXED, ["ZZ"], "product_fiscal_tax_unknown"),
    ],
)
def test_invalid_tax_codes(treatment: TaxTreatment, codes: list[str], error: str) -> None:
    with pytest.raises(BusinessRuleError) as exc:
        validate_tax_codes(treatment, codes, KNOWN_TAXES)
    assert exc.value.code == error


def test_unit_code_must_exist() -> None:
    assert validate_unit_code(" 59 ", KNOWN_UNITS) == "59"
    with pytest.raises(BusinessRuleError) as exc:
        validate_unit_code("77", KNOWN_UNITS)
    assert exc.value.code == "fiscal_unit_code_unknown"


def test_billing_issues() -> None:
    assert _product().billing_issues == []
    assert _product(can_sell=False, sale_unit=None).billing_issues == []
    disabled = UnitFiscal(1, "UNIT", "Unidad", "u", False, "59", "Unidad")
    assert _product(sale_unit=disabled).billing_issues == [
        "La unidad de venta no está habilitada en la empresa."
    ]
    assert _product(sale_unit=_unit(name=None)).billing_issues == [
        "La unidad de venta no tiene un código válido de Hacienda."
    ]
    service = _product(product_kind="service", additional_taxes=(CatalogEntry("D1", "FOVIAL"),))
    assert service.effective_item_type == DteItemType.SERVICES
