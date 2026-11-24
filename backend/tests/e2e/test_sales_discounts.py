"""V2c: costo y margen con permiso, márgenes por categoría, escalas, topes por rol y evaluación."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.models.inventory import InventoryItemModel
from app.infrastructure.models.inventory_valuation import (
    InventoryCostAverageModel,
    InventoryValuationSettingModel,
)
from app.infrastructure.models.rbac import Permission, Role, RolePermission, UserRole
from httpx import AsyncClient
from sqlalchemy import select

from tests.e2e.conftest import get_test_company_id, seed_user
from tests.e2e.test_price_lists import _ensure_inventory_item

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"
BASE = "/api/v1/price-lists"


async def _login(
    client: AsyncClient, *, superuser: bool, permissions: tuple[str, ...] = ()
) -> tuple[str, dict[str, str]]:
    username = f"discounts-{uuid.uuid4().hex[:8]}"
    user_id = await seed_user(
        username=username,
        email=f"{username}@example.com",
        password=PASSWORD,
        is_superuser=superuser,
    )
    company_id = await get_test_company_id()
    if permissions:
        async with async_session_factory() as session:
            rows = (
                await session.scalars(select(Permission).where(Permission.code.in_(permissions)))
            ).all()
            role = Role(company_id=company_id, name=f"V2c {uuid.uuid4().hex[:8]}")
            session.add(role)
            await session.flush()
            session.add_all(
                [
                    *[RolePermission(role_id=role.id, permission_id=p.id) for p in rows],
                    UserRole(user_id=uuid.UUID(user_id), company_id=company_id, role_id=role.id),
                ]
            )
            await session.commit()
    login = await client.post("/api/v1/auth/login", json={"login": username, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return user_id, {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Company-ID": str(company_id),
    }


async def _unit_with_cost(
    client: AsyncClient, headers: dict[str, str], user_id: str, cost: str
) -> dict:
    company_id = uuid.UUID(headers["X-Company-ID"])
    await _ensure_inventory_item(company_id)
    units = (await client.get(f"{BASE}/sellable-units", headers=headers)).json()
    unit = next(u for u in units if u["is_base"])
    async with async_session_factory() as session:
        if await session.get(InventoryValuationSettingModel, company_id) is None:
            session.add(
                InventoryValuationSettingModel(
                    company_id=company_id,
                    currency="USD",
                    opened_at=datetime.now(UTC),
                    opened_by=uuid.UUID(user_id),
                    opening_reference="Apertura de prueba",
                    opening_fingerprint="0" * 64,
                    physical_snapshot=[],
                )
            )
            await session.flush()
        item_id = await session.scalar(
            select(InventoryItemModel.id).where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.product_id == unit["product_id"],
            )
        )
        assert item_id is not None
        row = await session.get(InventoryCostAverageModel, (company_id, item_id))
        if row is None:
            row = InventoryCostAverageModel(company_id=company_id, inventory_item_id=item_id)
            session.add(row)
        row.quantity_base = Decimal("10")
        row.average_unit_cost = Decimal(cost)
        row.inventory_value = Decimal(cost) * 10
        row.updated_at = datetime.now(UTC)
        await session.commit()
    return unit


async def _new_list(client: AsyncClient, headers: dict[str, str], **extra: object) -> dict:
    response = await client.post(
        BASE,
        json={
            "code": f"L{uuid.uuid4().hex[:6].upper()}",
            "name": "Lista V2c",
            "prices_include_vat": True,
            **extra,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _key(unit: dict) -> dict[str, object]:
    return {
        "product_id": unit["product_id"],
        "variant_id": unit["variant_id"],
        "unit_id": unit["unit_id"],
    }


async def test_cost_margin_and_suggested_price_need_permission(e2e_client: AsyncClient) -> None:
    user_id, headers = await _login(e2e_client, superuser=True)
    unit = await _unit_with_cost(e2e_client, headers, user_id, "7.00")
    price_list = await _new_list(e2e_client, headers, target_margin_percent="30")
    assert price_list["target_margin_percent"] == "30.00"
    saved = await e2e_client.post(
        f"{BASE}/{price_list['id']}/prices", json={**_key(unit), "price": "9.04"}, headers=headers
    )
    assert saved.status_code == 201, saved.text

    rows = (
        await e2e_client.get(
            f"{BASE}/{price_list['id']}/prices", params={"search": unit["sku"]}, headers=headers
        )
    ).json()
    row = next(r for r in rows if r["unit"]["unit_id"] == unit["unit_id"] and r["unit"]["is_base"])
    assert row["cost"] == "7.00000000"
    assert row["margin_percent"] == "12.50"  # 9.04 / 1.13 = 8.00 -> (8 - 7) / 8
    assert row["suggested_price"] == "11.30"
    assert row["below_target"] is True
    assert row["below_cost"] is False

    product_category = None
    async with async_session_factory() as session:
        product_category = await session.scalar(
            select(ProductModel.id_category).where(ProductModel.id_product == unit["product_id"])
        )
    margins = await e2e_client.put(
        f"{BASE}/{price_list['id']}/category-margins",
        json={"margins": [{"category_id": product_category, "target_margin_percent": "12.5"}]},
        headers=headers,
    )
    assert margins.status_code == 200, margins.text
    again = (
        await e2e_client.get(
            f"{BASE}/{price_list['id']}/prices", params={"search": unit["sku"]}, headers=headers
        )
    ).json()
    row = next(r for r in again if r["unit"]["unit_id"] == unit["unit_id"] and r["unit"]["is_base"])
    assert row["target_margin_percent"] == "12.50"
    assert row["below_target"] is False

    _, reader = await _login(e2e_client, superuser=False, permissions=("price_lists:read",))
    hidden = (
        await e2e_client.get(
            f"{BASE}/{price_list['id']}/prices", params={"search": unit["sku"]}, headers=reader
        )
    ).json()
    assert all(r["cost"] is None and r["margin_percent"] is None for r in hidden)


async def test_volume_scales_customer_discount_and_role_limits(e2e_client: AsyncClient) -> None:
    user_id, headers = await _login(e2e_client, superuser=True)
    unit = await _unit_with_cost(e2e_client, headers, user_id, "7.00")
    price_list = await _new_list(e2e_client, headers, is_default=True, prices_include_vat=False)
    await e2e_client.post(
        f"{BASE}/{price_list['id']}/prices", json={**_key(unit), "price": "10.00"}, headers=headers
    )
    for quantity, percent in (("10", "3"), ("50", "6")):
        scale = await e2e_client.post(
            f"{BASE}/{price_list['id']}/volume-discounts",
            json={**_key(unit), "min_quantity": quantity, "discount_percent": percent},
            headers=headers,
        )
        assert scale.status_code == 201, scale.text
        assert scale.json()["status"] == "current"
    listed = (
        await e2e_client.get(f"{BASE}/{price_list['id']}/volume-discounts", headers=headers)
    ).json()
    assert len(listed) == 2

    customer = await e2e_client.post(
        "/api/v1/customers", json={"name": "Ana López", "discount_percent": "5"}, headers=headers
    )
    assert customer.status_code == 201, customer.text
    assert customer.json()["discount_percent"] == "5.00"

    seller_id, seller = await _login(
        e2e_client, superuser=False, permissions=("sales:read", "price_lists:read")
    )
    async with async_session_factory() as session:
        role_id = await session.scalar(
            select(UserRole.role_id).where(UserRole.user_id == uuid.UUID(seller_id))
        )
    policy = await e2e_client.put(
        f"/api/v1/sales/discount-policies/{role_id}",
        json={"max_line_discount_percent": "5", "max_global_discount_percent": "2"},
        headers=headers,
    )
    assert policy.status_code == 200, policy.text
    assert policy.json()["configured"] is True
    mine = await e2e_client.get("/api/v1/sales/my-discount-policy", headers=seller)
    assert mine.json()["max_line_discount_percent"] == "5.00"

    url = "/api/v1/sales/discount-evaluation"
    body = {
        "customer_id": customer.json()["id"],
        "lines": [{**_key(unit), "quantity": "60"}, {**_key(unit), "quantity": "2"}],
    }
    result = await e2e_client.post(url, json=body, headers=seller)
    assert result.status_code == 200, result.text
    big, small = result.json()["lines"]
    assert big["suggested_discount_percent"] == "6.00"
    assert big["suggested_discount_source"] == "volume"
    assert big["reasons"] == ["discount_above_limit"]
    assert big["cost"] is None  # sin sales_costs:read
    assert small["suggested_discount_source"] == "customer"
    assert small["discount_percent"] == "5.00"
    assert small["requires_authorization"] is False

    below_cost = await e2e_client.post(
        url,
        json={
            "lines": [{**_key(unit), "quantity": "1", "discount_percent": "40"}],
            "global_discount_percent": "3",
        },
        headers=seller,
    )
    data = below_cost.json()
    assert set(data["lines"][0]["reasons"]) == {"discount_above_limit", "below_cost"}
    # Bajo costo ya no se autoriza: se marca como bloqueo.
    assert data["lines"][0]["below_cost"] is True
    assert data["global_reasons"] == ["global_discount_above_limit"]
    assert data["requires_authorization"] is True

    admin_view = await e2e_client.post(
        url, json={"lines": [{**_key(unit), "quantity": "1"}]}, headers=headers
    )
    line = admin_view.json()["lines"][0]
    assert line["cost"] == "7.00000000"
    assert line["margin_percent"] == "30.00"
    assert "can_sell_below_cost" not in admin_view.json()["policy"]

    scale_id = listed[0]["id"]
    ended = await e2e_client.delete(f"{BASE}/volume-discounts/{scale_id}", headers=headers)
    assert ended.status_code == 204, ended.text


async def test_validation_and_permissions(e2e_client: AsyncClient) -> None:
    user_id, headers = await _login(e2e_client, superuser=True)
    unit = await _unit_with_cost(e2e_client, headers, user_id, "1.00")
    price_list = await _new_list(e2e_client, headers)
    wrong = await e2e_client.post(
        f"{BASE}/{price_list['id']}/volume-discounts",
        json={**_key(unit), "unit_id": 999_999, "min_quantity": "5", "discount_percent": "2"},
        headers=headers,
    )
    assert wrong.json()["code"] == "price_list_unit_invalid"
    duplicate = await e2e_client.post(
        f"{BASE}/{price_list['id']}/volume-discounts",
        json={**_key(unit), "min_quantity": "5", "discount_percent": "2"},
        headers=headers,
    )
    assert duplicate.status_code == 201
    future = await e2e_client.post(
        f"{BASE}/{price_list['id']}/volume-discounts",
        json={
            **_key(unit),
            "min_quantity": "5",
            "discount_percent": "4",
            "valid_from": "2099-01-01",
        },
        headers=headers,
    )
    assert future.status_code == 201
    jumped = await e2e_client.post(
        f"{BASE}/{price_list['id']}/volume-discounts",
        json={
            **_key(unit),
            "min_quantity": "5",
            "discount_percent": "3",
            "valid_from": "2098-01-01",
        },
        headers=headers,
    )
    assert jumped.status_code == 409
    assert jumped.json()["code"] == "sales_volume_future_exists"
    unknown_role = await e2e_client.put(
        f"/api/v1/sales/discount-policies/{uuid.uuid4()}",
        json={"max_line_discount_percent": "5", "max_global_discount_percent": "0"},
        headers=headers,
    )
    assert unknown_role.status_code == 404
    bad_margin = await e2e_client.put(
        f"{BASE}/{price_list['id']}/category-margins",
        json={"margins": [{"category_id": 999_999, "target_margin_percent": "10"}]},
        headers=headers,
    )
    assert bad_margin.status_code == 404
    customer = await e2e_client.post(
        "/api/v1/customers", json={"name": "Ana López", "discount_percent": "120"}, headers=headers
    )
    assert customer.status_code == 422

    _, nobody = await _login(e2e_client, superuser=False)
    assert (
        await e2e_client.get("/api/v1/sales/discount-policies", headers=nobody)
    ).status_code == 403
    assert (
        await e2e_client.post(
            "/api/v1/sales/discount-evaluation",
            json={"lines": [{**_key(unit), "quantity": "1"}]},
            headers=nobody,
        )
    ).status_code == 403
