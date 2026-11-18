"""V4b: anular, corregir y volver a facturar, contra el servicio DTE real en modo simulado."""

from __future__ import annotations

import uuid

import pytest
from app.core.config import settings
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.dte_worker import (
    dte_client,
    object_storage,
    process_fiscal_document,
    process_fiscal_invalidation,
)
from app.infrastructure.models.sales_fiscal import SalesFiscalDocumentModel
from httpx import AsyncClient

from tests.e2e.test_sales_invoices import (
    DOCUMENTS,
    ORDER_SELLER,
    ORDERS,
    _confirmed_order,
    _deliver,
    _mailbox,
    _set_customer_email,
    _with_policy,
)

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

RESPONSIBLE = {
    "name": "Encargada de facturación",
    "document_type": "13",
    "document_number": "01234567-8",
}
REQUESTER = {"name": "María Fernanda Rivas", "document_type": "13", "document_number": "04567890-1"}


async def _issued(client: AsyncClient) -> tuple[dict[str, str], dict, uuid.UUID, dict]:
    admin, order, point = await _confirmed_order(client)
    saved = await client.put(
        "/api/v1/sales/contingencies/responsible", json=RESPONSIBLE, headers=admin
    )
    assert saved.status_code == 200, saved.text
    document = (
        await client.post(
            f"{ORDERS}/{order['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
        )
    ).json()
    await _process_document(document["id"])
    issued = (await client.get(f"{DOCUMENTS}/{document['id']}", headers=admin)).json()
    assert issued["status"] == "simulated", issued
    return admin, order, point, issued


async def _process_document(document_id: str) -> None:
    client = dte_client()
    assert client is not None
    await process_fiscal_document(uuid.UUID(document_id), client=client, storage=object_storage())


async def _process_invalidation(invalidation_id: str) -> None:
    client = dte_client()
    assert client is not None
    await process_fiscal_invalidation(uuid.UUID(invalidation_id), client=client)


async def _set_status(document_id: str, status: str) -> None:
    async with async_session_factory() as session:
        model = await session.get(SalesFiscalDocumentModel, uuid.UUID(document_id))
        assert model is not None
        model.status = status
        if status in ("failed", "rejected"):
            model.error_message = "Prueba"
        await session.commit()


