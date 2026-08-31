from __future__ import annotations

import asyncio
import hashlib
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

import pikepdf
from arq import cron
from arq.connections import RedisSettings
from arq.worker import Retry
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import InfrastructureError, ValidationError
from app.core.logging import configure_logging, get_logger
from app.domain.entities.document_derivative import DocumentDerivative
from app.domain.ports.object_storage import StoredObjectInfo
from app.infrastructure.db.session import session_scope
from app.infrastructure.malware_scanner import ClamAVScanner
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.object_storage import S3ObjectStorage
from app.infrastructure.repositories.document_derivative_repository import (
    SqlAlchemyDocumentDerivativeRepository,
)

log = get_logger(__name__)


class PermanentOcrError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class TransientOcrError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _has_signature(pdf: pikepdf.Pdf) -> bool:
    acroform = pdf.Root.get("/AcroForm")
    if acroform is None:
        return False
    pending = list(acroform.get("/Fields", []))
    while pending:
        field = pending.pop()
        if str(field.get("/FT", "")) == "/Sig":
            return True
        pending.extend(field.get("/Kids", []))
    return False


def inspect_pdf(path: Path) -> None:
    try:
        with pikepdf.open(path) as pdf:
            if len(pdf.pages) > settings.OCR_MAX_PAGES:
                raise PermanentOcrError("ocr_page_limit_exceeded")
            if _has_signature(pdf):
                raise PermanentOcrError("ocr_signed_pdf")
    except pikepdf.PasswordError as exc:
        raise PermanentOcrError("ocr_encrypted_pdf") from exc
    except pikepdf.PdfError as exc:
        raise PermanentOcrError("ocr_invalid_pdf") from exc


async def _run_ocr(source: Path, destination: Path) -> None:
    process = await asyncio.create_subprocess_exec(
        "ocrmypdf",
        "--skip-text",
        "--rotate-pages",
        "--deskew",
        "--output-type",
        "pdf",
        "--optimize",
        "1",
        "--language",
        settings.OCR_LANGUAGES,
        "--tesseract-timeout",
        str(settings.OCR_TESSERACT_TIMEOUT_SECONDS),
        "--skip-big",
        str(settings.OCR_SKIP_BIG_MPIX),
        str(source),
        str(destination),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=settings.OCR_JOB_TIMEOUT_SECONDS
        )
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise TransientOcrError("ocr_timeout") from exc
    if process.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace")[-1000:]
        log.warning("ocr_command_failed", returncode=process.returncode, detail=detail)
        raise TransientOcrError("ocr_command_failed")


async def _audit(
    *,
    document: DocumentAssetModel,
    action: str,
    derivative_id: uuid.UUID,
    status: str,
    code: str | None,
) -> None:
    async with session_scope() as session:
        session.add(
            AuditLog(
                action=action,
                company_id=document.company_id,
                resource_type="documents",
                resource_id=str(document.id),
                after_state={
                    "derivative_id": str(derivative_id),
                    "ocr_status": status,
                    "failure_code": code,
                },
            )
        )


async def _load_document(document_id: uuid.UUID) -> DocumentAssetModel | None:
    async with session_scope() as session:
        return (
            await session.execute(
                select(DocumentAssetModel)
                .where(DocumentAssetModel.id == document_id)
                .execution_options(include_deleted=True)
            )
        ).scalar_one_or_none()


async def _mark_permanent(derivative_id: uuid.UUID, code: str) -> None:
    now = datetime.now(UTC)
    async with session_scope() as session:
        repository = SqlAlchemyDocumentDerivativeRepository(session)
        derivative = await repository.get(derivative_id)
        if derivative is None:
            return
        derivative.status = "skipped"
        derivative.failure_code = code
        derivative.completed_at = now
        derivative.started_at = None
        await repository.save(derivative)
        document = await session.get(DocumentAssetModel, derivative.document_id)
    if document is not None:
        await _audit(
            document=document,
            action="DOCUMENT_OCR_FAILED",
            derivative_id=derivative_id,
            status="skipped",
            code=code,
        )


async def _mark_transient(derivative_id: uuid.UUID, code: str) -> bool:
    now = datetime.now(UTC)
    async with session_scope() as session:
        repository = SqlAlchemyDocumentDerivativeRepository(session)
        derivative = await repository.get(derivative_id)
        if derivative is None:
            return False
        retry = derivative.attempts < settings.OCR_MAX_ATTEMPTS
        derivative.status = "pending" if retry else "failed"
        derivative.failure_code = code
        derivative.started_at = None
        derivative.completed_at = None if retry else now
        await repository.save(derivative)
        document = await session.get(DocumentAssetModel, derivative.document_id)
    if not retry and document is not None:
        await _audit(
            document=document,
            action="DOCUMENT_OCR_FAILED",
            derivative_id=derivative_id,
            status="failed",
            code=code,
        )
    return retry


async def _mark_ready(
    derivative_id: uuid.UUID, *, size_bytes: int, checksum: str, etag: str | None
) -> None:
    now = datetime.now(UTC)
    async with session_scope() as session:
        repository = SqlAlchemyDocumentDerivativeRepository(session)
        derivative = await repository.get(derivative_id)
        if derivative is None:
            return
        derivative.status = "ready"
        derivative.size_bytes = size_bytes
        derivative.checksum_sha256 = checksum
        derivative.etag = etag
        derivative.failure_code = None
        derivative.completed_at = now
        derivative.started_at = None
        await repository.save(derivative)
        document = await session.get(DocumentAssetModel, derivative.document_id)
    if document is not None:
        await _audit(
            document=document,
            action="DOCUMENT_OCR_COMPLETED",
            derivative_id=derivative_id,
            status="ready",
            code=None,
        )


