"""V4c: notas de crédito y de débito sobre un CCF, contra el servicio DTE real en modo simulado."""

from __future__ import annotations

import uuid

import pytest
from app.core.config import settings
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.sales_fiscal import SalesFiscalDocumentModel
from httpx import AsyncClient

from tests.e2e.test_customers import _geography, _taxpayer
from tests.e2e.test_sales_invalidations import (
    REQUESTER,
    RESPONSIBLE,
    _issued,
    _process_document,
    _process_invalidation,
)
from tests.e2e.test_sales_invoices import DOCUMENTS, ORDER_SELLER, ORDERS, _issuer, _with_policy
from tests.e2e.test_sales_orders import _create, _order_act, _order_body, _stock
from tests.e2e.test_sales_quotations import _setup

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]


async def _enable_notes(client: AsyncClient, admin: dict[str, str]) -> None:
    for document in ("05", "06"):
        enabled = await client.put(
            f"/api/v1/fiscal/document-types/{document}",
            json={"is_enabled": True, "certification_status": "pending"},
            headers=admin,
        )
        assert enabled.status_code == 200, enabled.text


async def _ccf(client: AsyncClient) -> tuple[dict[str, str], dict, dict]:
    """Un CCF simulado de 4 unidades a $10.00 sin IVA para un cliente contribuyente."""

    admin, body, _unit = await _setup(client)
    await _stock(admin, body, "5")
    company_id = uuid.UUID(admin["X-Company-ID"])
    point = await _issuer(company_id, uuid.UUID(str(body["branch_id"])))
    await _enable_notes(client, admin)
    saved = await client.put(
        "/api/v1/sales/contingencies/responsible", json=RESPONSIBLE, headers=admin
    )
    assert saved.status_code == 200, saved.text
    taxpayer = {
        **_taxpayer(await _geography()),
        "name": f"Distribuidora {uuid.uuid4().hex[:6]}, S.A. de C.V.",
        "document_number": f"0614{uuid.uuid4().int % 10**10:010d}",
    }
    customer = await client.post("/api/v1/customers", json=taxpayer, headers=admin)
    assert customer.status_code == 201, customer.text
    order = await _create(
        client,
        admin,
        _order_body({**body, "customer_id": customer.json()["id"]}, "4", document_type="03"),
    )
    confirmed = await _order_act(client, admin, order, "confirm")
    assert confirmed.status_code == 200, confirmed.text
    invoiced = await client.post(
        f"{ORDERS}/{order['id']}/invoice", json={"point_of_sale_id": str(point)}, headers=admin
    )
    assert invoiced.status_code == 202, invoiced.text
    await _process_document(invoiced.json()["id"])
    ccf = (await client.get(f"{DOCUMENTS}/{invoiced.json()['id']}", headers=admin)).json()
    assert ccf["status"] == "simulated", ccf
    assert ccf["document_type"] == "03"
    return admin, confirmed.json(), ccf