async def test_cancel_an_invoiced_order_invalidates_the_document(e2e_client: AsyncClient) -> None:
    admin, order, _point, issued = await _issued(e2e_client)
    url = f"{DOCUMENTS}/{issued['id']}"

    overview = (await e2e_client.get(f"{url}/invalidation", headers=admin)).json()
    assert overview["deadline"] is not None
    assert overview["expired"] is False
    assert overview["history"] == []

    short = await e2e_client.post(
        f"{url}/invalidate", json={"reason": "No", "requester": REQUESTER}, headers=admin
    )
    assert short.status_code == 422
    assert short.json()["code"] == "sales_invoice_invalidation_reason_required"
    bad = await e2e_client.post(
        f"{url}/invalidate",
        json={"reason": "El cliente desistió", "requester": {**REQUESTER, "document_type": "99"}},
        headers=admin,
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "sales_invoice_requester_invalid"

    requested = await e2e_client.post(
        f"{url}/invalidate",
        json={
            "reason": "El cliente desistió de la compra",
            "requester": REQUESTER,
            "cancel_order": True,
        },
        headers=admin,
    )
    assert requested.status_code == 202, requested.text
    invalidation = requested.json()
    assert invalidation["status"] == "pending"
    assert invalidation["responsible"] == RESPONSIBLE
    twice = await e2e_client.post(
        f"{url}/invalidate",
        json={"reason": "Otra vez el mismo motivo", "requester": REQUESTER},
        headers=admin,
    )
    assert twice.status_code == 422
    assert twice.json()["code"] == "sales_invoice_invalidation_in_progress"

    await _process_invalidation(invalidation["id"])
    document = (await e2e_client.get(url, headers=admin)).json()
    assert document["status"] == "invalidated", document
    history = (await e2e_client.get(f"{url}/invalidation", headers=admin)).json()["history"]
    assert history[0]["status"] == "accepted"
    assert history[0]["event_generation_code"]
    assert history[0]["event_seal"]
    cancelled = (await e2e_client.get(f"{ORDERS}/{order['id']}", headers=admin)).json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancellation_reason"] == "El cliente desistió de la compra"

    again = await e2e_client.post(
        f"{url}/invalidate",
        json={"reason": "Ya está invalidado", "requester": REQUESTER},
        headers=admin,
    )
    assert again.status_code == 422
    assert again.json()["code"] == "sales_invoice_not_invalidatable"


async def test_correct_issues_the_replacement_and_then_invalidates_the_original(
    e2e_client: AsyncClient,
) -> None:
    admin, order, _point, issued = await _issued(e2e_client)
    url = f"{DOCUMENTS}/{issued['id']}"
    corrected = await e2e_client.post(
        f"{url}/correct", json={"requester": REQUESTER}, headers=admin
    )
    assert corrected.status_code == 202, corrected.text
    replacement = corrected.json()["replacement"]
    invalidation = corrected.json()["invalidation"]
    assert replacement["replaces_document_id"] == issued["id"]
    assert replacement["status"] == "pending"
    assert invalidation["kind"] == 1
    original = (await e2e_client.get(url, headers=admin)).json()
    assert original["superseded_by_id"] == replacement["id"]
    options = (
        await e2e_client.get(f"{ORDERS}/{order['id']}/invoice-options", headers=admin)
    ).json()
    assert options["document"]["id"] == replacement["id"], "el reemplazo es el documento vigente"

    # Mientras el reemplazo no está sellado la invalidación espera, sin gastar intentos.
    await _process_invalidation(invalidation["id"])
    waiting = (await e2e_client.get(f"{url}/invalidation", headers=admin)).json()["history"][0]
    assert waiting["status"] == "pending"
    assert waiting["attempts"] == 0

    await _process_document(replacement["id"])
    await _process_invalidation(invalidation["id"])
    original = (await e2e_client.get(url, headers=admin)).json()
    assert original["status"] == "invalidated"
    sealed = (await e2e_client.get(f"{DOCUMENTS}/{replacement['id']}", headers=admin)).json()
    assert sealed["status"] == "simulated"
    order_now = (await e2e_client.get(f"{ORDERS}/{order['id']}", headers=admin)).json()
    assert order_now["status"] == "confirmed", "corregir no cancela el pedido"


async def test_a_lost_replacement_releases_the_original(e2e_client: AsyncClient) -> None:
    admin, _order, _point, issued = await _issued(e2e_client)
    url = f"{DOCUMENTS}/{issued['id']}"
    corrected = (
        await e2e_client.post(f"{url}/correct", json={"requester": REQUESTER}, headers=admin)
    ).json()
    await _set_status(corrected["replacement"]["id"], "failed")
    await _process_invalidation(corrected["invalidation"]["id"])
    history = (await e2e_client.get(f"{url}/invalidation", headers=admin)).json()["history"]
    assert history[0]["status"] == "failed"
    assert history[0]["error_code"] == "sales_invoice_replacement_not_issued"
    original = (await e2e_client.get(url, headers=admin)).json()
    assert original["status"] == "simulated"
    assert original["superseded_by_id"] is None


async def test_a_rejected_document_does_not_block_invoicing_again(e2e_client: AsyncClient) -> None:
    admin, order, point = await _confirmed_order(e2e_client)
    first = (
        await e2e_client.post(
            f"{ORDERS}/{order['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
        )
    ).json()
    await _set_status(first["id"], "rejected")
    options = (
        await e2e_client.get(f"{ORDERS}/{order['id']}/invoice-options", headers=admin)
    ).json()
    assert options["document"] is None
    assert options["previous_document"]["id"] == first["id"], "se muestra el rechazado"
    again = await e2e_client.post(
        f"{ORDERS}/{order['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
    )
    assert again.status_code == 202, again.text
    assert again.json()["id"] != first["id"]


async def test_invalidating_needs_its_permission(e2e_client: AsyncClient) -> None:
    admin, _order, _point, issued = await _issued(e2e_client)
    seller = await _with_policy(e2e_client, admin, ORDER_SELLER, "5", "2", False)
    denied = await e2e_client.post(
        f"{DOCUMENTS}/{issued['id']}/invalidate",
        json={"reason": "Sin permiso para esto", "requester": REQUESTER},
        headers=seller,
    )
    assert denied.status_code == 403


@pytest.mark.skipif(not settings.SMTP_HOST, reason="Sin servidor de correo configurado")
async def test_the_customer_is_told_about_the_invalidation(e2e_client: AsyncClient) -> None:
    admin, order, _point, issued = await _issued(e2e_client)
    customer = f"anulacion-{uuid.uuid4().hex[:8]}@example.com"
    await _set_customer_email(order, customer)
    invalidation = (
        await e2e_client.post(
            f"{DOCUMENTS}/{issued['id']}/invalidate",
            json={"reason": "El cliente desistió de la compra", "requester": REQUESTER},
            headers=admin,
        )
    ).json()
    queued: list[uuid.UUID] = []

    async def capture(email_id: uuid.UUID) -> None:
        queued.append(email_id)

    client = dte_client()
    assert client is not None
    await process_fiscal_invalidation(
        uuid.UUID(invalidation["id"]), client=client, on_email=capture
    )
    assert len(queued) == 1
    await _deliver(str(queued[0]))

    [message] = await _mailbox(customer)
    assert message["Subject"].startswith("[SIMULADO")
    assert "Anulación de factura" in message["Subject"]
    assert message["Attachments"] == 1
    history = (await e2e_client.get(f"{DOCUMENTS}/{issued['id']}/emails", headers=admin)).json()[
        "items"
    ]
    notice = next(item for item in history if item["invalidation_id"])
    assert notice["status"] == "sent"
