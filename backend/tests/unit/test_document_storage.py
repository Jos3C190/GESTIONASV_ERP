from __future__ import annotations

import hashlib
import uuid
import zipfile
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pytest
from app.application.audit.audit_service import AuditService
from app.application.documents.service import (
    DocumentService,
    InitiateDocumentInput,
    _validate_zip_entry,
    inspect_document,
    normalize_filename,
    validate_declaration,
)
from app.core.config import Settings
from app.core.exceptions import (
    ConflictError,
    InfrastructureError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from app.domain.entities.audit import AuditLog
from app.domain.entities.document import DocumentAsset
from app.domain.ports.malware_scanner import ScanResult
from app.domain.ports.object_storage import PresignedUpload, StoredObjectInfo


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, DocumentAsset] = {}

    async def add(self, document: DocumentAsset) -> DocumentAsset:
        self.items[document.id] = document
        return document

    async def get(
        self, document_id: uuid.UUID, *, include_deleted: bool = False
    ) -> DocumentAsset | None:
        document = self.items.get(document_id)
        if document is not None and document.deleted_at is not None and not include_deleted:
            return None
        return document

    async def save(self, document: DocumentAsset) -> DocumentAsset:
        self.items[document.id] = document
        return document

    async def list(
        self,
        company_id: uuid.UUID,
        *,
        page: int,
        size: int,
        search: str | None,
        status: str | None,
    ) -> tuple[Sequence[DocumentAsset], int]:
        result = [item for item in self.items.values() if item.company_id == company_id]
        if search:
            result = [
                item for item in result if search.casefold() in item.original_filename.casefold()
            ]
        if status:
            result = [item for item in result if item.status == status]
        return result[(page - 1) * size : page * size], len(result)

    async def count_pending(self, user_id: uuid.UUID) -> int:
        return sum(
            item.uploaded_by == user_id
            and item.status in {"pending_upload", "pending_scan", "scanning"}
            for item in self.items.values()
        )

    async def claim_for_scan(self, document_id: uuid.UUID, now: datetime) -> DocumentAsset | None:
        document = self.items[document_id]
        if document.status not in {"pending_upload", "pending_scan"}:
            return None
        document.status = "scanning"
        document.scan_started_at = now
        return document


class FakeObjectStorage:
    def __init__(self) -> None:
        self.payloads: dict[str, bytes] = {}
        self.declarations: dict[str, tuple[str, dict[str, str]]] = {}
        self.deleted: list[str] = []

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
            url=f"http://storage.local/erp-documents/{key}?signed=1",
            headers={
                "Content-Type": content_type,
                **{f"x-amz-meta-{name}": value for name, value in metadata.items()},
            },
        )

    async def presign_download(
        self,
        key: str,
        *,
        filename: str,
        content_type: str,
        expires_seconds: int,
    ) -> str:
        return f"http://storage.local/erp-documents/{key}?download={filename}"

    async def presign_preview(
        self,
        key: str,
        *,
        filename: str,
        content_type: str,
        expires_seconds: int,
    ) -> str:
        return f"http://storage.local/erp-documents/{key}?preview={filename}"

    async def head(self, key: str) -> StoredObjectInfo | None:
        payload = self.payloads.get(key)
        declaration = self.declarations.get(key)
        if payload is None or declaration is None:
            return None
        content_type, metadata = declaration
        return StoredObjectInfo(
            size_bytes=len(payload),
            content_type=content_type,
            etag="test-etag",
            metadata=metadata,
        )

    async def download_to(self, key: str, destination: Path, max_bytes: int) -> None:
        payload = self.payloads[key]
        if len(payload) > max_bytes:
            raise ValidationError(code="document_size_invalid")
        destination.write_bytes(payload)

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.payloads.pop(key, None)

    async def health(self) -> bool:
        return True


class FakeScanner:
    def __init__(self, result: ScanResult | None = None, *, unavailable: bool = False) -> None:
        self.result = result or ScanResult(clean=True)
        self.unavailable = unavailable
        self.calls = 0

    async def scan(self, path: Path) -> ScanResult:
        self.calls += 1
        if self.unavailable:
            raise InfrastructureError(code="document_scanner_unavailable")
        assert path.stat().st_size > 0
        return self.result

    async def health(self) -> bool:
        return not self.unavailable


