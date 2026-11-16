"""API de protección de datos: aviso, consentimientos, solicitudes, anonimizado y vulneraciones."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.application.privacy.use_cases import today_in_el_salvador
from app.domain.entities.privacy import NOTICE_ELEMENTS, add_business_days
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.organization import Company, UserCompany
from httpx import AsyncClient
from sqlalchemy import func, select

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e

PASSWORD = "Strong!Passw0rd2026"


async def _login(client: AsyncClient, *, superuser: bool) -> tuple[str, dict[str, str]]:
    username = f"privacidad-{uuid.uuid4().hex[:8]}"
    user_id = await seed_user(
        username=username,
        email=f"{username}@example.com",
        password=PASSWORD,
        is_superuser=superuser,
    )
    login = await client.post("/api/v1/auth/login", json={"login": username, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return user_id, {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Company-ID": str(await get_test_company_id()),
    }


async def _publish(client: AsyncClient, headers: dict[str, str]) -> dict[str, object]:
    template = await client.get("/api/v1/privacy/notice-template", headers=headers)
    assert template.status_code == 200, template.text
    published = await client.post(
        "/api/v1/privacy/notices",
        json={
            "title": "Aviso de privacidad",
            "body": template.json()["body"],
            "covered_elements": list(NOTICE_ELEMENTS),
        },
        headers=headers,
    )
    assert published.status_code == 201, published.text
    return published.json()


async def _customer(client: AsyncClient, headers: dict[str, str]) -> str:
    created = await client.post(
        "/api/v1/customers",
        json={
            "name": "Ana Lucía Pérez",
            "document_type": "13",
            "document_number": "00000099-9",
            "email": "ana@example.com",
            "phone": "7000-0000",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    customer_id = created.json()["id"]
    address = await client.post(
        f"/api/v1/customers/{customer_id}/delivery-addresses",
        json={"label": "Casa", "address_line": "Colonia Ficticia 1"},
        headers=headers,
    )
    assert address.status_code == 201, address.text
    return str(customer_id)


async def test_notice_versions_and_consents(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    customer_id = await _customer(e2e_client, headers)
    consents = f"/api/v1/customers/{customer_id}/consents"
    without_notice = await e2e_client.post(
        consents, json={"purpose": "marketing", "channel": "in_person"}, headers=headers
    )
    assert without_notice.status_code == 422
    assert without_notice.json()["code"] == "privacy_notice_missing"

    incomplete = await e2e_client.post(
        "/api/v1/privacy/notices",
        json={"title": "Aviso", "body": "x" * 300, "covered_elements": ["cookies"]},
        headers=headers,
    )
    assert incomplete.json()["code"] == "privacy_notice_incomplete"
    first = await _publish(e2e_client, headers)
    second = await _publish(e2e_client, headers)
    assert (first["version"], second["version"]) == (1, 2)
    current = await e2e_client.get("/api/v1/privacy/notice", headers=headers)
    assert current.json()["version"] == 2

    granted = await e2e_client.post(
        consents, json={"purpose": "marketing", "channel": "in_person"}, headers=headers
    )
    assert granted.status_code == 201, granted.text
    assert granted.json()["notice_version"] == 2
    duplicate = await e2e_client.post(
        consents, json={"purpose": "marketing", "channel": "email"}, headers=headers
    )
    assert duplicate.status_code == 409
    revoked = await e2e_client.post(
        f"{consents}/{granted.json()['id']}/revoke", json={"channel": "phone"}, headers=headers
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    again = await e2e_client.post(
        f"{consents}/{granted.json()['id']}/revoke", json={"channel": "phone"}, headers=headers
    )
    assert again.json()["code"] == "privacy_consent_already_revoked"


async def test_request_lifecycle_export_and_anonymization(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    customer_id = await _customer(e2e_client, headers)
    today = today_in_el_salvador()
    created = await e2e_client.post(
        "/api/v1/privacy/requests",
        json={
            "customer_id": customer_id,
            "requester_name": "Ana Lucía Pérez",
            "requester_document": "00000099-9",
            "response_channel": "ana@example.com",
            "right_type": "erasure",
            "description": "Quiero que borren mis datos.",
            "received_on": today.isoformat(),
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    request = created.json()
    assert request["code"] == "SOL-00001"
    assert request["due_on"] == add_business_days(today, 20).isoformat()
    actions = f"/api/v1/privacy/requests/{request['id']}/actions"

    no_reason = await e2e_client.post(actions, json={"action": "extend"}, headers=headers)
    assert no_reason.json()["code"] == "privacy_request_extension_reason_required"
    extended = await e2e_client.post(
        actions,
        json={"action": "extend", "extension_reason": "Revisión de documentos en sucursales."},
        headers=headers,
    )
    assert extended.json()["status"] == "extended"
    assert extended.json()["effective_due_on"] > request["due_on"]

    exported = await e2e_client.get(
        f"/api/v1/privacy/customers/{customer_id}/export", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert exported.json()["customer"]["email"] == "ana@example.com"
    assert exported.json()["delivery_addresses"][0]["label"] == "Casa"

    anonymize = f"/api/v1/privacy/customers/{customer_id}/anonymize"
    done = await e2e_client.post(anonymize, json={"request_id": request["id"]}, headers=headers)
    assert done.status_code == 204, done.text
    customer = (await e2e_client.get(f"/api/v1/customers/{customer_id}", headers=headers)).json()
    assert customer["name"].startswith("Titular anonimizado")
    assert customer["anonymized_at"] is not None
    assert customer["is_active"] is False
    assert (customer["document_number"], customer["email"], customer["delivery_addresses"]) == (
        None,
        None,
        [],
    )
    locked = await e2e_client.patch(
        f"/api/v1/customers/{customer_id}/status", json={"is_active": True}, headers=headers
    )
    assert locked.json()["code"] == "customer_anonymized_locked"
    twice = await e2e_client.post(anonymize, json={"request_id": request["id"]}, headers=headers)
    assert twice.status_code == 409

    resolved = await e2e_client.post(
        actions,
        json={"action": "resolve", "text": "Se anonimizaron los datos del cliente."},
        headers=headers,
    )
    assert resolved.json()["status"] == "resolved"
    open_requests = await e2e_client.get("/api/v1/privacy/requests", headers=headers)
    assert open_requests.json() == []
    closed = await e2e_client.get(
        "/api/v1/privacy/requests", params={"scope": "closed"}, headers=headers
    )
    assert [r["code"] for r in closed.json()] == ["SOL-00001"]
    company_id = uuid.UUID(headers["X-Company-ID"])
    async with async_session_factory() as session:
        anonymized_events = await session.scalar(
            select(func.count()).where(
                AuditLog.company_id == company_id, AuditLog.action == "ANONYMIZE"
            )
        )
    assert anonymized_events == 1


async def test_anonymization_needs_an_erasure_request(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    customer_id = await _customer(e2e_client, headers)
    access = await e2e_client.post(
        "/api/v1/privacy/requests",
        json={
            "customer_id": customer_id,
            "requester_name": "Ana Lucía Pérez",
            "response_channel": "ana@example.com",
            "right_type": "access",
            "description": "Quiero ver mis datos.",
            "received_on": today_in_el_salvador().isoformat(),
        },
        headers=headers,
    )
    response = await e2e_client.post(
        f"/api/v1/privacy/customers/{customer_id}/anonymize",
        json={"request_id": access.json()["id"]},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "privacy_erasure_request_required"


async def test_incident_closes_only_after_notifications(e2e_client: AsyncClient) -> None:
    _, headers = await _login(e2e_client, superuser=True)
    discovered = datetime.now(UTC) - timedelta(hours=2)
    base = {
        "discovered_at": discovered.isoformat(),
        "description": "Se envió por error una lista de clientes a un tercero.",
        "data_categories": "Nombres y correos",
        "affected_count": 40,
    }
    created = await e2e_client.post("/api/v1/privacy/incidents", json=base, headers=headers)
    assert created.status_code == 201, created.text
    incident = created.json()
    assert incident["code"] == "INC-00001"
    deadline = datetime.fromisoformat(incident["notification_deadline"])
    assert deadline - datetime.fromisoformat(incident["discovered_at"]) == timedelta(hours=72)
    url = f"/api/v1/privacy/incidents/{incident['id']}"
    early = await e2e_client.post(f"{url}/close", headers=headers)
    assert early.json()["code"] == "privacy_incident_notifications_missing"
    now = datetime.now(UTC).isoformat()
    notified = await e2e_client.put(
        url,
        json={
            **base,
            "notified_ace_at": now,
            "ace_reference": "Correo a la ACE",
            "notified_prosecutor_at": now,
            "notified_subjects_at": now,
        },
        headers=headers,
    )
    assert notified.status_code == 200, notified.text
    closed = await e2e_client.post(f"{url}/close", headers=headers)
    assert closed.json()["status"] == "closed"
    frozen = await e2e_client.put(url, json=base, headers=headers)
    assert frozen.json()["code"] == "privacy_incident_closed"


async def test_privacy_is_isolated_and_protected(e2e_client: AsyncClient) -> None:
    user_id, headers = await _login(e2e_client, superuser=True)
    created = await e2e_client.post(
        "/api/v1/privacy/requests",
        json={
            "requester_name": "Persona sin ficha",
            "response_channel": "persona@example.com",
            "right_type": "access",
            "description": "Quiero saber si tienen mis datos.",
            "received_on": today_in_el_salvador().isoformat(),
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    async with async_session_factory() as session:
        original = await session.get(Company, uuid.UUID(headers["X-Company-ID"]))
        assert original is not None
        suffix = uuid.uuid4().hex[:8]
        other = Company(
            name=f"Otra {suffix}, S.A. de C.V.",
            commercial_name=f"Otra {suffix}",
            nit=f"{uuid.uuid4().int % 10**14:014d}",
            nrc=f"{uuid.uuid4().int % 10**6:06d}",
            address="Aislada",
            department_id=original.department_id,
            municipality_id=original.municipality_id,
            district_id=original.district_id,
        )
        session.add(other)
        await session.flush()
        session.add(UserCompany(user_id=uuid.UUID(user_id), company_id=other.id))
        await session.commit()
        other_id = other.id
    other_headers = {**headers, "X-Company-ID": str(other_id)}
    foreign = await e2e_client.get(
        f"/api/v1/privacy/requests/{created.json()['id']}", headers=other_headers
    )
    assert foreign.status_code == 404
    assert (await e2e_client.get("/api/v1/privacy/requests", headers=other_headers)).json() == []

    _, plain = await _login(e2e_client, superuser=False)
    assert (await e2e_client.get("/api/v1/privacy/requests", headers=plain)).status_code == 403
    assert (await e2e_client.get("/api/v1/privacy/incidents", headers=plain)).status_code == 403
