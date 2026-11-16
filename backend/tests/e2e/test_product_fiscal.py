"""API de clasificación fiscal de productos y unidades: reglas, auditoría, permisos y aislamiento."""

from __future__ import annotations

import uuid

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.models.organization import Company, UserCompany
from httpx import AsyncClient
from sqlalchemy import func, select

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"


async def _login(client: AsyncClient, *, superuser: bool) -> tuple[str, dict[str, str]]:
    username = f"fiscal-prod-{uuid.uuid4().hex[:8]}"
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


async def _product_id(company_id: uuid.UUID) -> int:
    async with async_session_factory() as session:
        product_id = await session.scalar(
            select(ProductModel.id_product)
            .where(ProductModel.company_id == company_id, ProductModel.deleted_at.is_(None))
            .order_by(ProductModel.id_product)
            .limit(1)
        )
    assert product_id is not None
    return int(product_id)


async def test_options_exclude_iva(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    response = await e2e_client.get("/api/v1/product-fiscal/options", headers=headers)
    assert response.status_code == 200, response.text
    taxes = {t["code"] for t in response.json()["taxes"]}
    assert {"D1", "C8"} <= taxes
    assert not taxes & {"20", "C3"}
    assert {"code": "59", "name": "Unidad"} in response.json()["units"]


async def test_product_classification_is_validated_and_audited(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    company_id = uuid.UUID(headers["X-Company-ID"])
    product_id = await _product_id(company_id)
    url = f"/api/v1/products/{product_id}/fiscal"
    current = await e2e_client.get(url, headers=headers)
    assert current.status_code == 200, current.text
    assert current.json()["tax_treatment"] == "taxed"
    assert current.json()["effective_item_type"] == "1"

    rejected = await e2e_client.put(
        url,
        json={"tax_treatment": "exempt", "additional_tax_codes": ["D1"]},
        headers=headers,
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "product_fiscal_taxes_require_taxed"
    iva = await e2e_client.put(
        url, json={"tax_treatment": "taxed", "additional_tax_codes": ["20"]}, headers=headers
    )
    assert iva.json()["code"] == "product_fiscal_tax_is_iva"

    saved = await e2e_client.put(
        url,
        json={"tax_treatment": "taxed", "dte_item_type": "3", "additional_tax_codes": ["d1", "C8"]},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["effective_item_type"] == "3"
    assert [t["code"] for t in body["additional_taxes"]] == ["D1", "C8"]
    async with async_session_factory() as session:
        audited = await session.scalar(
            select(func.count()).where(
                AuditLog.company_id == company_id,
                AuditLog.resource_type == "product_fiscal",
                AuditLog.resource_id == str(product_id),
            )
        )
    assert audited == 1


async def test_unit_codes_per_company(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    units = await e2e_client.get("/api/v1/fiscal/units", headers=headers)
    assert units.status_code == 200, units.text
    by_code = {u["code"]: u for u in units.json()}
    assert by_code["UNIT"]["effective_code"] == "59"
    box = by_code["BOX"]
    assert box["effective_code"] == "99"
    url = f"/api/v1/fiscal/units/{box['unit_id']}"
    unknown = await e2e_client.put(url, json={"hacienda_unit_code": "77"}, headers=headers)
    assert unknown.status_code == 422
    assert unknown.json()["code"] == "fiscal_unit_code_unknown"
    saved = await e2e_client.put(url, json={"hacienda_unit_code": "59"}, headers=headers)
    assert saved.json()["effective_code"] == "59"
    cleared = await e2e_client.put(url, json={"hacienda_unit_code": None}, headers=headers)
    assert cleared.json()["hacienda_unit_code"] is None
    assert cleared.json()["effective_code"] == "99"  # vuelve a la sugerencia


async def test_another_company_cannot_touch_the_product(e2e_client: AsyncClient) -> None:
    user_id, headers = await _login(e2e_client, superuser=True)
    product_id = await _product_id(uuid.UUID(headers["X-Company-ID"]))
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
    response = await e2e_client.get(f"/api/v1/products/{product_id}/fiscal", headers=other_headers)
    assert response.status_code == 404
    units = await e2e_client.get("/api/v1/fiscal/units", headers=other_headers)
    by_code = {u["code"]: u for u in units.json()}
    # Las unidades que recibe una empresa nueva no traen código guardado: usan la sugerencia.
    assert by_code["BOX"]["hacienda_unit_code"] is None
    assert by_code["BOX"]["effective_code"] == "99"
    assert by_code["UNIT"]["effective_code"] == "59"


async def test_classification_requires_permissions(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=False)
    product_id = await _product_id(uuid.UUID(headers["X-Company-ID"]))
    assert (
        await e2e_client.get(f"/api/v1/products/{product_id}/fiscal", headers=headers)
    ).status_code == 403
    denied = await e2e_client.put(
        f"/api/v1/products/{product_id}/fiscal", json={"tax_treatment": "taxed"}, headers=headers
    )
    assert denied.status_code == 403
    assert (await e2e_client.get("/api/v1/fiscal/units", headers=headers)).status_code == 403
