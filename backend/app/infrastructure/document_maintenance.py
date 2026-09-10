from __future__ import annotations

import asyncio
import signal
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.infrastructure.db.session import session_scope
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.document_derivative import DocumentDerivativeModel
from app.infrastructure.models.document_general_import import (
    DocumentGeneralImportItemModel,
    DocumentGeneralImportModel,
)
from app.infrastructure.object_storage import S3ObjectStorage
from app.infrastructure.observability import (
    initialize_observability,
    operation_span,
    record_counter,
    record_histogram,
    shutdown_observability,
)

log = get_logger(__name__)


def _record_item_metrics(
    *, stale_scans: int, stale_ocr: int, purged: int, expired_imports: int, failures: int
) -> None:
    outcomes = {
        "document_scan_reset": stale_scans,
        "ocr_reset": stale_ocr,
        "purged": purged,
        "expired_imports": expired_imports,
        "failed": failures,
    }
    for item_status, count in outcomes.items():
        if count:
            record_counter(
                "erp.maintenance.items",
                value=count,
                attributes={"status": item_status},
            )


async def _expire_imports(session: AsyncSession, now: datetime) -> int:
    rows = (
        (
            await session.execute(
                select(DocumentGeneralImportModel)
                .where(
                    DocumentGeneralImportModel.expires_at.is_not(None),
                    DocumentGeneralImportModel.expires_at <= now,
                    DocumentGeneralImportModel.status.in_(("preparing", "ready", "running")),
                )
                .with_for_update(skip_locked=True)
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        pending_items = (
            (
                await session.execute(
                    select(DocumentGeneralImportItemModel).where(
                        DocumentGeneralImportItemModel.import_id == row.id,
                        DocumentGeneralImportItemModel.status.in_(("ready", "authorized")),
                    )
                )
            )
            .scalars()
            .all()
        )
        for item in pending_items:
            item.status = "cancelled"
            item.failure_code = "document_import_expired"
            item.failure_message = (
                "La sesión de importación expiró antes de completar este archivo."
            )
        row.status = "expired"
        row.completed_at = now
        session.add(
            AuditLog(
                action="GENERAL_FOLDER_IMPORT_EXPIRED",
                user_id=row.actor_id,
                company_id=row.company_id,
                resource_type="document_general_imports",
                resource_id=str(row.id),
                after_state={
                    "status": "expired",
                    "cancelled_files": len(pending_items),
                    "root_entry_id": str(row.root_entry_id) if row.root_entry_id else None,
                },
            )
        )
    return len(rows)


async def run_once() -> None:
    started = asyncio.get_running_loop().time()
    result = "ok"
    with operation_span("documents.maintenance", operation="run"):
        try:
            await _run_once_impl()
        except Exception:
            result = "failed"
            raise
        finally:
            record_counter("erp.maintenance.runs", attributes={"result": result})
            record_histogram(
                "erp.maintenance.duration",
                (asyncio.get_running_loop().time() - started) * 1000,
                attributes={"result": result},
            )


async def _run_once_impl() -> None:
    now = datetime.now(UTC)
    storage = S3ObjectStorage(settings)
    async with session_scope() as session:
        acquired = bool(
            await session.scalar(
                text("SELECT pg_try_advisory_xact_lock(hashtext('documents.maintenance'))")
            )
        )
        if not acquired:
            return
        expired_imports = await _expire_imports(session, now)
        stale_scan = now - timedelta(minutes=settings.DOCUMENT_SCAN_STALE_MINUTES)
        stale = (
            (
                await session.execute(
                    select(DocumentAssetModel)
                    .where(
                        DocumentAssetModel.status == "scanning",
                        DocumentAssetModel.scan_started_at < stale_scan,
                    )
                    .execution_options(include_deleted=True)
                )
            )
            .scalars()
            .all()
        )
        for document in stale:
            document.status = "pending_scan"
            document.failure_code = "document_scan_interrupted"

        stale_ocr_before = now - timedelta(minutes=settings.OCR_STALE_MINUTES)
        stale_ocr = cast(
            CursorResult[Any],
            await session.execute(
                update(DocumentDerivativeModel)
                .where(
                    DocumentDerivativeModel.status == "processing",
                    DocumentDerivativeModel.started_at < stale_ocr_before,
                )
                .values(
                    status="pending", failure_code="ocr_processing_interrupted", started_at=None
                )
            ),
        )

        pending_before = now - timedelta(hours=settings.DOCUMENT_PENDING_RETENTION_HOURS)
        quarantine_before = now - timedelta(days=settings.DOCUMENT_QUARANTINE_RETENTION_DAYS)
        deletion_before = now - timedelta(days=settings.DOCUMENT_DELETION_RETENTION_DAYS)
        candidates = (
            (
                await session.execute(
                    select(DocumentAssetModel)
                    .where(
                        or_(
                            and_(
                                DocumentAssetModel.status.in_(("pending_upload", "pending_scan")),
                                DocumentAssetModel.created_at < pending_before,
                            ),
                            and_(
                                DocumentAssetModel.status == "quarantined",
                                DocumentAssetModel.scanned_at < quarantine_before,
                            ),
                            and_(
                                DocumentAssetModel.status == "rejected",
                                DocumentAssetModel.object_deleted_at.is_(None),
                            ),
                            DocumentAssetModel.deleted_at < deletion_before,
                        )
                    )
                    .execution_options(include_deleted=True)
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        purged = 0
        failures = 0
        for document in candidates:
            try:
                derivatives = (
                    (
                        await session.execute(
                            select(DocumentDerivativeModel).where(
                                DocumentDerivativeModel.document_id == document.id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                for derivative in derivatives:
                    if derivative.object_deleted_at is None:
                        await storage.delete(derivative.object_key)
                        derivative.object_deleted_at = now
                if document.object_deleted_at is None:
                    await storage.delete(document.object_key)
                    document.object_deleted_at = now
                if document.deleted_at is not None or document.status in {
                    "pending_upload",
                    "pending_scan",
                    "rejected",
                }:
                    session.add(
                        AuditLog(
                            action="DOCUMENT_PURGED",
                            company_id=document.company_id,
                            resource_type="documents",
                            resource_id=str(document.id),
                            before_state={
                                "filename": document.original_filename,
                                "status": document.status,
                            },
                            after_state={"object_deleted_at": now.isoformat()},
                        )
                    )
                    await session.delete(document)
                    purged += 1
                else:
                    document.status = "rejected"
                    document.failure_code = "document_malware_purged"
                    session.add(
                        AuditLog(
                            action="DOCUMENT_QUARANTINE_PURGED",
                            company_id=document.company_id,
                            resource_type="documents",
                            resource_id=str(document.id),
                            after_state={"status": document.status},
                        )
                    )
                    purged += 1
            except Exception as exc:
                failures += 1
                log.warning("document_purge_failed", document_id=str(document.id), error=str(exc))
        _record_item_metrics(
            stale_scans=len(stale),
            stale_ocr=int(stale_ocr.rowcount or 0),
            purged=purged,
            expired_imports=expired_imports,
            failures=failures,
        )
        log.info(
            "document_maintenance_completed",
            stale_scans=len(stale),
            stale_ocr=int(stale_ocr.rowcount or 0),
            purge_candidates=len(candidates),
            expired_imports=expired_imports,
        )


async def main() -> None:
    configure_logging()
    initialize_observability("erp-document-maintenance")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signum, stop.set)
    try:
        while not stop.is_set():
            try:
                await run_once()
            except Exception:
                log.exception("document_maintenance_failed")
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=settings.DOCUMENT_MAINTENANCE_INTERVAL_SECONDS
                )
            except TimeoutError:
                continue
    finally:
        shutdown_observability()


if __name__ == "__main__":
    asyncio.run(main())
