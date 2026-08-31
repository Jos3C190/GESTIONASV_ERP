from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from app.application.audit.audit_service import AuditService
from app.application.documents.service import DocumentService
from app.core.config import Settings
from app.core.exceptions import ConflictError
from app.domain.entities.document import DocumentAsset
from app.domain.entities.document_derivative import DocumentDerivative

from tests.unit.test_document_storage import (
    FakeAuditRepository,
    FakeDocumentRepository,
    FakeObjectStorage,
    FakeScanner,
)


class FakeDerivativeRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, DocumentDerivative] = {}
        self.ensure_calls = 0

    async def ensure_ocr(
        self,
        *,
        derivative_id: uuid.UUID,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        bucket: str,
        object_key: str,
    ) -> DocumentDerivative:
        existing = await self.get_ocr(document_id)
        if existing is not None:
            return existing
        self.ensure_calls += 1
        derivative = DocumentDerivative(
            id=derivative_id,
            company_id=company_id,
            document_id=document_id,
            kind="ocr_pdf",
            status="pending",
            bucket=bucket,
            object_key=object_key,
        )
        self.items[derivative.id] = derivative
        return derivative

    async def get(self, derivative_id: uuid.UUID) -> DocumentDerivative | None:
        return self.items.get(derivative_id)

    async def get_ocr(self, document_id: uuid.UUID) -> DocumentDerivative | None:
        return next((item for item in self.items.values() if item.document_id == document_id), None)

    async def list_ocr(self, document_ids: Sequence[uuid.UUID]) -> Sequence[DocumentDerivative]:
        return [item for item in self.items.values() if item.document_id in document_ids]

    async def list_pending_ids(self, limit: int) -> Sequence[uuid.UUID]:
        return [item.id for item in self.items.values() if item.status == "pending"][:limit]

    async def claim(self, derivative_id: uuid.UUID, now: datetime) -> DocumentDerivative | None:
        derivative = self.items.get(derivative_id)
        if derivative is None or derivative.status != "pending":
            return None
        derivative.status = "processing"
        derivative.started_at = now
        derivative.attempts += 1
        return derivative

    async def save(self, derivative: DocumentDerivative) -> DocumentDerivative:
        self.items[derivative.id] = derivative
        return derivative

    async def reset_for_retry(self, derivative_id: uuid.UUID) -> DocumentDerivative | None:
        derivative = self.items.get(derivative_id)
        if derivative is None or derivative.status != "failed":
            return None
        derivative.status = "pending"
        derivative.failure_code = None
        derivative.attempts = 0
        derivative.completed_at = None
        return derivative

    async def reset_stale(self, before: datetime) -> int:
        reset = 0
        for derivative in self.items.values():
            if (
                derivative.status == "processing"
                and derivative.started_at is not None
                and derivative.started_at < before
            ):
                derivative.status = "pending"
                derivative.started_at = None
                reset += 1
        return reset


def make_ocr_service() -> tuple[
    DocumentService,
    FakeDocumentRepository,
    FakeObjectStorage,
    FakeDerivativeRepository,
    FakeAuditRepository,
]:
    documents = FakeDocumentRepository()
    storage = FakeObjectStorage()
    derivatives = FakeDerivativeRepository()
    audit = FakeAuditRepository()
    config = Settings(
        ENVIRONMENT="test",
        OBJECT_STORAGE_ENABLED=True,
        OBJECT_STORAGE_ACCESS_KEY="test-access-key",
        OBJECT_STORAGE_SECRET_KEY="test-secret-key",
        REDIS_ENABLED=True,
        REDIS_URL="redis://localhost:6379/0",
        OCR_ENABLED=True,
    )
    service = DocumentService(
        documents,
        storage,
        FakeScanner(),
        AuditService(audit),
        config,
        derivatives,
    )
    return service, documents, storage, derivatives, audit


