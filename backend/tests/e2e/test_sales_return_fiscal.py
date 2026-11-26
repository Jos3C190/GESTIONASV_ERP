"""V8a: aceptar una devolución de un pedido facturado emite su ajuste fiscal automáticamente."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.core.config import settings
from httpx import AsyncClient

from tests.e2e.test_sales_fiscal_returns import _issue
from tests.e2e.test_sales_invalidations import _issued, _process_document
from tests.e2e.test_sales_invoices import DOCUMENTS, _confirmed_order
from tests.e2e.test_sales_notes import _ccf

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

SALES = "/api/v1/sales"


async def _received_return(
    client: AsyncClient, admin: dict[str, str], sale_id: str, units: int
) -> tuple[str, str, Decimal]:
    """Devolución recibida de ``units`` unidades de venta; regresa su id, la línea y la base.

    El pedido se entregó al confirmarlo: la existencia de la prueba es una unidad logística justa.
    """

    sources = await client.get(f"{SALES}/{sale_id}/returnable-allocations", headers=admin)
    assert sources.status_code == 200, sources.text
    [source] = sources.json()
    order = (await client.get(f"{SALES}/{sale_id}", headers=admin)).json()
    [line] = order["lines"]
    per_unit = Decimal(str(line["quantity_base"])) / Decimal(str(line["quantity"]))
    created = await client.post(
        f"{SALES}/{sale_id}/returns",
        headers={**admin, "Idempotency-Key": f"v8a-create-{uuid.uuid4()}"},
        json={
            "lines": [
                {
                    "delivery_allocation_id": source["delivery_allocation_id"],
                    "quantity_base": str(per_unit * units),
                    "reason": "El cliente devolvió mercadería",
                    "declared_condition": "resalable",
                }
            ]
        },
    )
    assert created.status_code == 201, created.text
    return_id = created.json()["id"]
    received = await client.post(
        f"{SALES}/returns/{return_id}/receive",
        headers={**admin, "Idempotency-Key": f"v8a-receive-{uuid.uuid4()}"},
    )
    assert received.status_code == 200, received.text
    return return_id, received.json()["lines"][0]["id"], per_unit


def _accept(line_id: str, quantity: Decimal) -> dict:
    return {
        "lines": [
            {
                "return_line_id": line_id,
                "decision": "accepted",
                "quantity_base": str(quantity),
                "condition": "resalable",
                "reason": "Mercadería en buen estado",
            }
        ]
    }


async def test_accepting_a_return_on_a_ccf_issues_a_credit_note(e2e_client: AsyncClient) -> None:
    admin, order, _ccf_doc = await _ccf(e2e_client, stock="4")
    return_id, line_id, per_unit = await _received_return(e2e_client, admin, order["id"], 2)
    url = f"{SALES}/returns/{return_id}/resolve"

    key = f"v8a-resolve-{uuid.uuid4()}"
    resolved = await e2e_client.post(
        url, headers={**admin, "Idempotency-Key": key}, json=_accept(line_id, per_unit)
    )
    assert resolved.status_code == 200, resolved.text
    [adjustment] = resolved.json()["fiscal_adjustments"]
    assert adjustment["status"] == "issued", adjustment
    assert adjustment["fiscal_return_id"] is None
    assert adjustment["lines"] == [{"line_number": 1, "quantity": "1.000000"}]
    note_id = adjustment["fiscal_note_id"]
    await _process_document(note_id)
    note = (await e2e_client.get(f"{DOCUMENTS}/{note_id}", headers=admin)).json()
    assert note["document_type"] == "05"
    assert note["status"] == "simulated", note

    # El reintento con la misma llave no emite otra nota.
    replay = await e2e_client.post(
        url, headers={**admin, "Idempotency-Key": key}, json=_accept(line_id, per_unit)
    )
    assert replay.status_code == 200, replay.text
    assert len(replay.json()["fiscal_adjustments"]) == 1

    # Una segunda aceptación parcial emite su propia nota.
    second = await e2e_client.post(
        url,
        headers={**admin, "Idempotency-Key": f"v8a-resolve-{uuid.uuid4()}"},
        json=_accept(line_id, per_unit),
    )
    assert second.status_code == 200, second.text
    adjustments = second.json()["fiscal_adjustments"]
    assert [item["status"] for item in adjustments] == ["issued", "issued"]
    assert adjustments[1]["fiscal_note_id"] not in (None, note_id)


async def test_accepting_a_return_on_an_invoice_registers_a_return_event(
    e2e_client: AsyncClient,
) -> None:
    admin, order, _point, invoice = await _issued(e2e_client, stock="2")
    assert invoice["document_type"] == "01"
    return_id, line_id, per_unit = await _received_return(e2e_client, admin, order["id"], 1)
    resolved = await e2e_client.post(
        f"{SALES}/returns/{return_id}/resolve",
        headers={**admin, "Idempotency-Key": f"v8a-resolve-{uuid.uuid4()}"},
        json=_accept(line_id, per_unit),
    )
    assert resolved.status_code == 200, resolved.text
    [adjustment] = resolved.json()["fiscal_adjustments"]
    assert adjustment["status"] == "issued", adjustment
    assert adjustment["fiscal_note_id"] is None
    await _issue(adjustment["fiscal_return_id"])
    overview = (await e2e_client.get(f"{DOCUMENTS}/{invoice['id']}/returns", headers=admin)).json()
    [event] = overview["returns"]
    assert event["id"] == adjustment["fiscal_return_id"]
    assert event["status"] == "simulated", event
    assert Decimal(str(overview["lines"][0]["returned"])) == Decimal("1.000000")


async def test_uninvoiced_order_records_why_no_adjustment(e2e_client: AsyncClient) -> None:
    admin, order, _point = await _confirmed_order(e2e_client, stock="2")
    return_id, line_id, per_unit = await _received_return(e2e_client, admin, order["id"], 1)
    resolved = await e2e_client.post(
        f"{SALES}/returns/{return_id}/resolve",
        headers={**admin, "Idempotency-Key": f"v8a-resolve-{uuid.uuid4()}"},
        json=_accept(line_id, per_unit),
    )
    assert resolved.status_code == 200, resolved.text
    [adjustment] = resolved.json()["fiscal_adjustments"]
    assert adjustment["status"] == "skipped"
    assert adjustment["document_id"] is None
    assert "no está facturado" in adjustment["message"]
    detail = (await e2e_client.get(f"{SALES}/returns/{return_id}", headers=admin)).json()
    assert len(detail["fiscal_adjustments"]) == 1
