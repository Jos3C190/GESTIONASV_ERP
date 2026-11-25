"""V4d: la nota de remisión que se emite al despachar un traslado, contra el servicio simulado."""

from __future__ import annotations

import uuid

import pytest
from app.core.config import settings
from httpx import AsyncClient

from tests.e2e.test_inventory_transfers import (
    _committed_transfer_context,
    _create_preparation,
    _dispatch,
)
from tests.e2e.test_sales_invalidations import (
    REQUESTER,
    RESPONSIBLE,
    _process_document,
    _process_invalidation,
    _set_status,
)
from tests.e2e.test_sales_invoices import DOCUMENTS, _issuer

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

TRANSFERS = "/api/v1/inventory/transfers"


async def _enable_remission(client: AsyncClient, headers: dict[str, str], enabled: bool) -> None:
    response = await client.put(
        "/api/v1/fiscal/document-types/04",
        json={"is_enabled": enabled, "certification_status": "pending"},
        headers=headers,
    )
    assert response.status_code == 200, response.text


async def _transfer(client: AsyncClient, *, fiscal: bool = True, enabled: bool = True):
    suffix = uuid.uuid4().hex
    values, headers = await _committed_transfer_context(client, suffix)
    if fiscal:
        await _issuer(values.company_id, values.origin_branch_id)
        await _issuer(values.company_id, values.destination_branch_id)
    await _enable_remission(client, headers, enabled)
    transfer = await _create_preparation(client, values, headers, suffix)
    return values, headers, transfer, suffix


async def test_dispatch_issues_the_remission_note(e2e_client: AsyncClient) -> None:
    _values, headers, transfer, suffix = await _transfer(e2e_client)
    dispatched = await _dispatch(e2e_client, transfer, headers, suffix, _values.vehicle_id)
    assert dispatched.status_code == 200, dispatched.text

    url = f"{TRANSFERS}/{transfer['id']}/remission"
    remission = (await e2e_client.get(url, headers=headers)).json()
    assert remission["enabled"] is True
    document = remission["document"]
    assert document["document_type"] == "04"
    assert document["status"] == "pending"
    assert document["sale_id"] is None
    assert document["transfer_id"] == transfer["id"]
    assert document["transfer_code"] == transfer["code"]

    await _process_document(document["id"])
    issued = (await e2e_client.get(f"{DOCUMENTS}/{document['id']}", headers=headers)).json()
    assert issued["status"] == "simulated", issued
    assert issued["control_number"].startswith("DTE-04-")
    dte = (await e2e_client.get(f"{DOCUMENTS}/{document['id']}/json", headers=headers)).json()
    assert dte["receptor"]["bienTitulo"] == "04"
    assert dte["cuerpoDocumento"][0]["cantidad"] == 10
    assert transfer["code"] in dte["resumen"]["observaciones"]
    listed = (
        await e2e_client.get(DOCUMENTS, params={"document_type": "04"}, headers=headers)
    ).json()
    assert [item["id"] for item in listed["items"]] == [document["id"]]

    # Una NR sellada no se anula: se corrige con una de reemplazo (tipo 1).
    saved = await e2e_client.put(
        "/api/v1/sales/contingencies/responsible", json=RESPONSIBLE, headers=headers
    )
    assert saved.status_code == 200, saved.text
    annul = await e2e_client.post(
        f"{DOCUMENTS}/{document['id']}/invalidate",
        json={"reason": "Se despachó por error", "requester": REQUESTER},
        headers=headers,
    )
    assert annul.status_code == 422
    assert annul.json()["code"] == "transfer_remission_not_annullable"
    corrected = await e2e_client.post(
        f"{DOCUMENTS}/{document['id']}/correct", json={"requester": REQUESTER}, headers=headers
    )
    assert corrected.status_code == 202, corrected.text
    replacement = corrected.json()["replacement"]
    assert replacement["document_type"] == "04"
    assert replacement["transfer_id"] == transfer["id"]
    await _process_document(replacement["id"])
    await _process_invalidation(corrected.json()["invalidation"]["id"])
    original = (await e2e_client.get(f"{DOCUMENTS}/{document['id']}", headers=headers)).json()
    assert original["status"] == "invalidated"
    current = (await e2e_client.get(url, headers=headers)).json()["document"]
    assert current["id"] == replacement["id"]


async def test_rejected_note_is_issued_again(e2e_client: AsyncClient) -> None:
    values, headers, transfer, suffix = await _transfer(e2e_client)
    dispatched = await _dispatch(e2e_client, transfer, headers, suffix, values.vehicle_id)
    assert dispatched.status_code == 200, dispatched.text
    url = f"{TRANSFERS}/{transfer['id']}/remission"
    first = (await e2e_client.get(url, headers=headers)).json()["document"]

    early = await e2e_client.post(f"{url}/reissue", headers=headers)
    assert early.status_code == 422
    assert early.json()["code"] == "transfer_remission_already_issued"

    await _set_status(first["id"], "rejected")
    again = await e2e_client.post(f"{url}/reissue", headers=headers)
    assert again.status_code == 201, again.text
    assert again.json()["id"] != first["id"]
    assert again.json()["status"] == "pending"
    current = (await e2e_client.get(url, headers=headers)).json()["document"]
    assert current["id"] == again.json()["id"]


async def test_without_issuer_the_transfer_does_not_leave(e2e_client: AsyncClient) -> None:
    values, headers, transfer, suffix = await _transfer(e2e_client, fiscal=False)
    blocked = await _dispatch(e2e_client, transfer, headers, suffix, values.vehicle_id)
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["code"] == "transfer_remission_issuer_missing"
    detail = (await e2e_client.get(f"{TRANSFERS}/{transfer['id']}", headers=headers)).json()
    assert detail["status"] == "preparation"
    assert detail["dispatched_at"] is None


async def test_disabled_remission_keeps_the_dispatch_as_before(e2e_client: AsyncClient) -> None:
    values, headers, transfer, suffix = await _transfer(e2e_client, fiscal=False, enabled=False)
    dispatched = await _dispatch(e2e_client, transfer, headers, suffix, values.vehicle_id)
    assert dispatched.status_code == 200, dispatched.text
    remission = (
        await e2e_client.get(f"{TRANSFERS}/{transfer['id']}/remission", headers=headers)
    ).json()
    assert remission == {"enabled": False, "document": None}