async def test_credit_note_balance_and_the_ccf_lock(e2e_client: AsyncClient) -> None:
    admin, order, ccf = await _ccf(e2e_client)
    url = f"{DOCUMENTS}/{ccf['id']}"
    overview = (await e2e_client.get(f"{url}/notes", headers=admin)).json()
    assert overview["credit_blocker"] is None
    assert overview["debit_blocker"] is None
    assert overview["credit_deadline"] is not None
    [line] = overview["lines"]
    assert (line["quantity"], line["net"], line["remaining_amount"]) == ("4", "40.00", "40.00")

    created = await e2e_client.post(
        f"{url}/credit-note",
        json={
            "reason": "Devolución de una unidad",
            "lines": [{"ccf_line_number": 1, "kind": "return", "quantity": "1"}],
        },
        headers=admin,
    )
    assert created.status_code == 202, created.text
    note = created.json()
    assert (note["document_type"], note["status"], note["total"]) == ("05", "pending", "11.30")
    assert note["related_document_id"] == ccf["id"]
    assert note["sale_id"] == order["id"]
    assert note["renta_operation_type"] == ccf["renta_operation_type"]
    await _process_document(note["id"])
    sealed = (await e2e_client.get(f"{DOCUMENTS}/{note['id']}", headers=admin)).json()
    assert sealed["status"] == "simulated", sealed
    assert sealed["error_code"] is None, sealed["error_message"]

    overview = (await e2e_client.get(f"{url}/notes", headers=admin)).json()
    [line] = overview["lines"]
    assert (line["remaining_quantity"], line["remaining_amount"]) == ("3.000000", "30.00")
    assert [n["document"]["id"] for n in overview["notes"]] == [note["id"]]
    assert overview["notes"][0]["lines"][0]["kind"] == "return"
    options = (
        await e2e_client.get(f"{ORDERS}/{order['id']}/invoice-options", headers=admin)
    ).json()
    assert options["document"]["id"] == ccf["id"], "la nota no reemplaza al CCF del pedido"

    exceeded = await e2e_client.post(
        f"{url}/credit-note",
        json={
            "reason": "Devolución de más",
            "lines": [{"ccf_line_number": 1, "kind": "return", "quantity": "4"}],
        },
        headers=admin,
    )
    assert exceeded.status_code == 422
    assert exceeded.json()["code"] == "sales_note_quantity_exceeded"

    # Un CCF con una nota vigente no se invalida ni se corrige (regla 633).
    blocked = await e2e_client.post(
        f"{url}/invalidate",
        json={"reason": "El cliente desistió", "requester": REQUESTER},
        headers=admin,
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "sales_invoice_has_notes"
    corrected = await e2e_client.post(
        f"{url}/correct", json={"requester": REQUESTER}, headers=admin
    )
    assert corrected.json()["code"] == "sales_invoice_has_notes"

    # La nota se anula (tipo 2) y no se corrige; anularla no cancela el pedido.
    note_url = f"{DOCUMENTS}/{note['id']}"
    not_correctable = await e2e_client.post(
        f"{note_url}/correct", json={"requester": REQUESTER}, headers=admin
    )
    assert not_correctable.json()["code"] == "sales_invoice_not_correctable"
    with_order = await e2e_client.post(
        f"{note_url}/invalidate",
        json={"reason": "Se emitió por error", "requester": REQUESTER, "cancel_order": True},
        headers=admin,
    )
    assert with_order.json()["code"] == "sales_note_cancel_order_invalid"
    invalidation = await e2e_client.post(
        f"{note_url}/invalidate",
        json={"reason": "Se emitió por error", "requester": REQUESTER},
        headers=admin,
    )
    assert invalidation.status_code == 202, invalidation.text
    await _process_invalidation(invalidation.json()["id"])
    assert (await e2e_client.get(note_url, headers=admin)).json()["status"] == "invalidated"
    [line] = (await e2e_client.get(f"{url}/notes", headers=admin)).json()["lines"]
    assert line["remaining_amount"] == "40.00", "la nota anulada devuelve el saldo"


async def test_debit_note_charges(e2e_client: AsyncClient) -> None:
    admin, _order, ccf = await _ccf(e2e_client)
    created = await e2e_client.post(
        f"{DOCUMENTS}/{ccf['id']}/debit-note",
        json={
            "reason": "Ajuste de precio e intereses",
            "charges": [
                {
                    "description": "Ajuste de precio",
                    "quantity": "4",
                    "unit_price": "0.50",
                    "ccf_line_number": 1,
                },
                {
                    "description": "Intereses por mora",
                    "quantity": "1",
                    "unit_price": "3",
                    "nature": "taxed",
                },
            ],
        },
        headers=admin,
    )
    assert created.status_code == 202, created.text
    note = created.json()
    assert (note["document_type"], note["total"]) == ("06", "5.65")
    await _process_document(note["id"])
    sealed = (await e2e_client.get(f"{DOCUMENTS}/{note['id']}", headers=admin)).json()
    assert sealed["status"] == "simulated", sealed
    assert sealed["error_code"] is None, sealed["error_message"]
    lines = (await e2e_client.get(f"{DOCUMENTS}/{ccf['id']}/notes", headers=admin)).json()["lines"]
    assert lines[0]["remaining_amount"] == "40.00", "la nota de débito no consume saldo"


async def test_rules_deadline_and_permission(e2e_client: AsyncClient) -> None:
    admin, _order, _point, invoice = await _issued(e2e_client)
    on_invoice = await e2e_client.post(
        f"{DOCUMENTS}/{invoice['id']}/debit-note",
        json={
            "reason": "Cargo sobre factura",
            "charges": [
                {"description": "Flete", "quantity": "1", "unit_price": "1", "nature": "taxed"}
            ],
        },
        headers=admin,
    )
    assert on_invoice.status_code == 422
    assert on_invoice.json()["code"] == "sales_note_requires_ccf"

    admin, _order, ccf = await _ccf(e2e_client)
    seller = await _with_policy(e2e_client, admin, ORDER_SELLER, "5", "2", False)
    denied = await e2e_client.post(
        f"{DOCUMENTS}/{ccf['id']}/credit-note",
        json={
            "reason": "Sin permiso",
            "lines": [{"ccf_line_number": 1, "kind": "discount", "amount": "1"}],
        },
        headers=seller,
    )
    assert denied.status_code == 403

    # Pasados tres meses desde el CCF ya no se rebaja; la nota de débito sigue disponible.
    async with async_session_factory() as session:
        model = await session.get(SalesFiscalDocumentModel, uuid.UUID(ccf["id"]))
        assert model is not None
        assert model.dte_json is not None
        model.dte_json = {
            **model.dte_json,
            "identificacion": {**model.dte_json["identificacion"], "fecEmi": "2026-01-02"},
        }
        await session.commit()
    overview = (await e2e_client.get(f"{DOCUMENTS}/{ccf['id']}/notes", headers=admin)).json()
    assert "02/04/2026" in overview["credit_blocker"]
    assert overview["debit_blocker"] is None
    late = await e2e_client.post(
        f"{DOCUMENTS}/{ccf['id']}/credit-note",
        json={
            "reason": "Rebaja tardía",
            "lines": [{"ccf_line_number": 1, "kind": "discount", "amount": "1"}],
        },
        headers=admin,
    )
    assert late.status_code == 422
    assert late.json()["code"] == "sales_note_deadline_passed"
