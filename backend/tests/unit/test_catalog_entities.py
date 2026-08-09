"""Unit tests for catalog domain entities and dataclasses."""

import uuid

from app.domain.entities.catalog import Category, Country, Product, SubCategory, Unit


def test_country_dataclass():
    c = Country(
        id=1,
        name="El Salvador",
        iso_code_2="SV",
        iso_code_3="SLV",
        phone_code="+503",
    )
    assert c.id == 1
    assert c.iso_code_2 == "SV"
    assert c.is_active is True


def test_category_and_subcategory():
    u = uuid.uuid4()
    company_id = uuid.uuid4()
    cat = Category(
        id=10, company_id=company_id, uuid=u, name="Panadería", description="Harinas"
    )
    sub = SubCategory(
        id=1, company_id=company_id, category_id=10, name="Harinas Suaves"
    )

    assert cat.id == 10
    assert cat.uuid == u
    assert sub.category_id == cat.id


def test_unit_and_product():
    company_id = uuid.uuid4()
    u_buy = Unit(id=1, name="Kilogramo", type="Masa")
    u_sale = Unit(id=2, name="Unidad", type="Cantidad")
    p_uuid = uuid.uuid4()

    p = Product(
        id=100,
        company_id=company_id,
        uuid=p_uuid,
        category_id=10,
        sub_category_id=1,
        sku="HAR-001",
        name="Harina de Trigo",
        purchase_unit_id=u_buy.id,
        sale_unit_id=u_sale.id,
        internal_code="INT-HAR-001",
    )

    assert p.sku == "HAR-001"
    assert p.purchase_unit_id == 1
    assert p.internal_code == "INT-HAR-001"
