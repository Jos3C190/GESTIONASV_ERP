from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.api.v1.deps import get_malware_scanner, get_object_storage
from app.core.config import settings
from app.domain.ports.malware_scanner import ScanResult
from app.domain.ports.object_storage import PresignedUpload, StoredObjectInfo
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.document_derivative import DocumentDerivativeModel
from sqlalchemy import select

from tests.e2e.conftest import get_test_company_id, seed_user

pytestmark = pytest.mark.e2e


class E2EObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.declarations: dict[str, tuple[str, dict[str, str]]] = {}

    async def ensure_bucket(self) -> None:
        return None

    async def presign_upload(
        self,
        key: str,
        *,
        content_type: str,
        metadata: dict[str, str],
        expires_seconds: int,
    ) -> PresignedUpload:
        self.declarations[key] = (content_type, metadata)
        return PresignedUpload(
            url=f"http://object-storage.test/upload/{uuid.uuid4()}",
            headers={"Content-Type": content_type},
        )

    def put(self, document_id: str, payload: bytes) -> None:
        key = next(
            key
            for key, (_content_type, metadata) in self.declarations.items()
            if metadata["document-id"] == document_id
        )
        self.objects[key] = payload

    async def presign_download(
        self,
        key: str,
        *,
        filename: str,
        content_type: str,
        expires_seconds: int,
    ) -> str:
        return f"http://object-storage.test/download/{uuid.uuid4()}?filename={filename}"

    async def head(self, key: str) -> StoredObjectInfo | None:
        if key not in self.objects:
            return None
        content_type, metadata = self.declarations[key]
        return StoredObjectInfo(
            size_bytes=len(self.objects[key]),
            content_type=content_type,
            etag="e2e-etag",
            metadata=metadata,
        )

    async def download_to(self, key: str, destination: Path, max_bytes: int) -> None:
        destination.write_bytes(self.objects[key])

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def upload_from(
        self,
        key: str,
        source: Path,
        *,
        content_type: str,
        metadata: dict[str, str],
    ) -> StoredObjectInfo:
        payload = source.read_bytes()
        self.objects[key] = payload
        self.declarations[key] = (content_type, metadata)
        return StoredObjectInfo(
            size_bytes=len(payload), content_type=content_type, etag="e2e-etag", metadata=metadata
        )

    async def health(self) -> bool:
        return True


class E2EScanner:
    def __init__(self, result: ScanResult) -> None:
        self.result = result

    async def scan(self, path: Path) -> ScanResult:
        assert path.exists()
        return self.result

    async def health(self) -> bool:
        return True


def _enable_fake_services(e2e_client, monkeypatch, scanner: E2EScanner) -> E2EObjectStorage:
    storage = E2EObjectStorage()
    monkeypatch.setattr(settings, "OBJECT_STORAGE_ENABLED", True)
    app = e2e_client._transport.app
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_malware_scanner] = lambda: scanner
    return storage


async def _headers(e2e_client, *, superuser: bool) -> dict[str, str]:
    username = "document_superadmin" if superuser else "document_user"
    password = "Strong!Document2026"
    await seed_user(
        username=username,
        email=f"{username}@example.test",
        password=password,
        is_superuser=superuser,
    )
    response = await e2e_client.post(
        "/api/v1/auth/login", json={"login": username, "password": password}
    )
    assert response.status_code == 200
    return {
        "Authorization": f"Bearer {response.json()['access_token']}",
        "X-Company-ID": str(await get_test_company_id()),
    }


def _upload_body() -> dict[str, str | int]:
    payload = b"%PDF-1.7\ntest"
    return {
        "file_name": "contrato.pdf",
        "content_type": "application/pdf",
        "size_bytes": len(payload),
        "checksum_sha256": hashlib.sha256(payload).hexdigest(),
    }


