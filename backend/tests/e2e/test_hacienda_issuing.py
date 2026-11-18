"""V3d: el trabajador registra a la empresa con su modo y sus credenciales de Hacienda.

Un cliente DTE falso registra lo que el trabajador le envía; el camino real del servicio con el
firmador y un Hacienda simulado está cubierto por las pruebas del servicio DTE
(`dte-service/test/integration/modoPorEmisor.test.js`).
"""

from __future__ import annotations

import base64
import uuid
from typing import Any

import pytest
from app.core.config import settings
from app.domain.entities.fiscal import dte_nit
from app.domain.ports.dte_service import ConnectionCheck, IssuerCredentials, IssueResult
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.dte_worker import object_storage, process_fiscal_document
from app.infrastructure.models.fiscal import (
    CompanyFiscalProfileModel,
    CompanyHaciendaCredentialsModel,
)
from app.infrastructure.models.organization import Company
from httpx import AsyncClient

from tests.e2e.test_sales_invoices import ORDERS, _confirmed_order
from tests.hacienda_certificate import hacienda_certificate

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.DTE_SERVICE_URL, reason="Sin servicio DTE configurado"),
]

API = "api-de-la-empresa"
PRI = "privada-de-la-empresa"
SEAL = "2026SELLO00000000000000000000000000000001"


class FakeDte:
    """Responde como el servicio DTE en pruebas de Hacienda y guarda lo que recibe."""

    def __init__(self) -> None:
        self.registrations: list[dict[str, Any]] = []

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
        self.registrations.append({"nit": nit, "mode": mode, "credentials": credentials})

    async def test_issuer(self, nit: str) -> ConnectionCheck:
        return ConnectionCheck(True, True, "ok", True, "ok")

    async def issue(
        self, document_type: str, *, nit: str, idempotency_key: str, body: dict[str, Any]
    ) -> IssueResult:
        self.body = body
        return IssueResult(
            status="TRANSMITIDO",
            generation_code=str(uuid.uuid4()).upper(),
            control_number="DTE-01-M001P001-000000000000009",
            seal=SEAL,
            response={"estado": "TRANSMITIDO"},
        )

    async def document_json(self, nit: str, generation_code: str) -> dict[str, Any]:
        return {"identificacion": {"ambiente": "00"}, "resumen": {}}

    async def document_pdf(self, nit: str, generation_code: str) -> bytes:
        return b"%PDF-1.7 prueba"


async def _in_test_mode(client: AsyncClient, admin: dict[str, str]) -> None:
    company_id = uuid.UUID(admin["X-Company-ID"])
    async with async_session_factory() as session:
        company = await session.get(Company, company_id)
        assert company is not None
        nit = dte_nit(company.nit)
    assert nit is not None
    saved = await client.put(
        "/api/v1/fiscal/hacienda-credentials",
        json={
            "api_password": API,
            "private_key_password": PRI,
            "certificate_base64": base64.b64encode(hacienda_certificate(nit, PRI)).decode(),
        },
        headers=admin,
    )
    assert saved.status_code == 200, saved.text
    # La regla de pasar a pruebas exige una prueba correcta; aquí se deja el modo directo.
    async with async_session_factory() as session:
        profile = await session.get(CompanyFiscalProfileModel, company_id)
        assert profile is not None
        profile.operating_mode = "test"
        await session.commit()


async def test_documents_in_test_mode_register_the_issuer_with_its_credentials(
    e2e_client: AsyncClient,
) -> None:
    admin, order, point = await _confirmed_order(e2e_client)
    company_id = uuid.UUID(admin["X-Company-ID"])
    await _in_test_mode(e2e_client, admin)
    try:
        document = (
            await e2e_client.post(
                f"{ORDERS}/{order['id']}/invoice",
                json={"point_of_sale_id": str(point)},
                headers=admin,
            )
        ).json()
        assert document["mode"] == "hacienda-test"
        fake = FakeDte()
        issued = await process_fiscal_document(
            uuid.UUID(document["id"]), client=fake, storage=object_storage()
        )
        assert issued is not None
        assert issued.status.value == "issued", issued.error_message
        assert issued.seal == SEAL
        [registration] = fake.registrations
        assert registration["mode"] == "hacienda-test"
        credentials = registration["credentials"]
        assert credentials.api_password == API
        assert credentials.private_key_password == PRI
        assert b"CertificadoMH" in credentials.certificate

        # Sin credenciales, falla sin reintentar y con un motivo claro.
        async with async_session_factory() as session:
            stored = await session.get(CompanyHaciendaCredentialsModel, company_id)
            assert stored is not None
            await session.delete(stored)
            await session.commit()
        retried = await e2e_client.post(
            f"/api/v1/sales/fiscal-documents/{document['id']}/retry", headers=admin
        )
        assert retried.status_code == 422  # Ya emitido: no se reintenta.
        second_admin, second_order, second_point = await _confirmed_order(e2e_client)
        assert second_admin["X-Company-ID"] == admin["X-Company-ID"]
        # _confirmed_order deja el perfil en simulado: se vuelve a pruebas, ya sin credenciales.
        async with async_session_factory() as session:
            profile = await session.get(CompanyFiscalProfileModel, company_id)
            assert profile is not None
            profile.operating_mode = "test"
            await session.commit()
        second = (
            await e2e_client.post(
                f"{ORDERS}/{second_order['id']}/invoice",
                json={"point_of_sale_id": str(second_point)},
                headers=admin,
            )
        ).json()
        failed = await process_fiscal_document(
            uuid.UUID(second["id"]), client=FakeDte(), storage=object_storage()
        )
        assert failed is not None
        assert failed.status.value == "failed"
        assert failed.error_code == "hacienda_credentials_missing"
    finally:
        async with async_session_factory() as session:
            profile = await session.get(CompanyFiscalProfileModel, company_id)
            assert profile is not None
            profile.operating_mode = "simulated"
            await session.commit()
