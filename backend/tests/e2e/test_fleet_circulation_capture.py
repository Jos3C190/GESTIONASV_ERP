"""Guided circulation card capture: it must belong to the vehicle, and only a person confirms."""

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
from sqlalchemy import select, update

from tests.e2e.test_documents import E2EScanner, _enable_fake_services
from tests.e2e.test_fleet_vehicles import _admin, _branch_manager, _branches, _vehicle

pytestmark = pytest.mark.e2e

JPEG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00\x01" + b"tarjeta" * 8 + b"\xff\xd9"
FUTURE = datetime.now(UTC).year + 3
VIN = "1FAKE9X7K0M123456"


@pytest.fixture
def storage(e2e_client: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    return _enable_fake_services(e2e_client, monkeypatch, E2EScanner(ScanResult(clean=True)))


async def _car(
    e2e_client: Any, admin: dict[str, str], branch: str | None = None, **overrides: Any
) -> dict[str, Any]:
    branch_id = branch or (await _branches(e2e_client, admin))[0]["id"]
    suffix = uuid.uuid4().hex[:6].upper()
    payload = {
        **_vehicle(branch_id, f"TC-{suffix}", f"P{suffix}"),
        "brand": "Mitsubishi",
        "model": "Lancer",
        "year": 2017,
        **overrides,
    }
    created = await e2e_client.post("/api/v1/fleet/vehicles", headers=admin, json=payload)
    assert created.status_code == 201, created.text
    return dict(created.json())


def _base(vehicle: dict[str, Any]) -> str:
    return f"/api/v1/fleet/vehicles/{vehicle['id']}/circulation-captures"


async def _photo(
    e2e_client: Any,
    storage: Any,
    headers: dict[str, str],
    vehicle: dict[str, Any],
    capture_id: str,
    side: str,
) -> dict[str, Any]:
    base = f"{_base(vehicle)}/{capture_id}/sides/{side}"
    started = await e2e_client.post(
        f"{base}/upload",
        headers=headers,
        json={
            "content_type": "image/jpeg",
            "size_bytes": len(JPEG),
            "checksum_sha256": hashlib.sha256(JPEG).hexdigest(),
        },
    )
    assert started.status_code == 201, started.text
    storage.put(started.json()["document_id"], JPEG)
    completed = await e2e_client.post(f"{base}/complete", headers=headers)
    assert completed.status_code == 200, completed.text
    return dict(completed.json())


async def _capture_with_photos(
    e2e_client: Any, storage: Any, headers: dict[str, str], vehicle: dict[str, Any]
) -> str:
    opened = await e2e_client.post(_base(vehicle), headers=headers)
    assert opened.status_code == 201, opened.text
    capture_id = str(opened.json()["id"])
    await _photo(e2e_client, storage, headers, vehicle, capture_id, "front")
    await _photo(e2e_client, storage, headers, vehicle, capture_id, "back")
    return capture_id


def _values(vehicle: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {
        "plate": f"{vehicle['plate']}-2007",
        "expires": f"05-{FUTURE}",
        "issued": "05-25-2026",
        "year": "2017",
        "brand": "MITSUBISHI",
        "model": "LANCER",
        "color": "NEGRO",
        "chassis": "CHS7X9A42QK881",
        "engine": "MTRZP49931FAKE",
        "vin": VIN[:-6] + uuid.uuid4().hex[:6].upper().replace("I", "1"),
        **changes,
    }


async def _confirm(
    e2e_client: Any,
    headers: dict[str, str],
    vehicle: dict[str, Any],
    capture_id: str,
    values: dict[str, Any],
    acknowledged: list[str] | None = None,
) -> Any:
    return await e2e_client.post(
        f"{_base(vehicle)}/{capture_id}/confirm",
        headers=headers,
        json={"values": values, "acknowledged_warnings": acknowledged or []},
    )


def _card_issues(vehicle: dict[str, Any]) -> list[str]:
    return [
        issue["message"]
        for issue in vehicle["compliance"]["issues"]
        if "circulación" in issue["message"].lower()
    ]


async def test_unavailable_without_document_storage(e2e_client: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(settings, "OBJECT_STORAGE_ENABLED", False)
    admin = await _admin(e2e_client)
    vehicle = await _car(e2e_client, admin)

    capabilities = await e2e_client.get(
        "/api/v1/fleet/circulation-captures/capabilities", headers=admin
    )
    opened = await e2e_client.post(_base(vehicle), headers=admin)

    assert capabilities.json() == {"enabled": False, "extraction_available": False}
    assert opened.status_code == 404
    assert opened.json()["code"] == "circulation_capture_disabled"


async def test_confirming_makes_it_the_vehicle_card(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    vehicle = await _car(e2e_client, admin)
    assert _card_issues(vehicle)
    capture_id = await _capture_with_photos(e2e_client, storage, admin, vehicle)

    # Las fotos escaneadas todavía no cuentan.
    documents = f"/api/v1/fleet/vehicles/{vehicle['id']}/documents"
    assert (await e2e_client.get(documents, headers=admin)).json()["items"] == []

    confirmed = await _confirm(e2e_client, admin, vehicle, capture_id, _values(vehicle))

    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert _card_issues(body["vehicle"]) == []
    assert set(body["filled_fields"]) == {"vin", "color", "chassis_number", "engine_number"}
    assert body["skipped_fields"] == []
    assert body["vehicle"]["chassis_number"] == "CHS7X9A42QK881"
    assert body["vehicle"]["engine_number"] == "MTRZP49931FAKE"
    assert body["vehicle"]["color"] == "NEGRO"
    items = (await e2e_client.get(documents, headers=admin)).json()["items"]
    by_category = {item["category_code"]: item for item in items}
    assert set(by_category) == {"circulation_card", "circulation_card_back"}
    assert by_category["circulation_card"]["expires_on"] == f"{FUTURE}-05-31"
    assert by_category["circulation_card"]["issued_on"] == "2026-05-25"
    assert by_category["circulation_card_back"]["expires_on"] is None

    async with async_session_factory() as session:
        capture = await session.get(DocumentCaptureModel, uuid.UUID(capture_id))
        assert capture is not None
        assert capture.status == "confirmed"
        assert capture.extracted is None
        audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.action == "CIRCULATION_CARD_CAPTURE_CONFIRMED",
                AuditLog.resource_id == vehicle["id"],
            )
        )
        assert audit is not None
        # La auditoría guarda nombres de campos, no lo impreso en el documento.
        assert "MTRZP49931FAKE" not in str(audit.after_state)


async def test_other_plate_cannot_be_confirmed_by_anyone(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    vehicle = await _car(e2e_client, admin)
    capture_id = await _capture_with_photos(e2e_client, storage, admin, vehicle)

    refused = await _confirm(
        e2e_client,
        admin,
        vehicle,
        capture_id,
        _values(vehicle, plate="ZZZ999-2007"),
        ["plate_mismatch"],
    )

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "circulation_capture_plate_mismatch"
    documents = f"/api/v1/fleet/vehicles/{vehicle['id']}/documents"
    assert (await e2e_client.get(documents, headers=admin)).json()["items"] == []


async def test_check_reports_issues_and_what_would_be_filled(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    vehicle = await _car(e2e_client, admin, color="Blanco")
    capture_id = await _capture_with_photos(e2e_client, storage, admin, vehicle)

    checked = await e2e_client.post(
        f"{_base(vehicle)}/{capture_id}/check",
        headers=admin,
        json=_values(vehicle, plate="ZZZ999"),
    )

    assert checked.status_code == 200, checked.text
    codes = {issue["code"]: issue["severity"] for issue in checked.json()["issues"]}
    assert codes == {"plate_mismatch": "error", "color_mismatch": "warning"}
    assert set(checked.json()["fills"]) == {"vin", "chassis_number", "engine_number"}


async def test_differences_warn_and_never_overwrite(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    vehicle = await _car(e2e_client, admin, color="Blanco", year=2018)
    capture_id = await _capture_with_photos(e2e_client, storage, admin, vehicle)
    values = _values(vehicle)

    unacknowledged = await _confirm(e2e_client, admin, vehicle, capture_id, values)
    assert unacknowledged.status_code == 409, unacknowledged.text
    assert unacknowledged.json()["code"] == "circulation_capture_unacknowledged"

    confirmed = await _confirm(
        e2e_client, admin, vehicle, capture_id, values, ["color_mismatch", "year_mismatch"]
    )

    assert confirmed.status_code == 200, confirmed.text
    saved = confirmed.json()["vehicle"]
    assert saved["color"] == "Blanco"
    assert saved["year"] == 2018
    assert "color" not in confirmed.json()["filled_fields"]


async def test_vin_of_another_vehicle_is_refused(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    vin = f"1FAKE9X7K0M{uuid.uuid4().int % 1000000:06d}"
    await _car(e2e_client, admin, vin=vin)
    vehicle = await _car(e2e_client, admin)
    capture_id = await _capture_with_photos(e2e_client, storage, admin, vehicle)

    refused = await _confirm(e2e_client, admin, vehicle, capture_id, _values(vehicle, vin=vin))

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "vehicle_vin_taken"
    # Nada queda a medias: la captura sigue abierta y el documento sin registrar.
    documents = f"/api/v1/fleet/vehicles/{vehicle['id']}/documents"
    assert (await e2e_client.get(documents, headers=admin)).json()["items"] == []


async def test_vehicle_without_plate_has_no_card(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    vehicle = await _car(e2e_client, admin, kind="forklift", plate="", capacity_kg=None)

    opened = await e2e_client.post(_base(vehicle), headers=admin)

    assert opened.status_code == 409, opened.text
    assert opened.json()["code"] == "circulation_capture_no_plate"


async def test_both_photos_are_required(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    vehicle = await _car(e2e_client, admin)
    opened = await e2e_client.post(_base(vehicle), headers=admin)
    capture_id = opened.json()["id"]
    await _photo(e2e_client, storage, admin, vehicle, capture_id, "front")

    refused = await _confirm(e2e_client, admin, vehicle, capture_id, _values(vehicle))

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "circulation_capture_side_missing"


async def test_capture_is_the_only_way_to_register_the_card(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    vehicle = await _car(e2e_client, admin)
    documents = f"/api/v1/fleet/vehicles/{vehicle['id']}/documents"
    categories = (await e2e_client.get(f"{documents}/categories", headers=admin)).json()
    by_code = {item["code"]: item["id"] for item in categories}
    upload = {
        "file_name": "tarjeta.pdf",
        "content_type": "application/pdf",
        "size_bytes": 1024,
        "checksum_sha256": "a" * 64,
        "expires_on": f"{FUTURE}-05-31",
    }

    for code in ("circulation_card", "circulation_card_back"):
        refused = await e2e_client.post(
            f"{documents}/uploads", headers=admin, json={**upload, "category_id": by_code[code]}
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "document_category_capture_only"

    capture_id = await _capture_with_photos(e2e_client, storage, admin, vehicle)
    confirmed = await _confirm(e2e_client, admin, vehicle, capture_id, _values(vehicle))
    assert confirmed.status_code == 200, confirmed.text
    items = (await e2e_client.get(documents, headers=admin)).json()["items"]
    card = next(item for item in items if item["category_code"] == "circulation_card")

    edited = await e2e_client.patch(
        f"{documents}/{card['id']}", headers=admin, json={"expires_on": f"{FUTURE + 9}-01-01"}
    )
    assert edited.status_code == 409, edited.text
    assert edited.json()["code"] == "document_category_capture_only"


async def test_new_capture_replaces_the_previous_card(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    vehicle = await _car(e2e_client, admin)
    documents = f"/api/v1/fleet/vehicles/{vehicle['id']}/documents"
    first = await _capture_with_photos(e2e_client, storage, admin, vehicle)
    values = _values(vehicle)
    assert (await _confirm(e2e_client, admin, vehicle, first, values)).status_code == 200

    second = await _capture_with_photos(e2e_client, storage, admin, vehicle)
    renewed = await _confirm(
        e2e_client, admin, vehicle, second, {**values, "expires": f"05-{FUTURE + 1}"}
    )

    assert second != first
    assert renewed.status_code == 200, renewed.text
    items = (await e2e_client.get(documents, headers=admin)).json()["items"]
    cards = [item for item in items if item["category_code"] == "circulation_card"]
    assert len(cards) == 1
    assert cards[0]["expires_on"] == f"{FUTURE + 1}-05-31"
    assert renewed.json()["filled_fields"] == []


async def test_branch_scope_and_permissions(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    branches = await _branches(e2e_client, admin)
    vehicle = await _car(e2e_client, admin, branch=branches[0]["id"])
    outsider = await _branch_manager(e2e_client, admin, branches[1]["id"])

    opened = await e2e_client.post(_base(vehicle), headers=outsider)

    assert opened.status_code in {403, 404}, opened.text


async def test_cancel_discards_the_capture(e2e_client: Any, storage: Any) -> None:
    admin = await _admin(e2e_client)
    vehicle = await _car(e2e_client, admin)
    capture_id = await _capture_with_photos(e2e_client, storage, admin, vehicle)

    cancelled = await e2e_client.delete(f"{_base(vehicle)}/{capture_id}", headers=admin)
    late = await _confirm(e2e_client, admin, vehicle, capture_id, _values(vehicle))

    assert cancelled.status_code == 204, cancelled.text
    assert late.status_code == 409, late.text
    assert late.json()["code"] == "circulation_capture_closed"


async def test_extracted_values_reach_the_review_without_the_owner(
    e2e_client: Any, storage: Any
) -> None:
    admin = await _admin(e2e_client)
    vehicle = await _car(e2e_client, admin)
    capture_id = await _capture_with_photos(e2e_client, storage, admin, vehicle)
    async with async_session_factory() as session:
        await session.execute(
            update(DocumentCaptureModel)
            .where(DocumentCaptureModel.id == uuid.UUID(capture_id))
            .values(
                status="ready",
                extracted={
                    "front": {
                        "document_id": "x",
                        "values": {
                            "placa": f"{vehicle['plate']}-2007",
                            "vto": f"VTO 05-{FUTURE}",
                            "emision": "05-25-2026",
                        },
                    },
                    "back": {
                        "document_id": "y",
                        "values": {"anio": "2017", "marca": "TOYOTA", "vin": "1FAKE9X7K0M123456,"},
                    },
                },
            )
        )
        await session.commit()

    read = await e2e_client.get(f"{_base(vehicle)}/{capture_id}", headers=admin)

    assert read.status_code == 200, read.text
    body = read.json()
    assert body["values"]["expires"] == f"05-{FUTURE}"
    assert body["values"]["vin"] == "1FAKE9X7K0M123456"
    assert {issue["code"] for issue in body["issues"]} == {"brand_mismatch"}
    assert "vin" in body["fills"]
    assert "owner" not in body["values"]
