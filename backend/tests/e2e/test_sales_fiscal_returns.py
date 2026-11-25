"""V4d2: evento de retorno sobre una factura, contra el servicio DTE real en modo simulado."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.core.config import settings
from app.infrastructure.dte_returns_worker import process_fiscal_return, process_return_annulment
from app.infrastructure.dte_worker import dte_client, object_storage
from httpx import AsyncClient

from tests.e2e.test_sales_invalidations import REQUESTER, _issued
from tests.e2e.test_sales_invoices import DOCUMENTS

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

RETURNS = "/api/v1/sales/fiscal-returns"


async def _issue(return_id: str) -> None:
    client = dte_client()
    assert client is not None
    await process_fiscal_return(uuid.UUID(return_id), client=client, storage=object_storage())


async def _annul(return_id: str) -> None:
    client = dte_client()
    assert client is not None
    await process_return_annulment(uuid.UUID(return_id), client=client)


async def test_return_on_an_invoice_and_its_annulment(e2e_client: AsyncClient) -> None:
    admin, _order, _point, invoice = await _issued(e2e_client)
    assert invoice["document_type"] == "01"
    url = f"{DOCUMENTS}/{invoice['id']}/returns"

    overview = (await e2e_client.get(url, headers=admin)).json()
    assert overview["blocker"] is None
    assert overview["deadline"] is not None
    [line] = overview["lines"]
    assert Decimal(str(line["remaining_quantity"])) == Decimal("2.000000")

    too_much = await e2e_client.post(
        url,
        json={
            "reason": "El cliente devolvió",
            "lines": [{"invoice_line_number": 1, "quantity": "3"}],
        },
        headers=admin,
    )
    assert too_much.status_code == 422
    assert too_much.json()["code"] == "sales_return_quantity_exceeded"

    registered = await e2e_client.post(
        url,
        json={
            "reason": "El cliente devolvió una unidad",
            "lines": [{"invoice_line_number": 1, "quantity": "1"}],
        },
        headers=admin,
    )
    assert registered.status_code == 202, registered.text
    item = registered.json()
    assert item["status"] == "pending"
    await _issue(item["id"])

    overview = (await e2e_client.get(url, headers=admin)).json()
    [issued] = overview["returns"]
    assert issued["status"] == "simulated", issued
    assert issued["error_code"] is None, issued
    assert issued["seal"].startswith("SIMULATED-EVT-")
    assert Decimal(str(overview["lines"][0]["returned"])) == Decimal("1.000000")
    assert Decimal(str(overview["lines"][0]["remaining_quantity"])) == Decimal("1.000000")
    event = (await e2e_client.get(f"{RETURNS}/{item['id']}/json", headers=admin)).json()
    assert event["identificacion"]["tipoEvento"] == "18"
    pdf = await e2e_client.get(f"{RETURNS}/{item['id']}/pdf", headers=admin)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"

    # Con un retorno vigente la factura no se anula.
    blocked = await e2e_client.post(
        f"{DOCUMENTS}/{invoice['id']}/invalidate",
        json={"reason": "El cliente desistió", "requester": REQUESTER},
        headers=admin,
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "sales_invoice_has_returns"

    annulled = await e2e_client.post(
        f"{RETURNS}/{item['id']}/annul", json={"requester": REQUESTER}, headers=admin
    )
    assert annulled.status_code == 202, annulled.text
    assert annulled.json()["annul_status"] == "pending"
    again = await e2e_client.post(
        f"{RETURNS}/{item['id']}/annul", json={"requester": REQUESTER}, headers=admin
    )
    assert again.status_code == 422
    assert again.json()["code"] == "sales_return_not_annullable"
    await _annul(item["id"])
    overview = (await e2e_client.get(url, headers=admin)).json()
    [gone] = overview["returns"]
    assert gone["status"] == "invalidated", gone
    assert gone["annul_status"] == "accepted"
    assert Decimal(str(overview["lines"][0]["remaining_quantity"])) == Decimal("2.000000")

    allowed = await e2e_client.post(
        f"{DOCUMENTS}/{invoice['id']}/invalidate",
        json={"reason": "El cliente desistió", "requester": REQUESTER},
        headers=admin,
    )
    assert allowed.status_code == 202, allowed.text
