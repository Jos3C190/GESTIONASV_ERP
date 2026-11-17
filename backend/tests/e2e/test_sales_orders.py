"""V2e: pedido directo y desde cotización, reserva comercial, autorización y cancelación."""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from app.application.price_lists import today_in_el_salvador
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.inventory import InventoryHandlingUnitModel, InventoryItemModel
from app.infrastructure.models.organization import Location, Warehouse
from httpx import AsyncClient
from sqlalchemy import func, select, text

from tests.e2e.sales_quote_flow import order_from_quote
from tests.e2e.test_sales_deliveries import _seed_receipt
from tests.e2e.test_sales_quotations import AUTHORIZER, SELLER, _act, _post, _setup, _with_policy

pytestmark = pytest.mark.e2e

ORDERS = "/api/v1/sales"
ORDER_SELLER = (
    *SELLER,
    "sales_quotations:convert",
    "sales:read",
    "sales:manage",
    "sales:confirm",
    "sales:cancel",
)


async def _stock(admin: dict[str, str], body: dict, quantity: str) -> uuid.UUID:
    """Deja ``quantity`` unidades disponibles del artículo en una sucursal con bodega.

    Cambia ``body["branch_id"]`` a esa sucursal.
    """

    company_id = uuid.UUID(admin["X-Company-ID"])
    product_id = body["lines"][0]["product_id"]
    async with async_session_factory() as session:
        item_id = await session.scalar(
            select(InventoryItemModel.id).where(
                InventoryItemModel.company_id == company_id,
                InventoryItemModel.product_id == product_id,
            )
        )
        found = (
            await session.execute(
                select(Location.id, Warehouse.branch_id)
                .join(Warehouse, Warehouse.id == Location.warehouse_id)
                .where(
                    Warehouse.company_id == company_id,
                    Warehouse.is_active.is_(True),
                    Warehouse.is_transit.is_(False),
                    Warehouse.operational_status == "active",
                    Warehouse.deleted_at.is_(None),
                    Location.is_active.is_(True),
                    Location.lifecycle_status == "active",
                    Location.storage_eligible.is_(True),
                    Location.deleted_at.is_(None),
                    Location.location_type != "virtual",
                )
                .order_by(Location.id)
                .limit(1)
            )
        ).first()
        actor_id = await session.scalar(
            # Las acciones del trabajador DTE no tienen usuario: se toma una con usuario.
            select(AuditLog.user_id)
            .where(AuditLog.company_id == company_id, AuditLog.user_id.is_not(None))
            .limit(1)
        )
    assert item_id is not None
    assert found is not None, "La semilla debe tener una bodega con ubicación de almacenamiento."
    location_id, branch_id = found
    body["branch_id"] = str(branch_id)
    await _seed_receipt(
        company_id,
        actor_id,
        {
            "idempotency_key": f"v2e-receipt-{uuid.uuid4()}",
            "movement_type": "receipt",
            "source_reference": "V2e: existencias de prueba",
            "lines": [
                {
                    "inventory_item_id": str(item_id),
                    "to_location_id": str(location_id),
                    "to_stock_status": "available",
                    "quantity_base": quantity,
                    "handling_unit_code": f"V2E-{uuid.uuid4().hex[:8]}",
                    "actual_measures": {"gross_weight_kg": "1", "volume_m3": "0.1"},
                    "valuation_value": str(Decimal(quantity) * 7),
                    "valuation_currency": "USD",
                }
            ],
        },
    )
    return item_id


async def _physical(company_id: uuid.UUID, item_id: uuid.UUID) -> tuple[int, str]:
    async with async_session_factory() as session:
        row = (
            await session.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(InventoryHandlingUnitModel.quantity_base), 0),
                ).where(
                    InventoryHandlingUnitModel.company_id == company_id,
                    InventoryHandlingUnitModel.inventory_item_id == item_id,
                )
            )
        ).one()
    return int(row[0]), str(row[1])


def _order_body(body: dict, quantity: str, **extra: object) -> dict:
    return {
        **body,
        "lines": [{**body["lines"][0], "quantity": quantity}],
        "promised_date": today_in_el_salvador().isoformat(),
        "delivery_mode": "pickup",
        **extra,
    }


