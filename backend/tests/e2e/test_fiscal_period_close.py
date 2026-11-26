"""V8b2: cerrar un mes bloquea los movimientos con fecha de ese mes; reabrirlo pide motivo."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app.core.config import settings
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.sales_fiscal import SalesFiscalDocumentModel
from httpx import AsyncClient

from tests.e2e.test_sales_invalidations import REQUESTER
from tests.e2e.test_sales_invoices import DOCUMENTS
from tests.e2e.test_sales_notes import _ccf

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

BOOKS = "/api/v1/fiscal-books"
_TZ = ZoneInfo("America/El_Salvador")


def _previous_month(today: date) -> date:
    return today.replace(day=1) - timedelta(days=1)


async def _move_issue_date(document_id: str, day: date) -> None:
    async with async_session_factory() as session:
        model = await session.get(SalesFiscalDocumentModel, uuid.UUID(document_id))
        assert model is not None
        model.issued_at = datetime(day.year, day.month, day.day, 12, tzinfo=_TZ)
        await session.commit()


async def test_closed_month_blocks_dated_movements(e2e_client: AsyncClient) -> None:
    admin, order, ccf = await _ccf(e2e_client)
    today = datetime.now(_TZ).date()
    last_month = _previous_month(today)
    previous = f"{last_month:%Y-%m}"
    current = f"{today:%Y-%m}"

    # El mes actual no se cierra: todavía recibe documentos.
    status = (await e2e_client.get(f"{BOOKS}/{current}/close", headers=admin)).json()
    assert status["closed"] is None
    assert any("todavía no termina" in item for item in status["blockers"])
    refused = await e2e_client.post(f"{BOOKS}/{current}/close", headers=admin)
    assert refused.status_code == 422
    assert refused.json()["code"] == "fiscal_period_not_ended"

    closed = await e2e_client.post(f"{BOOKS}/{previous}/close", headers=admin)
    assert closed.status_code == 200, closed.text
    try:
        body = closed.json()
        assert body["closed"]["status"] == "closed"
        assert "balance" in body["closed"]["summary"]
        twice = await e2e_client.post(f"{BOOKS}/{previous}/close", headers=admin)
        assert twice.status_code == 409
        assert twice.json()["code"] == "fiscal_period_already_closed"

        # Un cobro fechado en el mes cerrado se rechaza; uno de hoy pasa.
        document = (
            await e2e_client.get(f"/api/v1/sales/receivables/documents/{ccf['id']}", headers=admin)
        ).json()

        def receipt(day: date) -> dict:
            return {
                "branch_id": order["branch_id"],
                "customer_id": document["customer_id"],
                "received_on": day.isoformat(),
                "payments": [{"method": "cash", "amount": "1.00"}],
                "applications": [],
                "idempotency_key": f"rc-{uuid.uuid4()}",
            }

        blocked = await e2e_client.post(
            "/api/v1/sales/receipts", json=receipt(last_month), headers=admin
        )
        assert blocked.status_code == 422
        assert blocked.json()["code"] == "fiscal_period_closed"
        assert "reábrelo" in blocked.json()["message"]
        allowed = await e2e_client.post(
            "/api/v1/sales/receipts", json=receipt(today), headers=admin
        )
        assert allowed.status_code == 201, allowed.text

        # Un documento emitido en el mes cerrado no se invalida.
        await _move_issue_date(ccf["id"], last_month)
        invalidate = await e2e_client.post(
            f"{DOCUMENTS}/{ccf['id']}/invalidate",
            json={"reason": "El cliente desistió de la compra", "requester": REQUESTER},
            headers=admin,
        )
        assert invalidate.status_code == 422
        assert invalidate.json()["code"] == "fiscal_period_closed"

        short = await e2e_client.post(
            f"{BOOKS}/{previous}/reopen", json={"reason": "corto"}, headers=admin
        )
        assert short.status_code == 422
    finally:
        reopened = await e2e_client.post(
            f"{BOOKS}/{previous}/reopen",
            json={"reason": "Corrección de un cobro registrado tarde"},
            headers=admin,
        )
    assert reopened.status_code == 200, reopened.text
    after = reopened.json()
    assert after["closed"] is None
    assert after["history"][0]["status"] == "reopened"
    assert after["history"][0]["reopen_reason"] == "Corrección de un cobro registrado tarde"
    again = await e2e_client.post("/api/v1/sales/receipts", json=receipt(last_month), headers=admin)
    assert again.status_code == 201, again.text
    not_closed = await e2e_client.post(
        f"{BOOKS}/{previous}/reopen",
        json={"reason": "Otra reapertura sin cierre"},
        headers=admin,
    )
    assert not_closed.status_code == 422
    assert not_closed.json()["code"] == "fiscal_period_not_closed"
