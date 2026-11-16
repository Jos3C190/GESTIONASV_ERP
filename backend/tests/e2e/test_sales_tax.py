"""API del cálculo fiscal de venta: datos de la empresa, reglas, permisos y aislamiento."""

from __future__ import annotations

import uuid

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.models.organization import Company, UserCompany
from httpx import AsyncClient
from sqlalchemy import select, update

from tests.e2e.conftest import get_test_company_id, seed_user
from tests.e2e.test_customers import _geography, _taxpayer

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"
URL = "/api/v1/sales/tax-calculation"


async def _login(client: AsyncClient, *, superuser: bool) -> tuple[str, dict[str, str]]:
    username = f"sales-tax-{uuid.uuid4().hex[:8]}"
    user_id = await seed_user(
        username=username,
        email=f"{username}@example.com",
        password=PASSWORD,
        is_superuser=superuser,
    )
    login = await client.post("/api/v1/auth/login", json={"login": username, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return user_id, {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Company-ID": str(await get_test_company_id()),
    }


async def _product_ids(company_id: uuid.UUID, count: int = 2) -> list[int]:
    async with async_session_factory() as session:
        rows = (
            await session.scalars(
                select(ProductModel.id_product)
                .where(ProductModel.company_id == company_id, ProductModel.deleted_at.is_(None))
                .order_by(ProductModel.id_product)
                .limit(count)
            )
        ).all()
        await session.execute(
            update(ProductModel).where(ProductModel.id_product.in_(rows)).values(can_sell=True)
        )
        await session.commit()
    assert len(rows) == count
    return [int(r) for r in rows]


async def _enable(client: AsyncClient, headers: dict[str, str], *documents: str) -> None:
    for document in documents:
        response = await client.put(
            f"/api/v1/fiscal/document-types/{document}",
            json={"is_enabled": True, "certification_status": "pending"},
            headers=headers,
        )
        assert response.status_code == 200, response.text


async def _issuer_category(client: AsyncClient, headers: dict[str, str], category: str) -> None:
    response = await client.put(
        "/api/v1/fiscal/profile",
        json={
            "taxpayer_category": category,
            "person_type": "2",
            "operating_mode": "simulated",
            "dte_email": "facturacion@example.com",
            "dte_phone": "2222-0000",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text


def _line(product_id: int, quantity: str, price: str, **extra: object) -> dict[str, object]:
    return {
        "product_id": product_id,
        "quantity": quantity,
        "unit_price": price,
        "price_includes_vat": False,
        **extra,
    }


async def test_same_product_in_invoice_and_tax_credit(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    product, _ = await _product_ids(uuid.UUID(headers["X-Company-ID"]))
    await _enable(e2e_client, headers, "01", "03")
    await _issuer_category(e2e_client, headers, "other")

    invoice = await e2e_client.post(
        URL, json={"document_type": "01", "lines": [_line(product, "1", "1.00")]}, headers=headers
    )
    assert invoice.status_code == 200, invoice.text
    body = invoice.json()
    assert body["prices_include_vat"] is True
    assert body["lines"][0]["unit_price"] == "1.13000000"
    assert body["lines"][0]["vat_item"] == "0.13000000"
    assert body["summary"]["vat"] == "0.13"
    assert body["summary"]["total_to_pay"] == "1.13"
    assert body["summary"]["total_in_words"] == "UNO 13/100 DÓLARES"
    assert body["customer_id"] is None

    geography = await _geography()
    customer = await e2e_client.post(
        "/api/v1/customers",
        json={**_taxpayer(geography), "taxpayer_category": "large"},
        headers=headers,
    )
    assert customer.status_code == 201, customer.text
    credit = await e2e_client.post(
        URL,
        json={
            "document_type": "03",
            "customer_id": customer.json()["id"],
            "lines": [_line(product, "1", "113.00", price_includes_vat=True)],
        },
        headers=headers,
    )
    assert credit.status_code == 200, credit.text
    summary = credit.json()["summary"]
    assert credit.json()["lines"][0]["unit_price"] == "100.00000000"
    assert summary["vat"] == "13.00"
    assert summary["vat_withheld"] == "1.00"  # gran contribuyente retiene el 1 %
    assert summary["total_operation"] == "112.00"


async def test_large_issuer_perceives_on_goods(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    product, _ = await _product_ids(uuid.UUID(headers["X-Company-ID"]))
    await _enable(e2e_client, headers, "03")
    await _issuer_category(e2e_client, headers, "large")
    customer = await e2e_client.post(
        "/api/v1/customers",
        json={
            **_taxpayer(await _geography()),
            "nrc": "765432-1",
            "document_number": "0614-020202-102-2",
        },
        headers=headers,
    )
    assert customer.status_code == 201, customer.text
    credit = await e2e_client.post(
        URL,
        json={
            "document_type": "03",
            "customer_id": customer.json()["id"],
            "lines": [_line(product, "2", "75.00")],
            "global_discounts": {"taxed": "0"},
        },
        headers=headers,
    )
    assert credit.status_code == 200, credit.text
    assert credit.json()["summary"]["vat_perceived"] == "1.50"
    assert credit.json()["summary"]["total_operation"] == "171.00"
    await _issuer_category(e2e_client, headers, "other")


async def test_document_rules(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    product, second = await _product_ids(uuid.UUID(headers["X-Company-ID"]))
    await _enable(e2e_client, headers, "01", "03")

    no_customer = await e2e_client.post(
        URL, json={"document_type": "03", "lines": [_line(product, "1", "1")]}, headers=headers
    )
    assert no_customer.status_code == 422
    assert no_customer.json()["code"] == "sales_tax_customer_required"

    consumer = await e2e_client.post(
        "/api/v1/customers", json={"name": "Ana López"}, headers=headers
    )
    assert consumer.status_code == 201, consumer.text
    not_receivable = await e2e_client.post(
        URL,
        json={
            "document_type": "03",
            "customer_id": consumer.json()["id"],
            "lines": [_line(product, "1", "1")],
        },
        headers=headers,
    )
    assert not_receivable.status_code == 422
    assert not_receivable.json()["code"] == "sales_tax_document_not_receivable"

    saved = await e2e_client.put(
        f"/api/v1/products/{second}/fiscal",
        json={"tax_treatment": "taxed", "additional_tax_codes": ["D1"]},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    additional = await e2e_client.post(
        URL, json={"document_type": "01", "lines": [_line(second, "1", "1")]}, headers=headers
    )
    assert additional.status_code == 422
    assert additional.json()["code"] == "sales_tax_additional_unsupported"
    await e2e_client.put(
        f"/api/v1/products/{second}/fiscal",
        json={"tax_treatment": "taxed", "additional_tax_codes": []},
        headers=headers,
    )

    excessive = await e2e_client.post(
        URL,
        json={
            "document_type": "01",
            "lines": [_line(product, "1", "1")],
            "global_discounts": {"exempt": "1.00"},
        },
        headers=headers,
    )
    assert excessive.status_code == 422
    assert excessive.json()["code"] == "sales_tax_global_discount_exceeds"

    missing = await e2e_client.post(
        URL, json={"document_type": "01", "lines": [_line(999_999_999, "1", "1")]}, headers=headers
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "product_not_found"

    invalid = await e2e_client.post(
        URL, json={"document_type": "05", "lines": [_line(product, "1", "1")]}, headers=headers
    )
    assert invalid.status_code == 422


async def test_disabled_document_and_company_isolation(e2e_client: AsyncClient) -> None:
    user_id, headers = await _login(e2e_client, superuser=True)
    product, _ = await _product_ids(uuid.UUID(headers["X-Company-ID"]))
    async with async_session_factory() as session:
        original = await session.get(Company, uuid.UUID(headers["X-Company-ID"]))
        assert original is not None
        suffix = uuid.uuid4().hex[:8]
        other = Company(
            name=f"Otra {suffix}, S.A. de C.V.",
            commercial_name=f"Otra {suffix}",
            nit=f"{uuid.uuid4().int % 10**14:014d}",
            nrc=f"{uuid.uuid4().int % 10**6:06d}",
            address="Aislada",
            department_id=original.department_id,
            municipality_id=original.municipality_id,
            district_id=original.district_id,
        )
        session.add(other)
        await session.flush()
        session.add(UserCompany(user_id=uuid.UUID(user_id), company_id=other.id))
        await session.commit()
        other_id = other.id
    other_headers = {**headers, "X-Company-ID": str(other_id)}
    disabled = await e2e_client.post(
        URL,
        json={"document_type": "01", "lines": [_line(product, "1", "1")]},
        headers=other_headers,
    )
    assert disabled.status_code == 422
    assert disabled.json()["code"] == "sales_tax_document_disabled"
    await _enable(e2e_client, other_headers, "01")
    foreign_product = await e2e_client.post(
        URL,
        json={"document_type": "01", "lines": [_line(product, "1", "1")]},
        headers=other_headers,
    )
    assert foreign_product.status_code == 404
    assert foreign_product.json()["code"] == "product_not_found"


async def test_calculation_requires_sales_permission(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=False)
    product, _ = await _product_ids(uuid.UUID(headers["X-Company-ID"]))
    denied = await e2e_client.post(
        URL, json={"document_type": "01", "lines": [_line(product, "1", "1")]}, headers=headers
    )
    assert denied.status_code == 403
