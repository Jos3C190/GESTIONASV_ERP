from __future__ import annotations

import asyncio
import signal
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, text

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.infrastructure.db.session import session_scope
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.object_storage import S3ObjectStorage

log = get_logger(__name__)


async def run_once() -> None:
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

        pending_before = now - timedelta(hours=settings.DOCUMENT_PENDING_RETENTION_HOURS)
        quarantine_before = now - timedelta(days=settings.DOCUMENT_QUARANTINE_RETENTION_DAYS)
        deletion_before = now - timedelta(days=settings.DOCUMENT_DELETION_RETENTION_DAYS)
        candidates = (
            (
                await session.execute(
                    select(DocumentAssetModel)
                    .where(
                        or_(
                            (
                                DocumentAssetModel.status.in_(("pending_upload", "pending_scan"))
                                & (DocumentAssetModel.created_at < pending_before)
                            ),
                            (
                                DocumentAssetModel.status
                                == "quarantined"
                                & (DocumentAssetModel.scanned_at < quarantine_before)
                            ),
                            (
                                DocumentAssetModel.status
                                == "rejected" & DocumentAssetModel.object_deleted_at.is_(None)
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
        for document in candidates:
            try:
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
            except Exception as exc:
                log.warning("document_purge_failed", document_id=str(document.id), error=str(exc))
        log.info(
            "document_maintenance_completed",
            stale_scans=len(stale),
            purge_candidates=len(candidates),
        )


async def main() -> None:
    configure_logging()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signum, stop.set)
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


if __name__ == "__main__":
    asyncio.run(main())
