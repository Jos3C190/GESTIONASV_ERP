"""Focused tests for company-scoped product detail projections."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from app.api.v1.schemas.catalog import ProductResponse, ProductSupplierResponse
from app.infrastructure.repositories import catalog_repository
from app.infrastructure.repositories.catalog_repository import (
    SqlAlchemyCatalogRepository,
    _to_product_supplier,
)


class _Result:
    def __init__(self, row: tuple[object, str | None]) -> None:
        self._row = row

    def one_or_none(self) -> tuple[object, str | None] | None:
        return self._row


class _Session:
    def __init__(self, category_name: str | None) -> None:
        self.category_name = category_name
        self.statement: Any = None

    async def execute(self, statement: Any) -> _Result:
        self.statement = statement
        return _Result((object(), self.category_name))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_product_detail_resolves_category_name_with_company_scoped_outer_join(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _Session("Bebidas y Cafetería")
    captured: dict[str, object] = {}

    def capture_product(_orm: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return kwargs["category_name"]

    monkeypatch.setattr(catalog_repository, "_to_product", capture_product)

    company_id = uuid.uuid4()
    product = await SqlAlchemyCatalogRepository(session).get_product_by_id(company_id, 3)

    assert product == "Bebidas y Cafetería"
    assert captured["category_name"] == "Bebidas y Cafetería"
    assert ProductResponse.model_fields["category_name"].default is None
    sql = str(session.statement)
    assert "LEFT OUTER JOIN categories" in sql
    assert "categories.company_id = products.company_id" in sql


@pytest.mark.unit
@pytest.mark.asyncio
async def test_product_detail_by_uuid_preserves_inactive_category_name_and_unknown_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        catalog_repository,
        "_to_product",
        lambda _orm, **kwargs: kwargs["category_name"],
    )
    company_id = uuid.uuid4()
    product_uuid = uuid.uuid4()

    inactive_session = _Session("Categoría histórica")
    inactive_product = await SqlAlchemyCatalogRepository(inactive_session).get_product_by_uuid(
        company_id, product_uuid
    )
    assert inactive_product == "Categoría histórica"
    assert "categories.is_active" not in str(inactive_session.statement)

    missing_session = _Session(None)
    missing_product = await SqlAlchemyCatalogRepository(missing_session).get_product_by_uuid(
        company_id, product_uuid
    )
    assert missing_product is None


@pytest.mark.unit
def test_product_supplier_maps_loaded_name_and_keeps_legacy_null_fallback() -> None:
    company_id = uuid.uuid4()
    relation = SimpleNamespace(
        id=uuid.uuid4(),
        product_id=4,
        supplier_id=7,
        company_id=company_id,
        supplier=SimpleNamespace(name="Proveedor Lorena", company_id=company_id, deleted_at=None),
        supplier_product_code="PROV-007-HAR-004",
        unit_cost=None,
        currency_code=None,
        minimum_order_qty=None,
        order_multiple=None,
        lead_time_days=3,
        is_preferred=True,
        status="active",
        valid_from=None,
        valid_until=None,
        notes=None,
        created_at=None,
        updated_at=None,
    )

    mapped = _to_product_supplier(relation)
    assert mapped.supplier_name == "Proveedor Lorena"
    assert mapped.supplier_id == 7
    assert ProductSupplierResponse.model_fields["supplier_name"].default is None

    relation.supplier = None
    assert _to_product_supplier(relation).supplier_name is None

    relation.supplier = SimpleNamespace(name="Proveedor eliminado", deleted_at=object())
    assert _to_product_supplier(relation).supplier_name is None

    relation.supplier = SimpleNamespace(
        name="Otra empresa", company_id=uuid.uuid4(), deleted_at=None
    )
    assert _to_product_supplier(relation).supplier_name is None