class FakeAuditRepository:
    def __init__(self) -> None:
        self.items: list[AuditLog] = []

    async def add(self, entry: AuditLog) -> AuditLog:
        self.items.append(entry)
        return entry


def make_service(
    *, scanner: FakeScanner | None = None, max_pending: int = 20
) -> tuple[
    DocumentService, FakeDocumentRepository, FakeObjectStorage, FakeScanner, FakeAuditRepository
]:
    repository = FakeDocumentRepository()
    storage = FakeObjectStorage()
    selected_scanner = scanner or FakeScanner()
    audit_repository = FakeAuditRepository()
    settings = Settings(
        ENVIRONMENT="test",
        OBJECT_STORAGE_ENABLED=True,
        OBJECT_STORAGE_ACCESS_KEY="test-access-key",
        OBJECT_STORAGE_SECRET_KEY="test-secret-key",
        DOCUMENT_MAX_PENDING_PER_USER=max_pending,
    )
    service = DocumentService(
        repository, storage, selected_scanner, AuditService(audit_repository), settings
    )
    return service, repository, storage, selected_scanner, audit_repository


@pytest.mark.parametrize(
    "filename",
    ["../../factura.pdf", r"C:\\fakepath\\factura.pdf", "factura.pdf.exe", "factura.exe.pdf"],
)
def test_rejects_dangerous_filenames(filename: str) -> None:
    with pytest.raises(ValidationError):
        normalize_filename(filename)


def test_validates_declared_type_checksum_and_exact_size_limit() -> None:
    checksum = "a" * 64
    assert validate_declaration(
        filename="reporte.pdf",
        content_type="application/pdf",
        size_bytes=50 * 1024 * 1024,
        checksum_sha256=checksum,
        max_bytes=50 * 1024 * 1024,
    ) == ("reporte.pdf", ".pdf", "application/pdf")
    with pytest.raises(ValidationError, match="MIME"):
        validate_declaration(
            filename="reporte.pdf",
            content_type="text/plain",
            size_bytes=1,
            checksum_sha256=checksum,
            max_bytes=50 * 1024 * 1024,
        )
    with pytest.raises(ValidationError):
        validate_declaration(
            filename="reporte.pdf",
            content_type="application/pdf",
            size_bytes=50 * 1024 * 1024 + 1,
            checksum_sha256=checksum,
            max_bytes=50 * 1024 * 1024,
        )


def test_rejects_zip_traversal_and_macros(tmp_path: Path) -> None:
    traversal = tmp_path / "traversal.docx"
    with zipfile.ZipFile(traversal, "w") as archive:
        archive.writestr("[Content_Types].xml", "types")
        archive.writestr("word/document.xml", "document")
        archive.writestr("../outside.txt", "bad")
    with pytest.raises(ValidationError, match="seguro"):
        inspect_document(traversal, ".docx")

    macro = tmp_path / "macro.xlsx"
    with zipfile.ZipFile(macro, "w") as archive:
        archive.writestr("[Content_Types].xml", "types")
        archive.writestr("xl/workbook.xml", "workbook")
        archive.writestr("xl/vbaProject.bin", "macro")
    with pytest.raises(ValidationError, match="macros"):
        inspect_document(macro, ".xlsx")

    bomb = tmp_path / "bomb.docx"
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "types")
        archive.writestr("word/document.xml", b"0" * (1024 * 1024))
    with pytest.raises(ValidationError, match="compresión"):
        inspect_document(bomb, ".docx")

    encrypted = zipfile.ZipInfo("word/document.xml")
    encrypted.flag_bits = 0x1
    with pytest.raises(ValidationError, match="seguro"):
        _validate_zip_entry(encrypted)


def test_detects_classic_office_stream_and_opendocument_mimetype(tmp_path: Path) -> None:
    classic = tmp_path / "classic.doc"
    classic.write_bytes(
        bytes.fromhex("D0CF11E0A1B11AE1") + b"padding" + "WordDocument".encode("utf-16le")
    )
    detected, _checksum = inspect_document(classic, ".doc")
    assert detected == "application/msword"
    with pytest.raises(ValidationError):
        inspect_document(classic, ".xls")

    disguised = tmp_path / "disguised.odt"
    with zipfile.ZipFile(disguised, "w") as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        archive.writestr("content.xml", "document")
    with pytest.raises(ValidationError, match="OpenDocument"):
        inspect_document(disguised, ".odt")


