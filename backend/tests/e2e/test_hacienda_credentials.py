"""V3d: credenciales de Hacienda de la empresa (secretos ocultos, validación, prueba y modo)."""

from __future__ import annotations

import base64
import uuid

import pytest
from app.domain.entities.fiscal import dte_nit
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.fiscal import CompanyHaciendaCredentialsModel
from app.infrastructure.models.organization import Company
from httpx import AsyncClient
from sqlalchemy import select

from tests.e2e.test_fiscal_settings import _login
from tests.hacienda_certificate import hacienda_certificate

pytestmark = pytest.mark.e2e

BASE = "/api/v1/fiscal/hacienda-credentials"
API = "clave-api-secreta"
PRI = "clave-privada-secreta"


async def _company_nit(headers: dict[str, str]) -> str:
    async with async_session_factory() as session:
        company = await session.get(Company, uuid.UUID(headers["X-Company-ID"]))
        assert company is not None
        nit = dte_nit(company.nit)
        if nit is None:
            company.nit = "06142803901121"
            await session.commit()
            nit = "06142803901121"
    return nit


def _certificate(nit: str, password: str = PRI) -> str:
    return base64.b64encode(hacienda_certificate(nit, password)).decode("ascii")


async def test_credentials_are_validated_encrypted_and_never_returned(
    e2e_client: AsyncClient,
) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    nit = await _company_nit(headers)
    assert (await e2e_client.get(BASE, headers=headers)).json() == {
        "configured": False,
        "certificate_nit": None,
        "certificate_sha256": None,
        "last_test_at": None,
        "last_test_ok": None,
        "last_test_error": None,
        "updated_at": None,
    }

    other = await e2e_client.put(
        BASE,
        json={
            "api_password": API,
            "private_key_password": PRI,
            "certificate_base64": _certificate("06140101900011"),
        },
        headers=headers,
    )
    assert other.status_code == 422
    assert other.json()["code"] == "hacienda_certificate_nit_mismatch"
    wrong = await e2e_client.put(
        BASE,
        json={
            "api_password": API,
            "private_key_password": "otra",
            "certificate_base64": _certificate(nit),
        },
        headers=headers,
    )
    assert wrong.json()["code"] == "hacienda_private_key_password_invalid"

    saved = await e2e_client.put(
        BASE,
        json={
            "api_password": API,
            "private_key_password": PRI,
            "certificate_base64": _certificate(nit),
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["configured"] is True
    assert saved.json()["certificate_nit"] == nit
    assert API not in saved.text
    assert PRI not in saved.text

    # Editar sin escribir nada conserva lo guardado (y vuelve a validarlo).
    kept = await e2e_client.put(BASE, json={}, headers=headers)
    assert kept.status_code == 200, kept.text
    assert kept.json()["certificate_sha256"] == saved.json()["certificate_sha256"]

    company_id = uuid.UUID(headers["X-Company-ID"])
    async with async_session_factory() as session:
        stored = await session.get(CompanyHaciendaCredentialsModel, company_id)
        assert stored is not None
        for column in (
            stored.api_password_encrypted,
            stored.private_key_password_encrypted,
            stored.certificate_encrypted,
        ):
            assert API.encode() not in column
            assert PRI.encode() not in column
            assert b"CertificadoMH" not in column
        audits = (
            await session.scalars(
                select(AuditLog).where(
                    AuditLog.company_id == company_id,
                    AuditLog.resource_type == "company_hacienda_credentials",
                )
            )
        ).all()
    assert audits
    assert all(API not in str(a.after_state) and PRI not in str(a.after_state) for a in audits)

    # Sin prueba correcta no se pasa al ambiente de pruebas.
    profile = (await e2e_client.get("/api/v1/fiscal/profile", headers=headers)).json()
    blocked = await e2e_client.put(
        "/api/v1/fiscal/profile",
        json={
            "taxpayer_category": profile["taxpayer_category"],
            "person_type": profile["person_type"],
            "operating_mode": "test",
            "dte_email": "facturacion@example.com",
            "dte_phone": "2222-0000",
        },
        headers=headers,
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "fiscal_test_not_ready"

    # El servicio de este entorno admite solo simulado: la prueba falla y queda registrada.
    tested = await e2e_client.post(f"{BASE}/test", headers=headers)
    assert tested.status_code == 200, tested.text
    assert tested.json()["ok"] is False
    assert tested.json()["authentication_message"]
    after = (await e2e_client.get(BASE, headers=headers)).json()
    assert after["last_test_ok"] is False
    assert after["last_test_error"]

    removed = await e2e_client.delete(BASE, headers=headers)
    assert removed.status_code == 204
    assert (await e2e_client.get(BASE, headers=headers)).json()["configured"] is False


async def test_credentials_require_fiscal_permissions(e2e_client: AsyncClient) -> None:
    _, reader = await _login(e2e_client, superuser=False)
    assert (await e2e_client.get(BASE, headers=reader)).status_code == 403
    assert (await e2e_client.put(BASE, json={}, headers=reader)).status_code == 403
    assert (await e2e_client.post(f"{BASE}/test", headers=reader)).status_code == 403
