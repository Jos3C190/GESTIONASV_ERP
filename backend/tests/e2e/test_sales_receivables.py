"""V5a: cobro de una factura simulada con recibos, saldo a favor, anulación e idempotencia."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from app.core.config import settings
from httpx import AsyncClient

from tests.e2e.test_sales_invalidations import _issued

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

RECEIVABLES = "/api/v1/sales/receivables"
RECEIPTS = "/api/v1/sales/receipts"


def _d(value: object) -> Decimal:
    return Decimal(str(value))


async def test_collect_an_invoice_with_receipts(e2e_client: AsyncClient) -> None:
    admin, order, _point, invoice = await _issued(e2e_client)
    today = datetime.now(ZoneInfo("America/El_Salvador")).date().isoformat()
    document = (
        await e2e_client.get(f"{RECEIVABLES}/documents/{invoice['id']}", headers=admin)
    ).json()
    payable = _d(document["payable"])
    assert payable > 0
    assert _d(document["balance"]) == payable
    customer_id = document["customer_id"]
    portfolio = (await e2e_client.get(RECEIVABLES, headers=admin)).json()
    assert customer_id in [row["customer"]["id"] for row in portfolio]

    def body(key: str, payments: list[dict], applications: list[dict]) -> dict:
        return {
            "branch_id": invoice["branch_id"],
            "customer_id": customer_id,
            "received_on": today,
            "payments": payments,
            "applications": applications,
            "idempotency_key": key,
        }

    no_reference = await e2e_client.post(
        RECEIPTS,
        json=body(f"rc-{uuid.uuid4()}", [{"method": "card", "amount": "1.00"}], []),
        headers=admin,
    )
    assert no_reference.status_code == 422
    assert no_reference.json()["code"] == "sales_receipt_reference_required"

    first_key = f"rc-{uuid.uuid4()}"
    first = await e2e_client.post(
        RECEIPTS,
        json=body(
            first_key,
            [{"method": "cash", "amount": "1.00"}],
            [{"document_id": invoice["id"], "amount": "1.00"}],
        ),
        headers=admin,
    )
    assert first.status_code == 201, first.text
    receipt = first.json()
    assert receipt["code"].startswith("RC-")
    replay = await e2e_client.post(
        RECEIPTS,
        json=body(
            first_key,
            [{"method": "cash", "amount": "1.00"}],
            [{"document_id": invoice["id"], "amount": "1.00"}],
        ),
        headers=admin,
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == receipt["id"]

    remaining = payable - Decimal("1.00")
    too_much = await e2e_client.post(
        RECEIPTS,
        json=body(
            f"rc-{uuid.uuid4()}",
            [{"method": "transfer", "amount": "100.00", "reference": "TRF-1"}],
            [{"document_id": invoice["id"], "amount": str(remaining + 1)}],
        ),
        headers=admin,
    )
    assert too_much.status_code == 422
    assert too_much.json()["code"] == "sales_receipt_exceeds_balance"

    second = await e2e_client.post(
        RECEIPTS,
        json=body(
            f"rc-{uuid.uuid4()}",
            [{"method": "transfer", "amount": "100.00", "reference": "TRF-1"}],
            [{"document_id": invoice["id"], "amount": str(remaining)}],
        ),
        headers=admin,
    )
    assert second.status_code == 201, second.text
    second_receipt = second.json()
    assert _d(second_receipt["unapplied"]) == Decimal("100.00") - remaining
    document = (
        await e2e_client.get(f"{RECEIVABLES}/documents/{invoice['id']}", headers=admin)
    ).json()
    assert _d(document["balance"]) == 0

    annulled = await e2e_client.post(
        f"{RECEIPTS}/{receipt['id']}/annul", json={"reason": "Billete falso"}, headers=admin
    )
    assert annulled.status_code == 200, annulled.text
    assert annulled.json()["status"] == "annulled"
    again = await e2e_client.post(
        f"{RECEIPTS}/{receipt['id']}/annul", json={"reason": "Billete falso"}, headers=admin
    )
    assert again.json()["code"] == "sales_receipt_annulled"
    document = (
        await e2e_client.get(f"{RECEIVABLES}/documents/{invoice['id']}", headers=admin)
    ).json()
    assert _d(document["balance"]) == Decimal("1.00")

    applied = await e2e_client.post(
        f"{RECEIPTS}/{second_receipt['id']}/apply",
        json={"applications": [{"document_id": invoice["id"], "amount": "1.00"}]},
        headers=admin,
    )
    assert applied.status_code == 200, applied.text
    assert _d(applied.json()["unapplied"]) == Decimal("99.00") - remaining

    account = (await e2e_client.get(f"{RECEIVABLES}/customers/{customer_id}", headers=admin)).json()
    assert _d(account["balance"]) == 0
    assert _d(account["credit"]) == Decimal("99.00") - remaining
    assert {item["id"] for item in account["receipts"]} >= {receipt["id"], second_receipt["id"]}

    certificate = await e2e_client.put(
        f"{RECEIVABLES}/documents/{invoice['id']}/withholding-certificate",
        json={"certificate_number": "CR-1", "issued_on": today, "amount": "0.10"},
        headers=admin,
    )
    pdf = await e2e_client.get(f"{RECEIPTS}/{receipt['id']}/pdf", headers=admin)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"
    assert certificate.status_code == 422
    assert certificate.json()["code"] == "sales_withholding_not_applicable"
    assert order["id"]