async def initiate_pdf(
    service: DocumentService,
    storage: FakeObjectStorage,
    payload: bytes,
    *,
    company_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> DocumentAsset:
    ticket = await service.initiate(
        InitiateDocumentInput(
            company_id=company_id,
            actor_id=actor_id,
            filename="contrato.pdf",
            content_type="application/pdf",
            size_bytes=len(payload),
            checksum_sha256=hashlib.sha256(payload).hexdigest(),
        )
    )
    storage.payloads[ticket.document.object_key] = payload
    assert "x-amz-meta-document-id" in ticket.required_headers
    assert "contrato.pdf" not in ticket.document.object_key
    assert ticket.document.object_key.startswith(f"companies/{company_id}/documents/")
    return ticket.document


@pytest.mark.asyncio
async def test_clean_document_flow_is_idempotent_and_downloadable() -> None:
    service, _repository, storage, scanner, audit = make_service()
    company_id, actor_id = uuid.uuid4(), uuid.uuid4()
    document = await initiate_pdf(
        service,
        storage,
        b"%PDF-1.7\nclean document",
        company_id=company_id,
        actor_id=actor_id,
    )

    completed = await service.complete(company_id, document.id, actor_id)
    repeated = await service.complete(company_id, document.id, actor_id)
    url, _expires = await service.download_url(company_id, document.id, actor_id)

    assert completed.status == repeated.status == "active"
    assert completed.detected_content_type == "application/pdf"
    assert completed.etag == "test-etag"
    assert scanner.calls == 1
    assert "download=contrato.pdf" in url
    assert [entry.action for entry in audit.items] == [
        "DOCUMENT_UPLOAD_INITIATED",
        "DOCUMENT_ACTIVATED",
        "DOCUMENT_DOWNLOAD_URL_ISSUED",
    ]


@pytest.mark.asyncio
async def test_malware_is_quarantined_without_download_url() -> None:
    infected_scanner = FakeScanner(ScanResult(clean=False, malware_name="Eicar-Signature"))
    service, repository, storage, _scanner, _audit = make_service(scanner=infected_scanner)
    company_id, actor_id = uuid.uuid4(), uuid.uuid4()
    document = await initiate_pdf(
        service,
        storage,
        b"%PDF-1.7\nEICAR payload",
        company_id=company_id,
        actor_id=actor_id,
    )

    with pytest.raises(ValidationError) as detected:
        await service.complete(company_id, document.id, actor_id)
    assert detected.value.code == "document_malware_detected"
    assert repository.items[document.id].status == "quarantined"
    assert document.object_key in storage.payloads
    with pytest.raises(ConflictError) as blocked:
        await service.download_url(company_id, document.id, actor_id)
    assert blocked.value.code == "document_not_downloadable"


@pytest.mark.asyncio
async def test_scanner_outage_leaves_document_pending_for_retry() -> None:
    service, repository, storage, _scanner, _audit = make_service(
        scanner=FakeScanner(unavailable=True)
    )
    company_id, actor_id = uuid.uuid4(), uuid.uuid4()
    document = await initiate_pdf(
        service,
        storage,
        b"%PDF-1.7\nretry later",
        company_id=company_id,
        actor_id=actor_id,
    )
    with pytest.raises(InfrastructureError):
        await service.complete(company_id, document.id, actor_id)
    assert repository.items[document.id].status == "pending_scan"
    assert document.object_key in storage.payloads


@pytest.mark.asyncio
async def test_pending_limit_and_cross_company_access_fail_closed() -> None:
    service, _repository, storage, _scanner, _audit = make_service(max_pending=1)
    company_id, actor_id = uuid.uuid4(), uuid.uuid4()
    document = await initiate_pdf(
        service,
        storage,
        b"%PDF-1.7\nfirst",
        company_id=company_id,
        actor_id=actor_id,
    )
    with pytest.raises(RateLimitError):
        await service.initiate(
            InitiateDocumentInput(
                company_id=company_id,
                actor_id=actor_id,
                filename="second.pdf",
                content_type="application/pdf",
                size_bytes=1,
                checksum_sha256=hashlib.sha256(b"x").hexdigest(),
            )
        )
    with pytest.raises(NotFoundError):
        await service.get(uuid.uuid4(), document.id)