def _validate_document(document: DocumentAssetModel | None) -> DocumentAssetModel:
    if (
        document is None
        or document.deleted_at is not None
        or document.status != "active"
        or document.extension != ".pdf"
    ):
        raise PermanentOcrError("ocr_document_not_eligible")
    return document


def _validate_output(path: Path) -> int:
    if not path.exists():
        raise PermanentOcrError("ocr_output_invalid")
    with path.open("rb") as processed:
        if processed.read(5) != b"%PDF-":
            raise PermanentOcrError("ocr_output_invalid")
    output_size = path.stat().st_size
    if output_size <= 0 or output_size > settings.OCR_MAX_OUTPUT_BYTES:
        raise PermanentOcrError("ocr_output_too_large")
    return output_size


async def _generate_derivative(
    ctx: dict[str, Any], derivative: DocumentDerivative, document: DocumentAssetModel
) -> tuple[StoredObjectInfo, str]:
    storage: S3ObjectStorage = ctx["storage"]
    existing = await storage.head(derivative.object_key)
    if (
        existing is not None
        and existing.metadata.get("derivative-id") == str(derivative.id)
        and existing.metadata.get("ocr-scan") == "clean"
        and existing.metadata.get("sha256")
    ):
        return existing, existing.metadata["sha256"]

    with tempfile.TemporaryDirectory(prefix="erp-ocr-") as directory:
        source = Path(directory) / "source.pdf"
        output = Path(directory) / "output.pdf"
        await storage.download_to(document.object_key, source, settings.DOCUMENT_MAX_BYTES)
        if _sha256(source) != document.checksum_sha256:
            raise PermanentOcrError("ocr_source_checksum_mismatch")
        inspect_pdf(source)
        await _run_ocr(source, output)
        _validate_output(output)
        scan = await ctx["scanner"].scan(output)
        if not scan.clean:
            raise PermanentOcrError("ocr_output_malware_detected")
        checksum = _sha256(output)
        info = await storage.upload_from(
            derivative.object_key,
            output,
            content_type="application/pdf",
            metadata={
                "document-id": str(document.id),
                "derivative-id": str(derivative.id),
                "sha256": checksum,
                "ocr-scan": "clean",
            },
        )
    return info, checksum


async def process_ocr(ctx: dict[str, Any], derivative_id_text: str) -> None:
    derivative_id = uuid.UUID(derivative_id_text)
    try:
        async with session_scope() as session:
            repository = SqlAlchemyDocumentDerivativeRepository(session)
            derivative = await repository.claim(derivative_id, datetime.now(UTC))
        if derivative is None:
            return
        document = _validate_document(await _load_document(derivative.document_id))
        info, checksum = await _generate_derivative(ctx, derivative, document)
        await _mark_ready(
            derivative.id, size_bytes=info.size_bytes, checksum=checksum, etag=info.etag
        )
    except PermanentOcrError as exc:
        await _mark_permanent(derivative_id, exc.code)
    except (InfrastructureError, ValidationError, TransientOcrError, OSError) as exc:
        code = getattr(exc, "code", "ocr_processing_failed")
        retry = await _mark_transient(derivative_id, str(code))
        if retry:
            derivative_attempt = 1
            async with session_scope() as session:
                current = await SqlAlchemyDocumentDerivativeRepository(session).get(derivative_id)
                if current is not None:
                    derivative_attempt = max(current.attempts, 1)
            raise Retry(defer=min(30 * (2 ** (derivative_attempt - 1)), 600)) from exc


async def reconcile_ocr(ctx: dict[str, Any]) -> None:
    if not settings.OCR_ENABLED:
        return
    stale_before = datetime.now(UTC) - timedelta(minutes=settings.OCR_STALE_MINUTES)
    async with session_scope() as session:
        repository = SqlAlchemyDocumentDerivativeRepository(session)
        reset = await repository.reset_stale(stale_before)
        pending = await repository.list_pending_ids(limit=20)
    for derivative_id in pending:
        await ctx["redis"].enqueue_job(
            "process_ocr", str(derivative_id), _job_id=f"ocr:{derivative_id}"
        )
    if reset or pending:
        log.info("ocr_reconciled", stale_reset=reset, pending_enqueued=len(pending))


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    ctx["storage"] = S3ObjectStorage(settings)
    ctx["scanner"] = ClamAVScanner(
        settings.CLAMAV_HOST, settings.CLAMAV_PORT, settings.CLAMAV_TIMEOUT_SECONDS
    )


_reconcile_seconds = set(range(0, 60, settings.OCR_RECONCILE_SECONDS))


class WorkerSettings:
    functions: ClassVar[list[Any]] = [process_ocr]
    cron_jobs: ClassVar[list[Any]] = [
        cron(reconcile_ocr, second=_reconcile_seconds, run_at_startup=True)
    ]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL or "redis://localhost:6379/0")
    on_startup = startup
    max_jobs = 1
    max_tries = settings.OCR_MAX_ATTEMPTS
    job_timeout = settings.OCR_JOB_TIMEOUT_SECONDS + 60
    keep_result = 0
    health_check_interval = 10
    health_check_key = "erp:ocr:health"