async def test_document_upload_requires_explicit_permission(e2e_client) -> None:
    response = await e2e_client.post(
        "/api/v1/documents/uploads",
        headers=await _headers(e2e_client, superuser=False),
        json=_upload_body(),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_external_deployment_fails_closed_until_storage_is_configured(
    e2e_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "OBJECT_STORAGE_ENABLED", False)
    response = await e2e_client.post(
        "/api/v1/documents/uploads",
        headers=await _headers(e2e_client, superuser=True),
        json=_upload_body(),
    )
    assert response.status_code == 503
    assert response.json()["code"] == "document_storage_unavailable"


async def test_superadmin_completes_clean_document_flow_with_audit(
    e2e_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"%PDF-1.7\nclean e2e document"
    storage = _enable_fake_services(e2e_client, monkeypatch, E2EScanner(ScanResult(clean=True)))
    headers = await _headers(e2e_client, superuser=True)
    initiated = await e2e_client.post(
        "/api/v1/documents/uploads",
        headers=headers,
        json={
            "file_name": "contrato.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(payload),
            "checksum_sha256": hashlib.sha256(payload).hexdigest(),
        },
    )
    assert initiated.status_code == 201, initiated.text
    assert "bucket" not in initiated.text
    assert "object_key" not in initiated.text
    document_id = initiated.json()["document_id"]
    storage.put(document_id, payload)

    completed = await e2e_client.post(f"/api/v1/documents/{document_id}/complete", headers=headers)
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "active"
    download = await e2e_client.post(
        f"/api/v1/documents/{document_id}/download-url", headers=headers
    )
    assert download.status_code == 200

    async with async_session_factory() as session:
        actions = set(
            (
                await session.scalars(
                    select(AuditLog.action).where(AuditLog.resource_id == document_id)
                )
            ).all()
        )
    assert {
        "DOCUMENT_UPLOAD_INITIATED",
        "DOCUMENT_ACTIVATED",
        "DOCUMENT_DOWNLOAD_URL_ISSUED",
    } <= actions


async def test_malware_cannot_be_downloaded(e2e_client, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"%PDF-1.7\nmalware simulation"
    storage = _enable_fake_services(
        e2e_client,
        monkeypatch,
        E2EScanner(ScanResult(clean=False, malware_name="Test.Signature")),
    )
    headers = await _headers(e2e_client, superuser=True)
    initiated = await e2e_client.post(
        "/api/v1/documents/uploads",
        headers=headers,
        json={
            "file_name": "infectado.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(payload),
            "checksum_sha256": hashlib.sha256(payload).hexdigest(),
        },
    )
    assert initiated.status_code == 201
    document_id = initiated.json()["document_id"]
    storage.put(document_id, payload)

    completed = await e2e_client.post(f"/api/v1/documents/{document_id}/complete", headers=headers)
    assert completed.status_code == 422
    assert completed.json()["code"] == "document_malware_detected"
    download = await e2e_client.post(
        f"/api/v1/documents/{document_id}/download-url", headers=headers
    )
    assert download.status_code == 409


async def test_pdf_is_immediately_available_then_exposes_explicit_ocr_variant(
    e2e_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"%PDF-1.7\nscanned document"
    storage = _enable_fake_services(e2e_client, monkeypatch, E2EScanner(ScanResult(clean=True)))
    monkeypatch.setattr(settings, "OCR_ENABLED", True)
    headers = await _headers(e2e_client, superuser=True)
    initiated = await e2e_client.post(
        "/api/v1/documents/uploads",
        headers=headers,
        json={
            "file_name": "escaneado.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(payload),
            "checksum_sha256": hashlib.sha256(payload).hexdigest(),
        },
    )
    assert initiated.status_code == 201
    document_id = initiated.json()["document_id"]
    storage.put(document_id, payload)

    completed = await e2e_client.post(f"/api/v1/documents/{document_id}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "active"
    assert completed.json()["ocr_status"] == "pending"
    assert completed.json()["ocr_available"] is False

    original = await e2e_client.post(
        f"/api/v1/documents/{document_id}/download-url", headers=headers
    )
    pending = await e2e_client.post(
        f"/api/v1/documents/{document_id}/download-url?variant=ocr", headers=headers
    )
    assert original.status_code == 200
    assert pending.status_code == 409
    assert pending.json()["code"] == "document_ocr_not_ready"

    async with async_session_factory() as session:
        derivative = (
            await session.execute(
                select(DocumentDerivativeModel).where(
                    DocumentDerivativeModel.document_id == uuid.UUID(document_id)
                )
            )
        ).scalar_one()
        derivative.status = "ready"
        derivative.size_bytes = len(payload)
        derivative.checksum_sha256 = hashlib.sha256(payload).hexdigest()
        derivative.etag = "ocr-e2e-etag"
        derivative.completed_at = datetime.now(UTC)
        await session.commit()

    detail = await e2e_client.get(f"/api/v1/documents/{document_id}", headers=headers)
    ocr_download = await e2e_client.post(
        f"/api/v1/documents/{document_id}/download-url?variant=ocr", headers=headers
    )
    assert detail.status_code == 200
    assert detail.json()["ocr_status"] == "ready"
    assert detail.json()["ocr_available"] is True
    assert ocr_download.status_code == 200


async def test_superadmin_can_retry_failed_ocr(e2e_client, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"%PDF-1.7\nretry OCR"
    storage = _enable_fake_services(e2e_client, monkeypatch, E2EScanner(ScanResult(clean=True)))
    monkeypatch.setattr(settings, "OCR_ENABLED", True)
    headers = await _headers(e2e_client, superuser=True)
    initiated = await e2e_client.post(
        "/api/v1/documents/uploads",
        headers=headers,
        json={
            "file_name": "retry.pdf",
            "content_type": "application/pdf",
            "size_bytes": len(payload),
            "checksum_sha256": hashlib.sha256(payload).hexdigest(),
        },
    )
    document_id = initiated.json()["document_id"]
    storage.put(document_id, payload)
    completed = await e2e_client.post(f"/api/v1/documents/{document_id}/complete", headers=headers)
    assert completed.status_code == 200

    async with async_session_factory() as session:
        derivative = (
            await session.execute(
                select(DocumentDerivativeModel).where(
                    DocumentDerivativeModel.document_id == uuid.UUID(document_id)
                )
            )
        ).scalar_one()
        derivative.status = "failed"
        derivative.failure_code = "ocr_timeout"
        derivative.attempts = 3
        await session.commit()

    retried = await e2e_client.post(f"/api/v1/documents/{document_id}/ocr/retry", headers=headers)
    assert retried.status_code == 202
    assert retried.json()["ocr_status"] == "pending"
    assert retried.json()["ocr_failure_code"] is None
