"""V9c: prueba integral del ciclo de venta y su conciliación.

Recorre pedido → salida de inventario al confirmar → crédito fiscal → cobro → devolución aceptada con su nota de
crédito → saldo a favor → reintegro, y comprueba que los módulos cuadran entre sí: la cartera queda en cero, el
kardex registra la salida y la devolución, el análisis comercial suma la venta, la devolución y el costo, y el libro
de IVA del mes trae el crédito fiscal y su nota. Un vendedor sin permiso no ve cifras ni libros.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from app.core.config import settings
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.inventory_valuation import InventoryValuationEntryModel
from httpx import AsyncClient
from sqlalchemy import func, select

from tests.e2e.test_sales_discounts import _login
from tests.e2e.test_sales_invalidations import _process_document
from tests.e2e.test_sales_invoices import DOCUMENTS
from tests.e2e.test_sales_notes import _ccf
from tests.e2e.test_sales_return_fiscal import SALES, _accept, _received_return

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

ANALYTICS = "/api/v1/sales/analytics"
RECEIVABLES = "/api/v1/sales/receivables"
RECEIPTS = "/api/v1/sales/receipts"
BOOKS = "/api/v1/fiscal-books"


def _d(value: object) -> Decimal:
    return Decimal(str(value))


async def _kardex(item_id: str) -> dict[str, Decimal]:
    async with async_session_factory() as session:
        rows = await session.execute(
            select(
                InventoryValuationEntryModel.kind,
                func.sum(InventoryValuationEntryModel.quantity_base),
            )
            .where(InventoryValuationEntryModel.inventory_item_id == uuid.UUID(item_id))
            .group_by(InventoryValuationEntryModel.kind)
        )
        return {kind: Decimal(quantity) for kind, quantity in rows.all()}


async def test_full_sales_cycle_reconciles(e2e_client: AsyncClient) -> None:  # noqa: PLR0915
    _, analyst = await _login(e2e_client, superuser=True)
    today = datetime.now(ZoneInfo("America/El_Salvador")).date()
    period = f"{today:%Y-%m}"
    before = (await e2e_client.get(ANALYTICS, headers=analyst)).json()

    # 1. Pedido de 4 unidades a $10.00 sin IVA (costo de kardex $7.00), entregado al confirmar,
    #    y su crédito fiscal simulado.
    admin, order, ccf = await _ccf(e2e_client, stock="4")
    [line] = order["lines"]
    item_id = line["inventory_item_id"]
    assert order["delivery_progress"] == "complete"
    kardex = await _kardex(item_id)
    assert kardex["issue"] == Decimal("4")

    # 2. Cobro total del documento.
    document = (await e2e_client.get(f"{RECEIVABLES}/documents/{ccf['id']}", headers=admin)).json()
    payable = _d(document["payable"])
    paid = await e2e_client.post(
        RECEIPTS,
        json={
            "branch_id": order["branch_id"],
            "customer_id": document["customer_id"],
            "received_on": today.isoformat(),
            "payments": [{"method": "transfer", "amount": str(payable), "reference": "TRF-CICLO"}],
            "applications": [{"document_id": ccf["id"], "amount": str(payable)}],
            "idempotency_key": f"rc-{uuid.uuid4()}",
        },
        headers=admin,
    )
    assert paid.status_code == 201, paid.text
    receipt = paid.json()

    # 3. El cliente devuelve una unidad: al aceptarla sale la nota de crédito y la mercadería vuelve.
    return_id, line_id, per_unit = await _received_return(e2e_client, admin, order["id"], 1)
    resolved = await e2e_client.post(
        f"{SALES}/returns/{return_id}/resolve",
        headers={**admin, "Idempotency-Key": f"ciclo-{uuid.uuid4()}"},
        json=_accept(line_id, per_unit),
    )
    assert resolved.status_code == 200, resolved.text
    [adjustment] = resolved.json()["fiscal_adjustments"]
    assert adjustment["status"] == "issued", adjustment
    await _process_document(adjustment["fiscal_note_id"])
    note = (
        await e2e_client.get(f"{DOCUMENTS}/{adjustment['fiscal_note_id']}", headers=admin)
    ).json()
    assert note["status"] == "simulated"
    kardex = await _kardex(item_id)
    assert kardex["customer_return"] == Decimal("1")

    # 4. La nota deja el documento pagado de más: el excedente vuelve al recibo y se reintegra.
    released = (await e2e_client.get(f"{RECEIPTS}/{receipt['id']}", headers=admin)).json()
    credit = _d(released["unapplied"])
    assert credit == _d(note["total"])
    refunded = await e2e_client.post(
        f"{RECEIPTS}/{receipt['id']}/refunds",
        json={
            "refunded_on": today.isoformat(),
            "amount": str(credit),
            "method": "transfer",
            "reference": "TRF-REINTEGRO",
            "reason": "Devolución de una unidad",
            "idempotency_key": f"ri-{uuid.uuid4()}",
        },
        headers=admin,
    )
    assert refunded.status_code == 201, refunded.text

    # Conciliación: la cartera del documento queda en cero y sin saldo a favor.
    document = (await e2e_client.get(f"{RECEIVABLES}/documents/{ccf['id']}", headers=admin)).json()
    assert _d(document["balance"]) == 0
    account = (
        await e2e_client.get(f"{RECEIVABLES}/customers/{document['customer_id']}", headers=admin)
    ).json()
    assert _d(account["credit"]) == 0

    # El análisis suma la venta, la devolución y el costo de salida.
    after = (await e2e_client.get(ANALYTICS, headers=analyst)).json()
    delta = {
        key: _d(after["totals"][key]) - _d(before["totals"][key])
        for key in ("net_sales", "returns", "cost")
    }
    assert delta == {
        "net_sales": Decimal("40.00"),
        "returns": Decimal("10.00"),
        "cost": Decimal("28.00"),
    }
    assert after["totals"]["documents"] - before["totals"]["documents"] == 1

    # El libro de contribuyentes del mes trae el crédito fiscal y su nota; el anexo, el documento.
    books = await e2e_client.get(f"{BOOKS}/{period}", params={"mode": "simulated"}, headers=admin)
    assert books.status_code == 200, books.text
    month = books.json()
    rows = {row["control_number"]: row for row in month["contributor_book"]}
    assert _d(rows[ccf["control_number"]]["taxed"]) == Decimal("40.00")
    assert abs(_d(rows[note["control_number"]]["taxed"])) == Decimal("10.00")
    generation = str(ccf["generation_code"]).replace("-", "").upper()
    cells = [
        str(cell).replace("-", "").upper()
        for annex in month["annexes"]
        for row in annex["rows"]
        for cell in row
    ]
    assert generation in cells

    # Permisos: quien solo consulta ventas no ve cifras ni libros.
    _, seller = await _login(e2e_client, superuser=False, permissions=("sales:read",))
    assert (await e2e_client.get(ANALYTICS, headers=seller)).status_code == 403
    assert (await e2e_client.get(f"{BOOKS}/{period}", headers=seller)).status_code == 403
