"""V4a: un documento generado en contingencia y su seguimiento hasta el sello.

Un cliente DTE falso responde como el servicio: primero CONTINGENCIA (documento en modelo
diferido) y después, al consultarlo, el estado final. El recorrido real del servicio (ventana,
evento y transmisión) está cubierto por sus pruebas (`contingenciaPorEmisor.test.js` y
`contingenciaSimulada.test.js`).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from app.core.config import settings
from app.domain.ports.dte_service import (
    ConnectionCheck,
    DocumentState,
    IssuerCredentials,
    IssueResult,
)
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.dte_worker import (
    follow_contingency_document,
    object_storage,
    process_fiscal_document,
)
from app.infrastructure.models.audit import AuditLog
from httpx import AsyncClient
from sqlalchemy import select

from tests.e2e.test_sales_invoices import DOCUMENTS, ORDERS, _confirmed_order

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

CONTROL = "DTE-01-M001P001-000000000000042"


class FakeDte:
    """Emite en contingencia y responde la consulta con el estado que se le indique."""

    def __init__(self) -> None:
        self.state = DocumentState("CONTINGENCIA", None)
        self.generation_code = str(uuid.uuid4()).upper()

    async def register_issuer(
        self,
        nit: str,
        *,
        name: str,
        mode: str,
        document_types: list[str],
        credentials: IssuerCredentials | None = None,
        responsible: object = None,
    ) -> None:
        return None

    async def test_issuer(self, nit: str) -> ConnectionCheck:
        return ConnectionCheck(True, True, "ok", True, "ok")

    async def issue(
        self, document_type: str, *, nit: str, idempotency_key: str, body: dict[str, Any]
    ) -> IssueResult:
        return IssueResult(
            status="CONTINGENCIA",
            generation_code=self.generation_code,
            control_number=CONTROL,
            seal=None,
            response={"estado": "CONTINGENCIA", "issuanceMode": "SIMULATED"},
        )

    async def document_state(self, nit: str, generation_code: str) -> DocumentState:
        assert generation_code == self.generation_code
        return self.state

    async def document_json(self, nit: str, generation_code: str) -> dict[str, Any]:
        return {
            "identificacion": {
                "ambiente": "00",
                "tipoModelo": 2,
                "tipoOperacion": 2,
                "tipoContingencia": 4,
                "motivoContin": None,
            },
            "resumen": {},
        }

    async def document_pdf(self, nit: str, generation_code: str) -> bytes:
        return b"%PDF-1.7 contingencia"


async def _actions(document_id: str) -> list[str]:
    async with async_session_factory() as session:
        rows = await session.scalars(
            select(AuditLog.action)
            .where(AuditLog.resource_id == document_id)
            .order_by(AuditLog.created_at)
        )
        return list(rows)


async def test_contingency_document_waits_for_its_seal(e2e_client: AsyncClient) -> None:
    admin, order, point = await _confirmed_order(e2e_client)
    created = await e2e_client.post(
        f"{ORDERS}/{order['id']}/invoice",
        json={"point_of_sale_id": str(point)},
        headers=admin,
    )
    assert created.status_code == 202, created.text
    document_id = created.json()["id"]
    fake = FakeDte()

    issued = await process_fiscal_document(
        uuid.UUID(document_id), client=fake, storage=object_storage()
    )
    assert issued is not None
    assert issued.status.value == "contingency", issued.error_message
    assert issued.control_number == CONTROL
    assert issued.contingency_type == 4
    assert issued.contingency_at is not None
    assert issued.seal is None
    assert issued.pdf_object_key is not None, "el cliente recibe la versión legible"

    shown = await e2e_client.get(f"{DOCUMENTS}/{document_id}", headers=admin)
    assert shown.status_code == 200
    assert shown.json()["status"] == "contingency"
    assert shown.json()["contingency_type"] == 4
    listed = await e2e_client.get(DOCUMENTS, params={"status": "contingency"}, headers=admin)
    assert document_id in {item["id"] for item in listed.json()["items"]}

    # Un pedido con un documento en contingencia no genera otro: se devuelve el mismo.
    again = await e2e_client.post(
        f"{ORDERS}/{order['id']}/invoice",
        json={"point_of_sale_id": str(point)},
        headers=admin,
    )
    assert again.status_code == 200, again.text
    assert again.json()["id"] == document_id, "devuelve el mismo documento"

    # Mientras el servicio no tenga el sello, el seguimiento solo lo marca como revisado.
    waiting = await follow_contingency_document(
        uuid.UUID(document_id), client=fake, storage=object_storage()
    )
    assert waiting is not None
    assert waiting.status.value == "contingency"

    fake.state = DocumentState("SIMULADO", None)
    sealed = await follow_contingency_document(
        uuid.UUID(document_id), client=fake, storage=object_storage()
    )
    assert sealed is not None
    assert sealed.status.value == "simulated"
    assert sealed.contingency_type == 4, "conserva de dónde vino"
    assert (
        await follow_contingency_document(
            uuid.UUID(document_id), client=fake, storage=object_storage()
        )
        is None
    ), "ya no está en contingencia"
    actions = await _actions(document_id)
    assert "FISCAL_DOCUMENT_CONTINGENCY" in actions
    assert actions[-1] == "FISCAL_DOCUMENT_ISSUED"


async def test_contingency_document_rejected_after_transmission(e2e_client: AsyncClient) -> None:
    admin, order, point = await _confirmed_order(e2e_client)
    document_id = (
        await e2e_client.post(
            f"{ORDERS}/{order['id']}/invoice",
            json={"point_of_sale_id": str(point)},
            headers=admin,
        )
    ).json()["id"]
    fake = FakeDte()
    await process_fiscal_document(uuid.UUID(document_id), client=fake, storage=object_storage())
    fake.state = DocumentState("RECHAZADO", None)
    rejected = await follow_contingency_document(
        uuid.UUID(document_id), client=fake, storage=object_storage()
    )
    assert rejected is not None
    assert rejected.status.value == "rejected"
    assert rejected.error_code == "dte_rejected"
