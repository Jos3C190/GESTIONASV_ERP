"""V8b1: cambio de producto como devolución aceptada + pedido nuevo vinculado."""

from __future__ import annotations

import uuid

import pytest
from app.core.config import settings
from httpx import AsyncClient

from tests.e2e.test_customers import _geography, _taxpayer
from tests.e2e.test_sales_invoices import ORDERS
from tests.e2e.test_sales_notes import _ccf
from tests.e2e.test_sales_orders import _order_act
from tests.e2e.test_sales_return_fiscal import SALES, _accept, _received_return

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]


def _exchange_body(order: dict, return_id: str, **extra: object) -> dict:
    [line] = order["lines"]
    return {
        "branch_id": order["branch_id"],
        "customer_id": order["customer_id"],
        "document_type": order["document_type"],
        "promised_date": order["promised_date"],
        "delivery_mode": "pickup",
        "lines": [
            {
                "product_id": line["product_id"],
                "variant_id": line["variant_id"],
                "unit_id": line["unit_id"],
                "quantity": "1",
            }
        ],
        "exchange_return_id": return_id,
        **extra,
    }


async def _post(client: AsyncClient, admin: dict[str, str], body: dict):
    return await client.post(
        ORDERS, json=body, headers={**admin, "Idempotency-Key": f"v8b1-{uuid.uuid4()}"}
    )


async def test_exchange_order_links_an_accepted_return(e2e_client: AsyncClient) -> None:
    admin, order, _document = await _ccf(e2e_client, stock="4")
    return_id, line_id, per_unit = await _received_return(e2e_client, admin, order["id"], 2)
    pending_id, _pending_line, _ = await _received_return(e2e_client, admin, order["id"], 1)

    # Sin mercadería aceptada no hay cambio.
    refused = await _post(e2e_client, admin, _exchange_body(order, return_id))
    assert refused.status_code == 422
    assert refused.json()["code"] == "sales_exchange_return_not_accepted"

    accepted = await e2e_client.post(
        f"{SALES}/returns/{return_id}/resolve",
        headers={**admin, "Idempotency-Key": f"v8b1-resolve-{uuid.uuid4()}"},
        json=_accept(line_id, per_unit * 2),
    )
    assert accepted.status_code == 200, accepted.text

    created = await _post(e2e_client, admin, _exchange_body(order, return_id))
    assert created.status_code == 201, created.text
    exchange = created.json()
    assert exchange["exchange_return_id"] == return_id
    assert exchange["exchange_return_code"].startswith("DEV-")

    detail = (await e2e_client.get(f"{SALES}/returns/{return_id}", headers=admin)).json()
    assert detail["exchange_orders"] == [
        {"id": exchange["id"], "code": exchange["code"], "status": "draft"}
    ]

    # Una devolución se cambia una sola vez mientras el pedido de cambio esté vigente.
    taken = await _post(e2e_client, admin, _exchange_body(order, return_id))
    assert taken.status_code == 422
    assert taken.json()["code"] == "sales_exchange_return_taken"

    # Editar el propio pedido de cambio conserva el vínculo.
    edited = await e2e_client.put(
        f"{ORDERS}/{exchange['id']}",
        json={
            **_exchange_body(order, return_id),
            "notes": "Cambio por otra presentación",
            "expected_version": exchange["version"],
        },
        headers=admin,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["exchange_return_id"] == return_id

    # Otro cliente no puede usar la devolución.
    stranger = await e2e_client.post(
        "/api/v1/customers",
        json={
            **_taxpayer(await _geography()),
            "name": f"Otro cliente {uuid.uuid4().hex[:6]}, S.A. de C.V.",
            "document_number": f"0614{uuid.uuid4().int % 10**10:010d}",
            "nrc": f"{uuid.uuid4().int % 10**6:06d}-{uuid.uuid4().int % 10}",
        },
        headers=admin,
    )
    assert stranger.status_code == 201, stranger.text
    mismatch = await _post(
        e2e_client,
        admin,
        _exchange_body(order, return_id, customer_id=stranger.json()["id"]),
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["code"] == "sales_exchange_customer_mismatch"

    missing = await _post(e2e_client, admin, _exchange_body(order, str(uuid.uuid4())))
    assert missing.status_code == 404
    assert missing.json()["code"] == "sales_exchange_return_not_found"

    # Cancelado el pedido de cambio, la devolución queda libre para otro.
    cancelled = await _order_act(
        e2e_client, admin, edited.json(), "cancel", reason="El cliente prefirió el reintegro"
    )
    assert cancelled.status_code == 200, cancelled.text
    again = await _post(e2e_client, admin, _exchange_body(order, return_id))
    assert again.status_code == 201, again.text
    assert pending_id != return_id