async def _create(client: AsyncClient, headers: dict[str, str], payload: dict) -> dict:
    response = await client.post(
        ORDERS, json=payload, headers={**headers, "Idempotency-Key": str(uuid.uuid4())}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _order_act(
    client: AsyncClient, headers: dict[str, str], order: dict, action: str, **extra: object
):
    return await client.post(
        f"{ORDERS}/{order['id']}/{action}",
        json={"expected_version": order["version"], **extra},
        headers=headers,
    )


async def test_reservation_confirm_cancel_and_concurrency(e2e_client: AsyncClient) -> None:
    admin, body, _unit = await _setup(e2e_client)
    item_id = await _stock(admin, body, "5")
    company_id = uuid.UUID(admin["X-Company-ID"])
    before = await _physical(company_id, item_id)

    first = await _create(e2e_client, admin, _order_body(body, "3"))
    assert first["status"] == "draft"
    assert first["payment_terms"] == "cash"
    assert first["lines"][0]["available_base"] == "5.000000"
    assert first["total"] == "33.90"

    confirmed = await _order_act(e2e_client, admin, first, "confirm")
    assert confirmed.status_code == 200, confirmed.text
    first = confirmed.json()
    assert first["status"] == "confirmed"
    assert first["delivery_progress"] == "pending"

    second = await _create(e2e_client, admin, _order_body(body, "3"))
    assert second["lines"][0]["available_base"] == "2.000000"
    short = await _order_act(e2e_client, admin, second, "confirm")
    assert short.status_code == 422
    assert short.json()["code"] == "sales_order_stock_insufficient"

    cancelled = await _order_act(e2e_client, admin, first, "cancel", reason="Cliente desistió")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    released = await _order_act(e2e_client, admin, second, "confirm")
    assert released.status_code == 200, released.text

    # Dos pedidos de 2 compiten por las 2 unidades libres: solo uno se confirma.
    racers = [await _create(e2e_client, admin, _order_body(body, "2")) for _ in range(2)]
    results = await asyncio.gather(
        *(_order_act(e2e_client, admin, order, "confirm") for order in racers)
    )
    assert sorted(r.status_code for r in results) == [200, 422], [r.text for r in results]

    # Apartar no mueve unidades físicas.
    assert await _physical(company_id, item_id) == before

    past = _order_body(
        body, "1", promised_date=(today_in_el_salvador() - timedelta(days=1)).isoformat()
    )
    stale = await e2e_client.post(
        ORDERS, json=past, headers={**admin, "Idempotency-Key": str(uuid.uuid4())}
    )
    assert stale.status_code == 422
    no_address = await e2e_client.post(
        ORDERS,
        json=_order_body(body, "1", delivery_mode="delivery"),
        headers={**admin, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert no_address.status_code == 422


async def test_order_from_quotation_keeps_accepted_terms(e2e_client: AsyncClient) -> None:
    admin, body, _unit = await _setup(e2e_client)
    await _stock(admin, body, "10")
    seller = await _with_policy(e2e_client, admin, ORDER_SELLER, "5", "2", False)
    high = await _with_policy(e2e_client, admin, AUTHORIZER, "20", "10", True)

    discounted = {
        **body,
        "lines": [{**body["lines"][0], "quantity": "2", "discount_percent": "10"}],
    }
    quote = await _post(e2e_client, seller, discounted)
    quote = (await _act(e2e_client, seller, quote, "issue")).json()
    quote = (await _act(e2e_client, high, quote, "authorize")).json()
    quote = (await _act(e2e_client, seller, quote, "accept")).json()
    assert quote["status"] == "accepted"

    key = str(uuid.uuid4())
    created = await order_from_quote(e2e_client, seller, quote["id"], key)
    assert created.status_code == 201, created.text
    order = created.json()
    assert order["quotation_code"] == quote["code"]
    assert order["total"] == quote["total"]
    assert order["lines"][0]["source_quotation_line_id"] == quote["lines"][0]["id"]
    assert quote["code"] in order["authorization_note"]
    again = await order_from_quote(e2e_client, seller, quote["id"], str(uuid.uuid4()))
    assert again.json()["id"] == order["id"]

    # Las condiciones aceptadas ya estaban autorizadas: el vendedor confirma sin pedir permiso.
    confirmed = await _order_act(e2e_client, seller, order, "confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"

    linked = await e2e_client.get(f"/api/v1/sales/quotations/{quote['id']}", headers=seller)
    assert linked.json()["sale_code"] == order["code"]


async def test_edited_order_is_reevaluated_and_scoped(e2e_client: AsyncClient) -> None:
    admin, body, _unit = await _setup(e2e_client)
    await _stock(admin, body, "10")
    seller = await _with_policy(e2e_client, admin, ORDER_SELLER, "5", "2", False)
    high = await _with_policy(e2e_client, admin, AUTHORIZER, "20", "10", True)

    order = await _create(e2e_client, seller, _order_body(body, "1"))
    edited = await e2e_client.put(
        f"{ORDERS}/{order['id']}",
        json={
            **_order_body(body, "2"),
            "lines": [{**body["lines"][0], "quantity": "2", "discount_percent": "10"}],
            "expected_version": order["version"],
        },
        headers=seller,
    )
    assert edited.status_code == 200, edited.text
    pending = await _order_act(e2e_client, seller, edited.json(), "confirm")
    assert pending.json()["status"] == "pending_authorization"
    denied = await _order_act(e2e_client, seller, pending.json(), "authorize")
    assert denied.status_code == 403
    authorized = await _order_act(e2e_client, high, pending.json(), "authorize", note="Ok")
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["status"] == "confirmed"
    assert authorized.json()["authorized_by_name"]

    listed = await e2e_client.get(ORDERS, params={"status": "confirmed"}, headers=seller)
    assert [o["id"] for o in listed.json()["items"]] == [order["id"]]
    other = await e2e_client.get(
        f"{ORDERS}/{order['id']}", headers={**seller, "X-Company-ID": str(uuid.uuid4())}
    )
    assert other.status_code in {403, 404}
    returns = await e2e_client.get(f"{ORDERS}/returns", headers=admin)
    assert returns.status_code == 200, returns.text

    async with async_session_factory() as session:
        actions = set(
            (
                await session.scalars(
                    select(AuditLog.action).where(AuditLog.resource_id == order["id"])
                )
            ).all()
        )
    assert {
        "SALES_ORDER_CREATED",
        "SALES_ORDER_UPDATED",
        "SALES_ORDER_SUBMITTED_FOR_AUTHORIZATION",
        "SALES_ORDER_AUTHORIZED",
    } <= actions


async def _fiscal_document(company_id: uuid.UUID, order: dict, status: str) -> None:
    """Simula el documento fiscal del pedido; el bloque V3b lo crea al facturar."""

    async with async_session_factory() as session:
        await session.execute(text("SET LOCAL session_replication_role = replica"))
        await session.execute(
            text(
                "INSERT INTO sales_fiscal_documents (company_id, branch_id, sale_id, "
                "establishment_id, point_of_sale_id, document_type, mode, status, "
                "idempotency_key, total, issuer_snapshot, request_payload, created_by_id) "
                "VALUES (:company, :branch, :sale, :establishment, :pos, '01', 'simulated', "
                ":status, :key, 0, '{}', '{}', :user)"
            ),
            {
                "company": company_id,
                "branch": order["branch_id"],
                "sale": order["id"],
                "establishment": uuid.uuid4(),
                "pos": uuid.uuid4(),
                "status": status,
                "key": uuid.uuid4().hex,
                "user": uuid.uuid4(),
            },
        )
        await session.commit()


async def test_invoiced_order_cannot_be_cancelled(e2e_client: AsyncClient) -> None:
    admin, body, _unit = await _setup(e2e_client)
    await _stock(admin, body, "2")
    company_id = uuid.UUID(admin["X-Company-ID"])
    order = await _create(e2e_client, admin, _order_body(body, "1"))
    order = (await _order_act(e2e_client, admin, order, "confirm")).json()

    # Un intento fallido no cuenta como facturado.
    await _fiscal_document(company_id, order, "failed")
    await _fiscal_document(company_id, order, "pending")
    blocked = await _order_act(e2e_client, admin, order, "cancel", reason="Cliente desistió")
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["code"] == "sales_order_invoiced"
