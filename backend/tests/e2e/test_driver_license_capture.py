"""Guided license capture: nothing counts until a person confirms it."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from app.core.config import settings
from app.domain.ports.malware_scanner import ScanResult
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.document_capture import DocumentCaptureModel
from app.infrastructure.models.employee import Employee
from sqlalchemy import select, update

from tests.e2e.test_documents import E2EScanner, _enable_fake_services
from tests.e2e.test_fleet_drivers import _employee
from tests.e2e.test_fleet_vehicles import _admin, _branch_manager, _branches

pytestmark = pytest.mark.e2e

JPEG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00\x01" + b"licencia" * 8 + b"\xff\xd9"
FUTURE = datetime.now(UTC).year + 3


@pytest.fixture
def storage(e2e_client: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(settings, "LICENSE_CAPTURE_ENABLED", True)
    return _enable_fake_services(e2e_client, monkeypatch, E2EScanner(ScanResult(clean=True)))


async def _driver(e2e_client: Any, admin: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    branch = (await _branches(e2e_client, admin))[0]["id"]
    employee = await _employee(e2e_client, admin, branch)
    created = await e2e_client.post(
        "/api/v1/drivers",
        headers=admin,
        json={"employee_id": employee["id"], "branch_id": branch, "license_class": "liviana"},
    )
    assert created.status_code == 201, created.text
    return created.json(), employee


async def _photo(
    e2e_client: Any,
    storage: Any,
    admin: dict[str, str],
    driver_id: str,
    capture_id: str,
    side: str,
    payload: bytes = JPEG,
) -> dict[str, Any]:
    base = f"/api/v1/drivers/{driver_id}/license-captures/{capture_id}/sides/{side}"
    started = await e2e_client.post(
        f"{base}/upload",
        headers=admin,
        json={
            "content_type": "image/jpeg",
            "size_bytes": len(payload),
            "checksum_sha256": hashlib.sha256(payload).hexdigest(),
        },
    )
    assert started.status_code == 201, started.text
    storage.put(started.json()["document_id"], payload)
    completed = await e2e_client.post(f"{base}/complete", headers=admin)
    assert completed.status_code == 200, completed.text
    return dict(completed.json())


async def _capture_with_photos(
    e2e_client: Any, storage: Any, admin: dict[str, str], driver_id: str
) -> str:
    opened = await e2e_client.post(f"/api/v1/drivers/{driver_id}/license-captures", headers=admin)
    assert opened.status_code == 201, opened.text
    capture_id = opened.json()["id"]
    await _photo(e2e_client, storage, admin, driver_id, capture_id, "front")
    await _photo(e2e_client, storage, admin, driver_id, capture_id, "back", JPEG + b"")
    return str(capture_id)


def _values(employee: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {
        "license_class": "D LIVIANA",
        "expires": f"02-{FUTURE}",
        "number": "0101-010101-101-1",
        "surnames": employee["last_name"],
        "given_names": employee["first_name"],
        "dui": "12345678-4",
        "issued": "25.02.2023",
        "birth": None,
        "control_number": "LD-000000001",
        **changes,
    }


NO_DUI_ON_FILE = ["dui_not_registered"]


async def test_feature_is_hidden_until_enabled(e2e_client: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(settings, "LICENSE_CAPTURE_ENABLED", False)
    admin = await _admin(e2e_client)
    driver, _ = await _driver(e2e_client, admin)

    capabilities = await e2e_client.get(
        "/api/v1/drivers/license-captures/capabilities", headers=admin
    )
    opened = await e2e_client.post(
        f"/api/v1/drivers/{driver['id']}/license-captures", headers=admin
    )

    assert capabilities.status_code == 200, capabilities.text
    assert capabilities.json() == {"enabled": False, "extraction_available": False}
    assert opened.status_code == 404
    assert opened.json()["code"] == "license_capture_disabled"


async def test_confirming_turns_photos_into_the_current_license(
    e2e_client: Any, storage: Any
) -> None:
    admin = await _admin(e2e_client)
    driver, employee = await _driver(e2e_client, admin)
    capture_id = await _capture_with_photos(e2e_client, storage, admin, driver["id"])

    # Las fotos escaneadas todavía no cuentan: sigue sin licencia.
    before = (await e2e_client.get(f"/api/v1/drivers/{driver['id']}", headers=admin)).json()
    assert before["license"]["document_id"] is None
    assert before["compliance"]["state"] == "blocked"
    listed = await e2e_client.get(f"/api/v1/drivers/{driver['id']}/documents", headers=admin)
    assert listed.json()["items"] == []

    confirmed = await e2e_client.post(
        f"/api/v1/drivers/{driver['id']}/license-captures/{capture_id}/confirm",
        headers=admin,
        json={"values": _values(employee), "acknowledged_warnings": NO_DUI_ON_FILE},
    )

    assert confirmed.status_code == 200, confirmed.text
    license_view = confirmed.json()["license"]
    assert license_view["number"] == "0101-010101-101-1"
    assert license_view["expires_on"] == f"{FUTURE}-02-{28 if FUTURE % 4 else 29}"
    assert license_view["document_id"] is not None
    # El reverso no aparece en el expediente de Conductores: trae datos de salud.
    listed = await e2e_client.get(f"/api/v1/drivers/{driver['id']}/documents", headers=admin)
    assert [item["id"] for item in listed.json()["items"]] == [license_view["document_id"]]
    back = await e2e_client.post(
        f"/api/v1/drivers/{driver['id']}/license-back/preview-url", headers=admin
    )
    assert back.status_code == 200, back.text

    async with async_session_factory() as session:
        capture = await session.get(DocumentCaptureModel, uuid.UUID(capture_id))
        audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.action == "DRIVER_LICENSE_CAPTURE_CONFIRMED",
                AuditLog.resource_id == driver["id"],
            )
        )
    assert capture is not None
    assert capture.status == "confirmed"
    assert capture.extracted is None
    assert audit is not None
    # La auditoría guarda ids y nombres de campos, nunca los valores de la licencia.
    assert "0101-010101-101-1" not in str(audit.after_state)
    assert "12345678-4" not in str(audit.after_state)

    closed = await e2e_client.delete(
        f"/api/v1/drivers/{driver['id']}/license-captures/{capture_id}", headers=admin
    )
    assert closed.status_code == 409
    assert closed.json()["code"] == "license_capture_closed"


async def test_new_license_replaces_one_with_a_later_expiry(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    driver, employee = await _driver(e2e_client, admin)
    first = await _capture_with_photos(e2e_client, storage, admin, driver["id"])
    await e2e_client.post(
        f"/api/v1/drivers/{driver['id']}/license-captures/{first}/confirm",
        headers=admin,
        json={
            "values": _values(employee, expires=f"12-{FUTURE + 5}", number="0101-010101-101-9"),
            "acknowledged_warnings": NO_DUI_ON_FILE,
        },
    )
    second = await _capture_with_photos(e2e_client, storage, admin, driver["id"])

    confirmed = await e2e_client.post(
        f"/api/v1/drivers/{driver['id']}/license-captures/{second}/confirm",
        headers=admin,
        json={"values": _values(employee), "acknowledged_warnings": NO_DUI_ON_FILE},
    )

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["license"]["number"] == "0101-010101-101-1"
    assert confirmed.json()["license"]["expires_on"].startswith(f"{FUTURE}-02")


async def test_both_sides_and_valid_values_are_required(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    driver, employee = await _driver(e2e_client, admin)
    opened = await e2e_client.post(
        f"/api/v1/drivers/{driver['id']}/license-captures", headers=admin
    )
    capture_id = opened.json()["id"]
    await _photo(e2e_client, storage, admin, driver["id"], capture_id, "front")
    confirm = f"/api/v1/drivers/{driver['id']}/license-captures/{capture_id}/confirm"

    missing_back = await e2e_client.post(
        confirm,
        headers=admin,
        json={"values": _values(employee), "acknowledged_warnings": NO_DUI_ON_FILE},
    )
    assert missing_back.status_code == 409
    assert missing_back.json()["code"] == "license_capture_side_missing"

    await _photo(e2e_client, storage, admin, driver["id"], capture_id, "back")
    invalid = await e2e_client.post(
        confirm,
        headers=admin,
        json={"values": _values(employee, expires="Expires")},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "license_capture_invalid"

    unacknowledged = await e2e_client.post(
        confirm, headers=admin, json={"values": _values(employee)}
    )
    assert unacknowledged.status_code == 409
    assert unacknowledged.json()["code"] == "license_capture_unacknowledged"


async def test_mismatch_needs_override_permission_and_reason(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    driver, employee = await _driver(e2e_client, admin)
    async with async_session_factory() as session:
        await session.execute(
            update(Employee)
            .where(Employee.id == uuid.UUID(employee["id"]))
            .values(document_id="20000001-0")
        )
        await session.commit()
    capture_id = await _capture_with_photos(e2e_client, storage, admin, driver["id"])
    confirm = f"/api/v1/drivers/{driver['id']}/license-captures/{capture_id}/confirm"

    no_reason = await e2e_client.post(confirm, headers=admin, json={"values": _values(employee)})
    assert no_reason.status_code == 422
    assert no_reason.json()["code"] == "license_capture_reason_required"

    manager = await _branch_manager(e2e_client, admin, driver["branch_id"])
    denied = await e2e_client.post(
        confirm,
        headers=manager,
        json={"values": _values(employee), "override_reason": "Error en expediente"},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "license_capture_override_required"

    allowed = await e2e_client.post(
        confirm,
        headers=admin,
        json={"values": _values(employee), "override_reason": "Error en expediente"},
    )
    assert allowed.status_code == 200, allowed.text


async def test_retaking_a_photo_discards_the_previous_one(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    driver, _ = await _driver(e2e_client, admin)
    opened = await e2e_client.post(
        f"/api/v1/drivers/{driver['id']}/license-captures", headers=admin
    )
    capture_id = opened.json()["id"]
    first = await _photo(e2e_client, storage, admin, driver["id"], capture_id, "front")

    second = await _photo(e2e_client, storage, admin, driver["id"], capture_id, "front", JPEG * 2)

    assert second["front"]["document_id"] != first["front"]["document_id"]
    assert len(storage.objects) == 1
    resumed = await e2e_client.post(
        f"/api/v1/drivers/{driver['id']}/license-captures", headers=admin
    )
    assert resumed.json()["id"] == capture_id


async def test_capture_requires_permission_and_scope(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    branches = await _branches(e2e_client, admin)
    other_employee = await _employee(e2e_client, admin, branches[1]["id"])
    foreign = (
        await e2e_client.post(
            "/api/v1/drivers",
            headers=admin,
            json={
                "employee_id": other_employee["id"],
                "branch_id": branches[1]["id"],
                "license_class": "liviana",
            },
        )
    ).json()
    manager = await _branch_manager(e2e_client, admin, branches[0]["id"])

    reached = await e2e_client.post(
        f"/api/v1/drivers/{foreign['id']}/license-captures", headers=manager
    )

    assert reached.status_code == 404
