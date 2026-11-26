"""V5b: notas de cobro, bloqueo de crédito y estado de cuenta en PDF y por correo."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app.core.config import settings
from httpx import AsyncClient

from tests.e2e.test_sales_quotations import _setup

pytestmark = pytest.mark.e2e

RECEIVABLES = "/api/v1/sales/receivables"


async def test_notes_block_and_statement(e2e_client: AsyncClient) -> None:
    admin, body, _unit = await _setup(e2e_client)
    customer = body["customer_id"]
    base = f"{RECEIVABLES}/customers/{customer}"
    today = datetime.now(ZoneInfo("America/El_Salvador")).date()

    status = (await e2e_client.get(f"{base}/credit", headers=admin)).json()
    assert status["customer"]["credit_blocked"] is False
    assert status["notes"] == []

    past = await e2e_client.post(
        f"{base}/notes",
        json={"note": "Llamar el lunes", "next_action_on": str(today - timedelta(days=1))},
        headers=admin,
    )
    assert past.status_code == 422
    assert past.json()["code"] == "sales_collection_next_action_invalid"
    noted = await e2e_client.post(
        f"{base}/notes",
        json={"note": "Prometió pagar el viernes", "next_action_on": str(today)},
        headers=admin,
    )
    assert noted.status_code == 201, noted.text
    [note] = noted.json()["notes"]
    assert note["note"] == "Prometió pagar el viernes"
    assert note["created_by"]

    blocked = await e2e_client.post(
        f"{base}/block", json={"reason": "Cheque rechazado dos veces"}, headers=admin
    )
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["customer"]["credit_blocked"] is True
    assert blocked.json()["customer"]["credit_block_reason"] == "Cheque rechazado dos veces"
    again = await e2e_client.post(
        f"{base}/block", json={"reason": "Cheque rechazado dos veces"}, headers=admin
    )
    assert again.json()["code"] == "sales_credit_already_blocked"
    unblocked = await e2e_client.post(f"{base}/unblock", headers=admin)
    assert unblocked.json()["customer"]["credit_blocked"] is False

    pdf = await e2e_client.get(f"{base}/statement.pdf", headers=admin)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"

    no_email = await e2e_client.post(f"{base}/send-statement", json={}, headers=admin)
    assert no_email.status_code == 422
    assert no_email.json()["code"] == "sales_statement_recipient_required"
    if settings.SMTP_HOST:
        sent = await e2e_client.post(
            f"{base}/send-statement", json={"to": "cliente@example.com"}, headers=admin
        )
        assert sent.status_code == 200, sent.text
        assert sent.json() == {"sent_to": "cliente@example.com"}
