"""V3c: SMTP propio de la empresa (configuración, prueba y envío del DTE con él).

Mailpit hace de servidor SMTP de la empresa: el remitente con el que llega el correo prueba que se
usó la configuración de la empresa y no la del servidor.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from app.core.config import settings
from app.infrastructure.db.session import async_session_factory, session_scope
from app.infrastructure.dte_email import process_fiscal_email
from app.infrastructure.dte_worker import dte_client, object_storage
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.fiscal import CompanyEmailSettingsModel
from httpx import AsyncClient
from sqlalchemy import select

from tests.e2e.test_fiscal_settings import _login
from tests.e2e.test_sales_invoices import (
    DOCUMENTS,
    MAILPIT,
    _issued,
    _process,
    _set_customer_email,
)

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not (settings.DTE_SERVICE_URL and settings.SMTP_HOST),
        reason="Sin servicio DTE o sin Mailpit",
    ),
]

SETTINGS = "/api/v1/fiscal/email-settings"


def _body(from_address: str, **extra: object) -> dict[str, object]:
    return {
        "host": "mailpit",
        "port": 1025,
        "security": "none",
        "from_address": from_address,
        "from_name": "Pastelería Lorena",
        **extra,
    }


async def _from(address: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        found = await client.get(f"{MAILPIT}/search", params={"query": f"from:{address}"})
    found.raise_for_status()
    return list(found.json()["messages"])


async def test_settings_hide_the_password_test_and_are_audited(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    sender = f"ventas-{uuid.uuid4().hex[:8]}@lorena.example"
    empty = await e2e_client.get(SETTINGS, headers=headers)
    assert empty.status_code == 200, empty.text
    assert empty.json()["server_fallback"] is True

    saved = await e2e_client.put(
        SETTINGS,
        json=_body(sender.upper(), username="ventas", password="clave-secreta"),
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()
    assert data["configured"] is True
    assert data["from_address"] == sender
    assert data["has_password"] is True
    assert "password" not in data
    assert "clave-secreta" not in saved.text

    async with async_session_factory() as session:
        stored = await session.get(CompanyEmailSettingsModel, uuid.UUID(headers["X-Company-ID"]))
        assert stored is not None
        assert stored.password_encrypted is not None
        assert b"clave-secreta" not in stored.password_encrypted
        audits = (
            await session.scalars(
                select(AuditLog).where(AuditLog.resource_type == "company_email_settings")
            )
        ).all()
    assert audits
    assert all("clave-secreta" not in str(item.after_state) for item in audits)

    # Editar sin escribir la contraseña la conserva; Mailpit acepta sin autenticación.
    relay = await e2e_client.put(SETTINGS, json=_body(sender), headers=headers)
    assert relay.status_code == 200, relay.text
    assert relay.json()["has_password"] is False
    tested = await e2e_client.post(
        f"{SETTINGS}/test", json={"recipient": "prueba@example.com"}, headers=headers
    )
    assert tested.status_code == 200, tested.text
    assert tested.json()["ok"] is True
    [message] = await _from(sender)
    assert message["From"]["Name"] == "Pastelería Lorena"
    after = (await e2e_client.get(SETTINGS, headers=headers)).json()
    assert after["last_test_ok"] is True

    broken = await e2e_client.put(
        SETTINGS, json=_body(sender, host="smtp.invalid", port=2525), headers=headers
    )
    assert broken.json()["last_test_ok"] is None  # Cambiar la conexión invalida la prueba.
    failed = await e2e_client.post(
        f"{SETTINGS}/test", json={"recipient": "prueba@example.com"}, headers=headers
    )
    assert failed.json()["ok"] is False
    assert (await e2e_client.get(SETTINGS, headers=headers)).json()["last_test_ok"] is False

    invalid = await e2e_client.put(SETTINGS, json=_body(sender, username="ventas"), headers=headers)
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "email_settings_password_required"

    removed = await e2e_client.delete(SETTINGS, headers=headers)
    assert removed.status_code == 204
    assert (await e2e_client.get(SETTINGS, headers=headers)).json()["configured"] is False

    _, reader = await _login(e2e_client, superuser=False)
    assert (await e2e_client.put(SETTINGS, json=_body(sender), headers=reader)).status_code == 403


async def test_documents_are_sent_with_the_company_smtp(e2e_client: AsyncClient) -> None:
    admin, order, document = await _issued(e2e_client)
    sender = f"dte-{uuid.uuid4().hex[:8]}@lorena.example"
    saved = await e2e_client.put(SETTINGS, json=_body(sender), headers=admin)
    assert saved.status_code == 200, saved.text
    customer = f"cliente-{uuid.uuid4().hex[:8]}@example.com"
    await _set_customer_email(order, customer)
    await _process(document["id"])
    [auto] = (await e2e_client.get(f"{DOCUMENTS}/{document['id']}/emails", headers=admin)).json()[
        "items"
    ]
    # Sin el SMTP del servidor, igual sale por el de la empresa.
    await process_fiscal_email(
        uuid.UUID(auto["id"]),
        sender=None,
        storage=object_storage(),
        client=dte_client(),
        scope=session_scope,
    )
    [message] = await _from(sender)
    assert message["To"][0]["Address"] == customer
    assert message["From"]["Name"] == "Pastelería Lorena"
    assert message["Attachments"] == 2

    # Desactivado, el envío sin SMTP del servidor falla sin reintentar.
    off = await e2e_client.put(SETTINGS, json=_body(sender, is_enabled=False), headers=admin)
    assert off.status_code == 200, off.text
    manual = await e2e_client.post(
        f"{DOCUMENTS}/{document['id']}/emails", json={"recipients": [customer]}, headers=admin
    )
    assert manual.status_code == 202  # El servidor tiene Mailpit como respaldo.
    result = await process_fiscal_email(
        uuid.UUID(manual.json()["id"]),
        sender=None,
        storage=object_storage(),
        client=dte_client(),
        scope=session_scope,
    )
    assert result is not None
    assert result.status == "failed"
    assert result.error_code == "email_unavailable"
