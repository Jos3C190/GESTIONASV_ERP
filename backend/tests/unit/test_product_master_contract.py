"""Pure contract tests for the product master enrichment."""

from datetime import date
from decimal import Decimal

import pytest
from app.api.v1.schemas.catalog import (
    ProductCreate,
    ProductIdentifierCreate,
    ProductSupplierCreate,
    ProductSupplierReplace,
)
from pydantic import ValidationError


def _product(**overrides: object) -> ProductCreate:
    data: dict[str, object] = {
        "id_category": 1,
        "sku": "SKU-001",
        "name": "Producto",
        "purchase_unit": 1,
        "sale_unit": 1,
    }
    data.update(overrides)
    return ProductCreate.model_validate(data)


def test_service_cannot_receive_storage_rules() -> None:
    with pytest.raises(ValidationError, match="almacenamiento"):
        _product(product_kind="service", storage_condition="ambient")


def test_goods_accept_structured_master_data() -> None:
    product = _product(
        sales_name="Producto comercial",
        keywords=["uno", "uno", "dos"],
        storage_condition="refrigerated",
        storage_temperature_min_c=Decimal("2"),
        storage_temperature_max_c=Decimal("8"),
    )
    assert product.product_kind == "goods"
    assert product.storage_temperature_max_c == Decimal("8")


def test_identifier_validates_gtin_check_digit() -> None:
    ProductIdentifierCreate(identifier_type="ean", value="4006381333931")
    with pytest.raises(ValidationError, match="dígito"):
        ProductIdentifierCreate(identifier_type="ean", value="4006381333930")


def test_product_accepts_multiple_identifiers_and_rejects_duplicates() -> None:
    product = _product(
        identifiers=[
            {"identifier_type": "ean", "value": "4006381333931", "is_primary": True},
            {"identifier_type": "internal", "value": "HAR-001"},
        ]
    )
    assert len(product.identifiers or []) == 2
    with pytest.raises(ValidationError, match="repetir"):
        _product(
            identifiers=[
                {"identifier_type": "internal", "value": "HAR-001"},
                {"identifier_type": "internal", "value": "HAR001"},
            ]
        )


def test_supplier_terms_require_currency_for_cost_and_coherent_dates() -> None:
    with pytest.raises(ValidationError, match="moneda"):
        ProductSupplierCreate(supplier_id=1, unit_cost=Decimal("2"))
    with pytest.raises(ValidationError, match="vigencia"):
        ProductSupplierCreate(supplier_id=1, valid_from=date(2026, 2, 1), valid_until=date(2026, 1, 1))


def test_supplier_replace_payload_supports_empty_set() -> None:
    assert ProductSupplierReplace().suppliers == []
