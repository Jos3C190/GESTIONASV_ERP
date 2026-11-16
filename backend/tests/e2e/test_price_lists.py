"""API de listas de precios: vigencias, sucursal, cliente, resolución, permisos y aislamiento."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from app.application.price_lists import today_in_el_salvador
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.catalog import CompanyUnitModel, ProductModel
from app.infrastructure.models.inventory import InventoryItemModel
from app.infrastructure.models.organization import Branch, Company, UserCompany
from httpx import AsyncClient
from sqlalchemy import func, select

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"
BASE = "/api/v1/price-lists"


async def _login(client: AsyncClient, *, superuser: bool) -> tuple[str, dict[str, str]]:
    username = f"prices-{uuid.uuid4().hex[:8]}"
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


async def _list(client: AsyncClient, headers: dict[str, str], code: str, **extra: object) -> dict:
    response = await client.post(
        BASE,
        json={"code": code, "name": f"Lista {code}", "prices_include_vat": True, **extra},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _ensure_inventory_item(company_id: uuid.UUID) -> None:
    """La semilla de API trae productos sin identidad de inventario; se prepara una."""
    async with async_session_factory() as session:
        product = await session.scalar(
            select(ProductModel)
            .join(
                CompanyUnitModel,
                (CompanyUnitModel.company_id == ProductModel.company_id)
                & (CompanyUnitModel.unit_id == ProductModel.sale_unit),
            )
            .where(
                ProductModel.company_id == company_id,
                ProductModel.is_active.is_(True),
                ProductModel.can_sell.is_(True),
                ProductModel.product_kind == "goods",
                ProductModel.lifecycle_status == "active",
                ProductModel.variant_mode == "standalone",
                ProductModel.deleted_at.is_(None),
                CompanyUnitModel.is_enabled.is_(True),
            )
            .order_by(ProductModel.id_product)
            .limit(1)
        )
        assert product is not None, "La semilla debe tener un producto vendible."
        item = await session.scalar(
            select(InventoryItemModel).where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.product_id == product.id_product,
            )
        )
        if item is None:
            session.add(
                InventoryItemModel(
                    company_id=company_id,
                    product_id=product.id_product,
                    base_unit_id=product.sale_unit,
                    is_active=True,
                )
            )
            await session.commit()


async def _unit(client: AsyncClient, headers: dict[str, str]) -> dict:
    await _ensure_inventory_item(uuid.UUID(headers["X-Company-ID"]))
    response = await client.get(f"{BASE}/sellable-units", headers=headers)
    assert response.status_code == 200, response.text
    units = response.json()
    assert units, "el entorno de prueba necesita productos vendibles con artículo de inventario"
    return units[0]


async def _branch(company_id: uuid.UUID) -> uuid.UUID:
    async with async_session_factory() as session:
        branch_id = await session.scalar(
            select(Branch.id)
            .where(Branch.company_id == company_id, Branch.deleted_at.is_(None))
            .limit(1)
        )
    assert branch_id is not None
    return branch_id


def _price(unit: dict, price: str, **extra: object) -> dict[str, object]:
    return {
        "product_id": unit["product_id"],
        "variant_id": unit["variant_id"],
        "unit_id": unit["unit_id"],
        "price": price,
        **extra,
    }


def _resolve_params(unit: dict, **extra: object) -> dict[str, object]:
    params: dict[str, object] = {"product_id": unit["product_id"], "unit_id": unit["unit_id"]}
    if unit["variant_id"]:
        params["variant_id"] = unit["variant_id"]
    params.update({k: v for k, v in extra.items() if v is not None})
    return params


async def test_first_list_is_default_and_default_is_unique(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    existing = (await e2e_client.get(BASE, headers=headers)).json()
    first = await _list(e2e_client, headers, f"A{uuid.uuid4().hex[:6].upper()}")
    assert first["is_default"] is (not any(item["is_default"] for item in existing))
    second = await _list(e2e_client, headers, f"B{uuid.uuid4().hex[:6].upper()}", is_default=True)
    lists = (await e2e_client.get(BASE, headers=headers)).json()
    assert [item["id"] for item in lists if item["is_default"]] == [second["id"]]

    payload = {"code": second["code"], "name": second["name"], "prices_include_vat": True}
    lost = await e2e_client.put(
        f"{BASE}/{second['id']}", json={**payload, "is_default": False}, headers=headers
    )
    assert lost.status_code == 422
    assert lost.json()["code"] == "price_list_default_required"
    duplicate = await e2e_client.post(
        BASE,
        json={"code": second["code"].lower(), "name": "Otra", "prices_include_vat": False},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "price_list_code_taken"


async def test_price_changes_keep_history_and_resolve_by_branch_and_date(
    e2e_client: AsyncClient,
) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    company_id = uuid.UUID(headers["X-Company-ID"])
    price_list = await _list(
        e2e_client, headers, f"M{uuid.uuid4().hex[:6].upper()}", is_default=True
    )
    unit = await _unit(e2e_client, headers)
    url = f"{BASE}/{price_list['id']}/prices"
    today = today_in_el_salvador()
    future = today + timedelta(days=10)

    current = await e2e_client.post(url, json=_price(unit, "1.13"), headers=headers)
    assert current.status_code == 201, current.text
    assert current.json()["status"] == "current"
    scheduled = await e2e_client.post(
        url, json=_price(unit, "1.25", valid_from=future.isoformat()), headers=headers
    )
    assert scheduled.status_code == 201, scheduled.text
    assert scheduled.json()["status"] == "scheduled"

    backdated = await e2e_client.post(
        url,
        json=_price(unit, "1", valid_from=(today - timedelta(days=1)).isoformat()),
        headers=headers,
    )
    assert backdated.json()["code"] == "price_list_backdated"
    jumped = await e2e_client.post(
        url,
        json=_price(unit, "1.20", valid_from=(today + timedelta(days=3)).isoformat()),
        headers=headers,
    )
    assert jumped.status_code == 409
    assert jumped.json()["code"] == "price_list_future_exists"

    branch_id = await _branch(company_id)
    own = await e2e_client.post(
        url, json=_price(unit, "1.50", branch_id=str(branch_id)), headers=headers
    )
    assert own.status_code == 201, own.text

    resolve = "/api/v1/sales/prices/resolve"
    general = await e2e_client.get(resolve, params=_resolve_params(unit), headers=headers)
    assert general.status_code == 200, general.text
    assert general.json()["price"] == "1.13000000"
    assert general.json()["source"] == "default"
    assert general.json()["prices_include_vat"] is True
    at_branch = await e2e_client.get(
        resolve, params=_resolve_params(unit, branch_id=str(branch_id)), headers=headers
    )
    assert at_branch.json()["price"] == "1.50000000"
    assert at_branch.json()["branch_specific"] is True
    later = await e2e_client.get(
        resolve, params=_resolve_params(unit, on=future.isoformat()), headers=headers
    )
    assert later.json()["price"] == "1.25000000"

    history = await e2e_client.get(
        f"{BASE}/{price_list['id']}/history",
        params=_resolve_params(unit),
        headers=headers,
    )
    assert history.status_code == 200, history.text
    assert len(history.json()) == 3
    closed = next(e for e in history.json() if e["price"] == "1.13000000")
    assert closed["valid_to"] == (future - timedelta(days=1)).isoformat()

    cancelled = await e2e_client.delete(f"{BASE}/items/{scheduled.json()['id']}", headers=headers)
    assert cancelled.status_code == 204, cancelled.text
    reopened = await e2e_client.get(
        f"{BASE}/{price_list['id']}/history", params=_resolve_params(unit), headers=headers
    )
    assert next(e for e in reopened.json() if e["price"] == "1.13000000")["valid_to"] is None
    not_scheduled = await e2e_client.delete(f"{BASE}/items/{current.json()['id']}", headers=headers)
    assert not_scheduled.json()["code"] == "price_list_not_scheduled"

    ended = await e2e_client.post(
        f"{BASE}/items/{own.json()['id']}/end",
        json={"ends_on": today.isoformat()},
        headers=headers,
    )
    assert ended.status_code == 200, ended.text
    assert ended.json()["valid_to"] == today.isoformat()

    listed = await e2e_client.get(
        url, params={"branch_id": str(branch_id), "search": unit["sku"]}, headers=headers
    )
    assert listed.status_code == 200, listed.text
    row = next(r for r in listed.json() if r["unit"]["unit_id"] == unit["unit_id"])
    assert row["current"]["price"] == "1.50000000"
    assert row["branch_overrides"] == 1

    async with async_session_factory() as session:
        audited = await session.scalar(
            select(func.count()).where(
                AuditLog.company_id == company_id,
                AuditLog.resource_type == "price_list_item",
            )
        )
    assert audited is not None
    assert audited >= 5


async def test_customer_list_wins_over_default(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    default = await _list(e2e_client, headers, f"D{uuid.uuid4().hex[:6].upper()}", is_default=True)
    wholesale = await _list(
        e2e_client, headers, f"W{uuid.uuid4().hex[:6].upper()}", prices_include_vat=False
    )
    inactive = await _list(e2e_client, headers, f"I{uuid.uuid4().hex[:6].upper()}", is_active=False)
    unit = await _unit(e2e_client, headers)
    for price_list, price in ((default, "1.13"), (wholesale, "0.90")):
        saved = await e2e_client.post(
            f"{BASE}/{price_list['id']}/prices", json=_price(unit, price), headers=headers
        )
        assert saved.status_code == 201, saved.text

    rejected = await e2e_client.post(
        "/api/v1/customers",
        json={"name": "Ana López", "price_list_id": inactive["id"]},
        headers=headers,
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "customer_price_list_invalid"
    customer = await e2e_client.post(
        "/api/v1/customers",
        json={"name": "Ana López", "price_list_id": wholesale["id"]},
        headers=headers,
    )
    assert customer.status_code == 201, customer.text
    assert customer.json()["price_list_name"] == wholesale["name"]

    resolved = await e2e_client.get(
        "/api/v1/sales/prices/resolve",
        params=_resolve_params(unit, customer_id=customer.json()["id"]),
        headers=headers,
    )
    assert resolved.json()["price"] == "0.90000000"
    assert resolved.json()["source"] == "customer"
    assert resolved.json()["prices_include_vat"] is False

    missing = await e2e_client.get(
        "/api/v1/sales/prices/resolve",
        params={"product_id": unit["product_id"], "unit_id": 999_999},
        headers=headers,
    )
    assert missing.status_code == 200
    assert missing.json()["found"] is False
    assert "no tiene precio" in missing.json()["message"]


async def test_unit_must_be_a_selling_form(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    price_list = await _list(e2e_client, headers, f"U{uuid.uuid4().hex[:6].upper()}")
    unit = await _unit(e2e_client, headers)
    wrong = await e2e_client.post(
        f"{BASE}/{price_list['id']}/prices",
        json={**_price(unit, "1"), "unit_id": 999_999},
        headers=headers,
    )
    assert wrong.status_code == 422
    assert wrong.json()["code"] == "price_list_unit_invalid"
    unknown = await e2e_client.post(
        f"{BASE}/{price_list['id']}/prices",
        json={**_price(unit, "1"), "product_id": 999_999},
        headers=headers,
    )
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "price_list_product_not_sellable"


async def test_another_company_never_sees_the_list(e2e_client: AsyncClient) -> None:
    user_id, headers = await _login(e2e_client, superuser=True)
    price_list = await _list(e2e_client, headers, f"X{uuid.uuid4().hex[:6].upper()}")
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
    assert (await e2e_client.get(BASE, headers=other_headers)).json() == []
    hidden = await e2e_client.get(f"{BASE}/{price_list['id']}", headers=other_headers)
    assert hidden.status_code == 404
    customer = await e2e_client.post(
        "/api/v1/customers",
        json={"name": "Ana López", "price_list_id": price_list["id"]},
        headers=other_headers,
    )
    assert customer.json()["code"] == "customer_price_list_invalid"
    nothing = await e2e_client.get(
        "/api/v1/sales/prices/resolve",
        params={"product_id": 1, "unit_id": 1, "on": date(2026, 11, 16).isoformat()},
        headers=other_headers,
    )
    assert nothing.json()["found"] is False
    assert nothing.json()["price_list_id"] is None


async def test_price_lists_require_permissions(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=False)
    assert (await e2e_client.get(BASE, headers=headers)).status_code == 403
    denied = await e2e_client.post(
        BASE, json={"code": "L1", "name": "Lista", "prices_include_vat": True}, headers=headers
    )
    assert denied.status_code == 403
    resolve = await e2e_client.get(
        "/api/v1/sales/prices/resolve", params={"product_id": 1, "unit_id": 1}, headers=headers
    )
    assert resolve.status_code == 403