async def add_active_document(
    repository: FakeDocumentRepository, *, extension: str = ".pdf"
) -> DocumentAsset:
    document = DocumentAsset(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        original_filename=f"manual{extension}",
        extension=extension,
        declared_content_type="application/pdf" if extension == ".pdf" else "text/plain",
        detected_content_type="application/pdf" if extension == ".pdf" else "text/plain",
        size_bytes=20,
        checksum_sha256="a" * 64,
        bucket="erp-documents",
        object_key=f"objects/{uuid.uuid4().hex}",
        status="active",
        scanned_at=datetime.now(UTC),
    )
    return await repository.add(document)


@pytest.mark.asyncio
async def test_active_pdf_creates_one_idempotent_pending_derivative() -> None:
    service, documents, _storage, derivatives, audit = make_ocr_service()
    document = await add_active_document(documents)
    actor_id = uuid.uuid4()

    first = await service.complete(document.company_id, document.id, actor_id)
    second = await service.complete(document.company_id, document.id, actor_id)

    assert first.ocr_status == second.ocr_status == "pending"
    assert not first.ocr_available
    assert derivatives.ensure_calls == 1
    assert [entry.action for entry in audit.items] == ["DOCUMENT_OCR_QUEUED"]
    derivative = await derivatives.get_ocr(document.id)
    assert derivative is not None
    assert derivative.object_key.startswith(
        f"companies/{document.company_id}/documents/{document.id}/derivatives/ocr/"
    )
    assert document.original_filename not in derivative.object_key


@pytest.mark.asyncio
async def test_non_pdf_does_not_create_ocr_work() -> None:
    service, documents, _storage, derivatives, _audit = make_ocr_service()
    document = await add_active_document(documents, extension=".txt")

    result = await service.complete(document.company_id, document.id, uuid.uuid4())

    assert result.ocr_status is None
    assert derivatives.ensure_calls == 0


@pytest.mark.asyncio
async def test_original_remains_default_and_ocr_requires_ready_derivative() -> None:
    service, documents, _storage, derivatives, audit = make_ocr_service()
    document = await add_active_document(documents)
    actor_id = uuid.uuid4()
    await service.complete(document.company_id, document.id, actor_id)

    original_url, _ = await service.download_url(document.company_id, document.id, actor_id)
    assert document.object_key in original_url
    with pytest.raises(ConflictError) as pending:
        await service.download_url(document.company_id, document.id, actor_id, variant="ocr")
    assert pending.value.code == "document_ocr_not_ready"

    derivative = await derivatives.get_ocr(document.id)
    assert derivative is not None
    derivative.status = "ready"
    derivative.size_bytes = 30
    derivative.checksum_sha256 = "b" * 64
    derivative.completed_at = datetime.now(UTC)
    ocr_url, _ = await service.download_url(
        document.company_id, document.id, actor_id, variant="ocr"
    )

    assert derivative.object_key in ocr_url
    assert "download=manual-ocr.pdf" in ocr_url
    assert [entry.action for entry in audit.items][-2:] == [
        "DOCUMENT_DOWNLOAD_URL_ISSUED",
        "DOCUMENT_OCR_DOWNLOAD_URL_ISSUED",
    ]


@pytest.mark.asyncio
async def test_manual_retry_is_limited_to_failed_ocr() -> None:
    service, documents, _storage, derivatives, audit = make_ocr_service()
    document = await add_active_document(documents)
    actor_id = uuid.uuid4()
    await service.complete(document.company_id, document.id, actor_id)
    derivative = await derivatives.get_ocr(document.id)
    assert derivative is not None

    with pytest.raises(ConflictError) as pending:
        await service.retry_ocr(document.company_id, document.id, actor_id)
    assert pending.value.code == "document_ocr_retry_not_allowed"

    derivative.status = "failed"
    derivative.failure_code = "ocr_timeout"
    derivative.attempts = 3
    retried = await service.retry_ocr(document.company_id, document.id, actor_id)

    assert retried.ocr_status == "pending"
    assert retried.ocr_failure_code is None
    assert derivative.attempts == 0
    assert [entry.action for entry in audit.items][-1] == "DOCUMENT_OCR_RETRY_REQUESTED"
