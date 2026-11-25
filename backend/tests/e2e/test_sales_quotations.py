"""V2d: cotización con precio de lista, topes, autorización, respuesta del cliente y PDF."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from app.application.price_lists import today_in_el_salvador
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.organization import Branch
from app.infrastructure.models.rbac import UserRole
from httpx import AsyncClient
from sqlalchemy import select

from tests.e2e.sales_quote_flow import order_from_quote
from tests.e2e.test_sales_discounts import BASE, _key, _login, _new_list, _unit_with_cost

pytestmark = pytest.mark.e2e

QUOTES = "/api/v1/sales/quotations"
SELLER = ("sales_quotations:read", "sales_quotations:manage", "sales_quotations:confirm")
AUTHORIZER = ("sales_quotations:read", "sales_discounts:authorize")


async def _branch(company_id: uuid.UUID) -> uuid.UUID:
    async with async_session_factory() as session:
        branch = await session.scalar(
            select(Branch.id)
            .where(
                Branch.company_id == company_id,
                Branch.is_active.is_(True),
                Branch.deleted_at.is_(None),
                Branch.operational_status == "active",
            )
            .order_by(Branch.code)
            .limit(1)
        )
    assert branch is not None
    return branch


async def _with_policy(
    client: AsyncClient,
    admin: dict[str, str],
    permissions: tuple[str, ...],
    line: str,
    global_: str,
) -> dict[str, str]:
    user_id, headers = await _login(client, superuser=False, permissions=permissions)
    async with async_session_factory() as session:
        role_id = await session.scalar(
            select(UserRole.role_id).where(UserRole.user_id == uuid.UUID(user_id))
        )
    saved = await client.put(
        f"/api/v1/sales/discount-policies/{role_id}",
        json={
            "max_line_discount_percent": line,
            "max_global_discount_percent": global_,
        },
        headers=admin,
    )
    assert saved.status_code == 200, saved.text
    return headers


async def _setup(client: AsyncClient) -> tuple[dict[str, str], dict[str, object], dict]:
    admin_id, admin = await _login(client, superuser=True)
    unit = await _unit_with_cost(client, admin, admin_id, "7.00")
    price_list = await _new_list(client, admin, is_default=True, prices_include_vat=False)
    price = await client.post(
        f"{BASE}/{price_list['id']}/prices", json={**_key(unit), "price": "10.00"}, headers=admin
    )
    assert price.status_code == 201, price.text
    for document in ("01", "03"):
        enabled = await client.put(
            f"/api/v1/fiscal/document-types/{document}",
            json={"is_enabled": True, "certification_status": "pending"},
            headers=admin,
        )
        assert enabled.status_code == 200, enabled.text
    customer = await client.post(
        "/api/v1/customers", json={"name": "Clínica San Rafael"}, headers=admin
    )
    assert customer.status_code == 201, customer.text
    company_id = uuid.UUID(admin["X-Company-ID"])
    body: dict[str, object] = {
        "branch_id": str(await _branch(company_id)),
        "customer_id": customer.json()["id"],
        "lines": [{**_key(unit), "quantity": "2"}],
    }
    return admin, body, unit


async def _post(client: AsyncClient, headers: dict[str, str], body: dict) -> dict:
    response = await client.post(
        QUOTES, json=body, headers={**headers, "Idempotency-Key": str(uuid.uuid4())}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _act(
    client: AsyncClient, headers: dict[str, str], quote: dict, action: str, **extra: object
):
    return await client.post(
        f"{QUOTES}/{quote['id']}/{action}",
        json={"expected_version": quote["version"], **extra},
        headers=headers,
    )


async def test_list_price_limits_authorization_and_customer_answer(e2e_client: AsyncClient) -> None:
    admin, body, unit = await _setup(e2e_client)
    seller = await _with_policy(e2e_client, admin, SELLER, "5", "2")
    low = await _with_policy(e2e_client, admin, AUTHORIZER, "8", "5")
    high = await _with_policy(e2e_client, admin, AUTHORIZER, "20", "10")

    preview = await e2e_client.post(f"{QUOTES}/preview", json=body, headers=seller)
    assert preview.status_code == 200, preview.text
    data = preview.json()
    line = data["lines"][0]
    assert data["document_type"] == "01"
    assert data["prices_include_vat"] is False
    assert line["list_price"] == "10.00000000"
    assert line["price_overridden"] is False
    assert line["document_unit_price"] == "11.30000000"
    assert data["total"] == "22.60"
    assert line["cost"] is None
    assert data["costs_visible"] is False

    manual = await e2e_client.post(
        f"{QUOTES}/preview",
        json={**body, "lines": [{**_key(unit), "quantity": "1", "manual_price": "9"}]},
        headers=seller,
    )
    assert manual.status_code == 422
    assert manual.json()["code"] == "sales_quote_price_override_forbidden"

    discounted = {**body, "lines": [{**_key(unit), "quantity": "2", "discount_percent": "10"}]}
    quote = await _post(e2e_client, seller, discounted)
    assert quote["status"] == "draft"
    assert quote["total"] == "20.34"
    assert [r["code"] for r in quote["authorization_reasons"]] == ["discount_above_limit"]

    issued = await _act(e2e_client, seller, quote, "issue")
    assert issued.status_code == 200, issued.text
    quote = issued.json()
    assert quote["status"] == "pending_authorization"

    denied = await _act(e2e_client, seller, quote, "authorize")
    assert denied.status_code == 403
    insufficient = await _act(e2e_client, low, quote, "authorize")
    assert insufficient.status_code == 422
    assert insufficient.json()["code"] == "sales_quote_authority_insufficient"

    seen = await e2e_client.get(f"{QUOTES}/{quote['id']}", headers=high)
    assert seen.json()["costs_visible"] is True
    assert seen.json()["lines"][0]["cost"] == "7.00000000"
    assert seen.json()["lines"][0]["margin_percent"] == "22.22"

    authorized = await _act(e2e_client, high, quote, "authorize", note="Cliente frecuente")
    assert authorized.status_code == 200, authorized.text
    quote = authorized.json()
    assert quote["status"] == "issued"
    assert quote["authorization_note"] == "Cliente frecuente"
    assert quote["authorized_by_name"]

    accepted = await _act(e2e_client, seller, quote, "accept")
    assert accepted.status_code == 200, accepted.text
    quote = accepted.json()
    assert quote["status"] == "accepted"
    rejected_late = await _act(e2e_client, seller, quote, "reject", reason="Tarde")
    assert rejected_late.status_code == 422

    pdf = await e2e_client.get(f"{QUOTES}/{quote['id']}/pdf", headers=seller)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    order = await order_from_quote(e2e_client, admin, quote["id"], str(uuid.uuid4()))
    assert order.status_code == 201, order.text
    assert order.json()["total"] == "20.34"
    assert order.json()["vat"] == quote["vat"]
    cancel_converted = await _act(e2e_client, admin, quote, "cancel", reason="Ya no")
    assert cancel_converted.status_code == 422

    async with async_session_factory() as session:
        actions = set(
            (
                await session.scalars(
                    select(AuditLog.action).where(AuditLog.resource_id == quote["id"])
                )
            ).all()
        )
    assert {
        "SALES_QUOTATION_CREATED",
        "SALES_QUOTATION_SUBMITTED_FOR_AUTHORIZATION",
        "SALES_QUOTATION_AUTHORIZED",
        "SALES_QUOTATION_ACCEPTED",
    } <= actions


async def test_rejection_return_cancel_settings_and_isolation(e2e_client: AsyncClient) -> None:
    admin, body, unit = await _setup(e2e_client)
    seller = await _with_policy(e2e_client, admin, SELLER, "5", "2")
    authorizer = await _with_policy(e2e_client, admin, AUTHORIZER, "20", "10")

    plain = await _post(e2e_client, seller, body)
    issued = await _act(e2e_client, seller, plain, "issue")
    assert issued.json()["status"] == "issued"
    rejected = await _act(e2e_client, seller, issued.json(), "reject", reason="Precio alto")
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "Precio alto"

    discounted = {**body, "global_discount_percent": "4"}
    pending = await _post(e2e_client, seller, discounted)
    pending = (await _act(e2e_client, seller, pending, "issue")).json()
    assert pending["status"] == "pending_authorization"
    returned = await _act(e2e_client, authorizer, pending, "return", reason="Baja el descuento")
    assert returned.status_code == 200, returned.text
    draft = returned.json()
    assert draft["status"] == "draft"
    assert draft["authorization_note"] == "Baja el descuento"
    edited = await e2e_client.put(
        f"{QUOTES}/{draft['id']}",
        json={**body, "expected_version": draft["version"], "global_discount_percent": "2"},
        headers=seller,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["requires_authorization"] is False
    stale = await e2e_client.put(
        f"{QUOTES}/{draft['id']}",
        json={**body, "expected_version": draft["version"]},
        headers=seller,
    )
    assert stale.status_code == 409
    cancelled = await _act(e2e_client, seller, edited.json(), "cancel", reason="Cliente desistió")
    assert cancelled.json()["status"] == "cancelled"

    accepted = await _post(e2e_client, seller, body)
    accepted = (await _act(e2e_client, seller, accepted, "issue")).json()
    accepted = (await _act(e2e_client, seller, accepted, "accept")).json()
    withdrawn = await _act(e2e_client, seller, accepted, "cancel", reason="Cliente desistió")
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["status"] == "cancelled"
    assert withdrawn.json()["customer_response_at"] is not None

    settings = await e2e_client.get("/api/v1/sales/settings/quotations", headers=seller)
    assert settings.json() == {"quotation_validity_days": 15}
    forbidden = await e2e_client.put(
        "/api/v1/sales/settings/quotations", json={"quotation_validity_days": 30}, headers=seller
    )
    assert forbidden.status_code == 403
    saved = await e2e_client.put(
        "/api/v1/sales/settings/quotations", json={"quotation_validity_days": 30}, headers=admin
    )
    assert saved.status_code == 200, saved.text
    longer = await _post(e2e_client, seller, body)
    assert longer["valid_until"] == (today_in_el_salvador() + timedelta(days=30)).isoformat()

    listed = await e2e_client.get(QUOTES, params={"status": "rejected"}, headers=seller)
    assert listed.status_code == 200, listed.text
    assert [q["id"] for q in listed.json()["items"]] == [plain["id"]]

    other = await e2e_client.get(
        f"{QUOTES}/{plain['id']}", headers={**seller, "X-Company-ID": str(uuid.uuid4())}
    )
    assert other.status_code in {403, 404}
