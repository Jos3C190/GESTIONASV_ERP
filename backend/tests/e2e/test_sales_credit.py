"""V5b: cupo, mora y bloqueo al confirmar, autorizar y facturar pedidos a crédito."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.core.config import settings
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.sales import SalesCustomerModel
from httpx import AsyncClient

from tests.e2e.test_sales_invoices import ORDERS, _issuer
from tests.e2e.test_sales_orders import _create, _order_act, _order_body, _stock
from tests.e2e.test_sales_quotations import _setup

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]


async def _terms(
    customer_id: str,
    *,
    days: int,
    limit: str | None,
    blocked: bool = False,
    actor: uuid.UUID | None = None,
) -> None:
    async with async_session_factory() as session:
        customer = await session.get(SalesCustomerModel, uuid.UUID(customer_id))
        assert customer is not None
        customer.credit_days = days
        customer.credit_limit = Decimal(limit) if limit is not None else None
        customer.credit_blocked = blocked
        customer.credit_block_reason = "Prueba de bloqueo" if blocked else None
        customer.credit_blocked_by_id = actor if blocked else None
        if blocked:
            from datetime import UTC, datetime

            customer.credit_blocked_at = datetime.now(UTC)
        else:
            customer.credit_blocked_at = None
        await session.commit()


async def test_credit_limit_block_and_invoice_recheck(e2e_client: AsyncClient) -> None:
    admin, body, _unit = await _setup(e2e_client)
    await _stock(admin, body, "20")
    point = await _issuer(uuid.UUID(admin["X-Company-ID"]), uuid.UUID(str(body["branch_id"])))
    customer_id = str(body["customer_id"])

    # Fuera de cupo: el pedido a crédito pide autorización con nota.
    await _terms(customer_id, days=15, limit="1.00")
    order = await _create(e2e_client, admin, _order_body(body, "1"))
    assert order["payment_terms"] == "credit"
    pending = await _order_act(e2e_client, admin, order, "confirm")
    assert pending.status_code == 200, pending.text
    assert pending.json()["status"] == "pending_authorization"
    codes = [reason["code"] for reason in pending.json()["authorization_reasons"]]
    assert "credit_limit_exceeded" in codes
    no_note = await _order_act(e2e_client, admin, pending.json(), "authorize", note="")
    assert no_note.status_code == 422
    assert no_note.json()["code"] == "sales_credit_note_required"
    authorized = await _order_act(
        e2e_client, admin, pending.json(), "authorize", note="Cliente con garantía"
    )
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["status"] == "confirmed"
    # La autorización de crédito vale para facturarlo.
    invoiced = await e2e_client.post(
        f"{ORDERS}/{order['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
    )
    assert invoiced.status_code == 202, invoiced.text

    # Confirmado dentro de cupo, pero al facturar el cupo ya no alcanza.
    await _terms(customer_id, days=15, limit="100000.00")
    second = await _create(e2e_client, admin, _order_body(body, "1"))
    confirmed = await _order_act(e2e_client, admin, second, "confirm")
    assert confirmed.json()["status"] == "confirmed", confirmed.text
    await _terms(customer_id, days=15, limit="1.00")
    blocked_invoice = await e2e_client.post(
        f"{ORDERS}/{second['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
    )
    assert blocked_invoice.status_code == 422
    assert blocked_invoice.json()["code"] == "sales_credit_authorization_required"
    # Quien controla el crédito lo autoriza sobre el pedido confirmado y ya se factura.
    credit_ok = await _order_act(
        e2e_client, admin, confirmed.json(), "authorize-credit", note="Pagará con cheque"
    )
    assert credit_ok.status_code == 200, credit_ok.text
    assert "credit_limit_exceeded" in [r["code"] for r in credit_ok.json()["authorization_reasons"]]
    again = await _order_act(
        e2e_client, admin, credit_ok.json(), "authorize-credit", note="Pagará con cheque"
    )
    assert again.json()["code"] == "sales_credit_already_authorized"
    allowed = await e2e_client.post(
        f"{ORDERS}/{second['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
    )
    assert allowed.status_code == 202, allowed.text

    # Cliente bloqueado: sin límite igual pide autorización; el contado no se evalúa.
    async with async_session_factory() as session:
        actor = (await session.get(SalesCustomerModel, uuid.UUID(customer_id))).created_by_id  # type: ignore[union-attr]
    await _terms(customer_id, days=15, limit=None, blocked=True, actor=actor)
    third = await _create(e2e_client, admin, _order_body(body, "1"))
    held = await _order_act(e2e_client, admin, third, "confirm")
    assert held.json()["status"] == "pending_authorization"
    assert [r["code"] for r in held.json()["authorization_reasons"]] == ["customer_blocked"]
    await _terms(customer_id, days=0, limit=None, blocked=True, actor=actor)
    cash = await _create(e2e_client, admin, _order_body(body, "1"))
    assert cash["payment_terms"] == "cash"
    cash_confirmed = await _order_act(e2e_client, admin, cash, "confirm")
    assert cash_confirmed.json()["status"] == "confirmed", cash_confirmed.text
