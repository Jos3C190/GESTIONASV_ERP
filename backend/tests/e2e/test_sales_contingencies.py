"""V4a: API de contingencias contra el servicio DTE real en modo simulado.

Recorrido completo: registrar al responsable, activar la contingencia del establecimiento,
facturar (el documento nace en contingencia), cerrar (el evento se informa con sello simulado)
y seguir el documento hasta que queda simulado. También permisos, errores y bitácora.
"""

from __future__ import annotations

import uuid

import pytest
from app.core.config import settings
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.dte_worker import (
    dte_client,
    follow_contingency_document,
    object_storage,
    process_fiscal_document,
)
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.fiscal import FiscalPointOfSaleModel
from httpx import AsyncClient
from sqlalchemy import select

from tests.e2e.test_sales_invoices import (
    DOCUMENTS,
    ORDER_SELLER,
    ORDERS,
    _confirmed_order,
    _with_policy,
)

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

CONTINGENCIES = "/api/v1/sales/contingencies"
RESPONSIBLE = {
    "name": "Encargada de facturación",
    "document_type": "13",
    "document_number": "01234567-8",
}


async def _establishment(point: uuid.UUID) -> uuid.UUID:
    async with async_session_factory() as session:
        model = await session.get(FiscalPointOfSaleModel, point)
        assert model is not None
        return model.establishment_id


async def _actions(company_id: str, resource_type: str) -> list[str]:
    async with async_session_factory() as session:
        rows = await session.scalars(
            select(AuditLog.action)
            .where(
                AuditLog.company_id == uuid.UUID(company_id),
                AuditLog.resource_type == resource_type,
            )
            .order_by(AuditLog.created_at)
        )
        return list(rows)


async def test_contingency_round_trip_in_simulated_mode(e2e_client: AsyncClient) -> None:
    admin, order, point = await _confirmed_order(e2e_client)
    establishment = await _establishment(point)
    client = dte_client()
    assert client is not None

    invalid = await e2e_client.put(
        f"{CONTINGENCIES}/responsible",
        json={**RESPONSIBLE, "document_type": "99"},
        headers=admin,
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "sales_contingency_responsible_invalid"
    saved = await e2e_client.put(f"{CONTINGENCIES}/responsible", json=RESPONSIBLE, headers=admin)
    assert saved.status_code == 200, saved.text

    no_reason = await e2e_client.post(
        CONTINGENCIES,
        json={"establishment_id": str(establishment), "contingency_type": 5},
        headers=admin,
    )
    assert no_reason.status_code == 422
    assert no_reason.json()["code"] == "sales_contingency_reason_required"
    unknown = await e2e_client.post(
        CONTINGENCIES,
        json={"establishment_id": str(uuid.uuid4()), "contingency_type": 4},
        headers=admin,
    )
    assert unknown.status_code == 404

    activated = await e2e_client.post(
        CONTINGENCIES,
        json={"establishment_id": str(establishment), "contingency_type": 4},
        headers=admin,
    )
    assert activated.status_code == 201, activated.text
    window = activated.json()
    assert window["status"] == "ACTIVA"
    assert window["contingency_label"].startswith("Falla en el suministro de servicio de energía")
    assert window["branch_name"]
    again = await e2e_client.post(
        CONTINGENCIES,
        json={"establishment_id": str(establishment), "contingency_type": 4},
        headers=admin,
    )
    assert again.status_code == 409
    assert again.json()["code"] == "sales_contingency_already_active"

    overview = (await e2e_client.get(CONTINGENCIES, headers=admin)).json()
    assert overview["active"] is True
    assert overview["responsible"] == RESPONSIBLE
    assert window["id"] in {item["id"] for item in overview["windows"]}

    # El documento nace en contingencia: tiene número y PDF, sin sello.
    document = (
        await e2e_client.post(
            f"{ORDERS}/{order['id']}/invoice",
            json={"point_of_sale_id": str(point)},
            headers=admin,
        )
    ).json()
    await process_fiscal_document(
        uuid.UUID(document["id"]), client=client, storage=object_storage()
    )
    shown = (await e2e_client.get(f"{DOCUMENTS}/{document['id']}", headers=admin)).json()
    assert shown["status"] == "contingency", (shown["error_code"], shown["error_message"])
    assert shown["contingency_type"] == 4
    assert shown["has_pdf"] is True
    assert shown["error_code"] is None, shown

    closed = await e2e_client.post(f"{CONTINGENCIES}/{window['id']}/close", headers=admin)
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "COMPLETADA", closed.json()
    assert closed.json()["event_seal"]
    assert closed.json()["documents"]["total"] == 1

    followed = await follow_contingency_document(
        uuid.UUID(document["id"]), client=client, storage=object_storage()
    )
    assert followed is not None
    assert followed.status.value == "simulated"
    dte = (await e2e_client.get(f"{DOCUMENTS}/{document['id']}/json", headers=admin)).json()
    assert dte["identificacion"]["tipoModelo"] == 2
    assert dte["identificacion"]["tipoContingencia"] == 4

    actions = await _actions(admin["X-Company-ID"], "sales_contingency")
    assert actions[-2:] == ["ACTIVATE_CONTINGENCY", "CLOSE_CONTINGENCY"]
    assert "CREATE" in await _actions(admin["X-Company-ID"], "company_contingency_responsible") or (
        "UPDATE" in await _actions(admin["X-Company-ID"], "company_contingency_responsible")
    )


async def test_contingency_needs_its_permission(e2e_client: AsyncClient) -> None:
    admin, _order, point = await _confirmed_order(e2e_client)
    seller = await _with_policy(e2e_client, admin, ORDER_SELLER, "5", "2", False)
    establishment = await _establishment(point)
    denied = await e2e_client.post(
        CONTINGENCIES,
        json={"establishment_id": str(establishment), "contingency_type": 2},
        headers=seller,
    )
    assert denied.status_code == 403
    assert (await e2e_client.get(CONTINGENCIES, headers=seller)).status_code == 403
    closing = await e2e_client.post(f"{CONTINGENCIES}/999999/close", headers=admin)
    assert closing.status_code == 404
    assert closing.json()["code"] == "sales_contingency_not_found"
