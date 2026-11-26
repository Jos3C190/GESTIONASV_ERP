"""V8a: una nota de crédito sobre un CCF pagado deja saldo a favor; reintegro y su anulación."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from app.core.config import settings
from httpx import AsyncClient

from tests.e2e.test_sales_invalidations import _process_document
from tests.e2e.test_sales_invoices import DOCUMENTS
from tests.e2e.test_sales_notes import _ccf

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

RECEIVABLES = "/api/v1/sales/receivables"
RECEIPTS = "/api/v1/sales/receipts"


def _d(value: object) -> Decimal:
    return Decimal(str(value))


async def test_overpaid_document_releases_credit_and_refund(e2e_client: AsyncClient) -> None:
    admin, order, ccf = await _ccf(e2e_client)
    today = datetime.now(ZoneInfo("America/El_Salvador")).date().isoformat()
    document = (await e2e_client.get(f"{RECEIVABLES}/documents/{ccf['id']}", headers=admin)).json()
    payable = _d(document["payable"])

    paid = await e2e_client.post(
        RECEIPTS,
        json={
            "branch_id": order["branch_id"],
            "customer_id": document["customer_id"],
            "received_on": today,
            "payments": [{"method": "transfer", "amount": str(payable), "reference": "TRF-77"}],
            "applications": [{"document_id": ccf["id"], "amount": str(payable)}],
            "idempotency_key": f"rc-{uuid.uuid4()}",
        },
        headers=admin,
    )
    assert paid.status_code == 201, paid.text
    receipt = paid.json()
    assert _d(receipt["unapplied"]) == 0

    # La nota de crédito de una unidad deja el CCF pagado de más: el excedente vuelve al recibo.
    note = await e2e_client.post(
        f"{DOCUMENTS}/{ccf['id']}/credit-note",
        json={
            "reason": "Devolución de una unidad",
            "lines": [{"ccf_line_number": 1, "kind": "return", "quantity": "1"}],
        },
        headers=admin,
    )
    assert note.status_code == 202, note.text
    await _process_document(note.json()["id"])
    note_total = _d(
        (await e2e_client.get(f"{RECEIVABLES}/documents/{ccf['id']}", headers=admin)).json()[
            "credited"
        ]
    )
    assert note_total > 0
    refreshed = (await e2e_client.get(f"{RECEIPTS}/{receipt['id']}", headers=admin)).json()
    assert _d(refreshed["released"]) == note_total
    assert _d(refreshed["unapplied"]) == note_total

    def refund(amount: str, key: str, **extra: object) -> dict:
        return {
            "refunded_on": today,
            "amount": amount,
            "method": "transfer",
            "reference": "TRF-REINTEGRO",
            "reason": "Devolución de una unidad",
            "idempotency_key": key,
            **extra,
        }

    too_much = await e2e_client.post(
        f"{RECEIPTS}/{receipt['id']}/refunds",
        json=refund(str(note_total + 1), f"ri-{uuid.uuid4()}"),
        headers=admin,
    )
    assert too_much.status_code == 422
    assert too_much.json()["code"] == "sales_refund_exceeds_credit"
    key = f"ri-{uuid.uuid4()}"
    refunded = await e2e_client.post(
        f"{RECEIPTS}/{receipt['id']}/refunds", json=refund(str(note_total), key), headers=admin
    )
    assert refunded.status_code == 201, refunded.text
    body = refunded.json()
    assert _d(body["unapplied"]) == 0
    [item] = body["refunds"]
    assert item["code"].startswith("RI-")
    replay = await e2e_client.post(
        f"{RECEIPTS}/{receipt['id']}/refunds", json=refund(str(note_total), key), headers=admin
    )
    assert replay.status_code == 200

    account = (
        await e2e_client.get(f"{RECEIVABLES}/customers/{document['customer_id']}", headers=admin)
    ).json()
    assert _d(account["credit"]) == 0

    annulled = await e2e_client.post(
        f"/api/v1/sales/refunds/{item['id']}/annul",
        json={"reason": "Transferencia rechazada"},
        headers=admin,
    )
    assert annulled.status_code == 200, annulled.text
    assert _d(annulled.json()["unapplied"]) == note_total
    assert annulled.json()["refunds"][0]["status"] == "annulled"
