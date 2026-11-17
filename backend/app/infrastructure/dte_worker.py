"""Trabajador ``dte-worker``: emite en el servicio DTE los documentos fiscales pendientes.

La fila ``pending`` es la cola. La API encola el documento después de confirmar la transacción y
la conciliación periódica recoge lo que se haya escapado (Redis caído, un reinicio). Cada
emisión usa la clave de idempotencia del documento, así que repetirla no crea otro DTE.

Pasos por documento:

1. Toma el documento (``SKIP LOCKED``) y cuenta el intento.
2. Registra o actualiza al emisor en el servicio con su modo y sus tipos habilitados.
3. Emite. Con un resultado final baja el JSON y el PDF, los guarda en el almacenamiento y
   compara el resumen del JSON con los totales del pedido.
4. Un error reintentable deja el documento pendiente; uno definitivo lo marca ``failed``.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

from arq import create_pool, cron
from arq.connections import ArqRedis, RedisSettings
from arq.worker import Retry
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.audit.audit_service import AuditService
from app.application.fiscal.hacienda_credentials import decrypt_credentials
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.domain.entities.sales_fiscal_document import (
    INVOICEABLE_DOCUMENTS,
    FiscalDocumentStatus,
    FiscalMode,
    dte_differences,
    service_status,
)
from app.domain.ports.dte_service import DteService, DteServiceError, IssuerCredentials
from app.domain.ports.email_sender import EmailDeliveryError
from app.domain.ports.object_storage import ObjectStorage
from app.domain.ports.sales_fiscal_repository import FiscalDocument
from app.infrastructure.db.session import session_scope
from app.infrastructure.dte_email import email_sender, process_fiscal_email, queue_auto_email
from app.infrastructure.dte_service_client import HttpDteServiceClient
from app.infrastructure.object_storage import S3ObjectStorage
from app.infrastructure.repositories.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.repositories.fiscal_repository import SqlAlchemyFiscalRepository
from app.infrastructure.repositories.hacienda_credentials_repository import (
    SqlAlchemyHaciendaCredentialsRepository,
)
from app.infrastructure.repositories.sales_fiscal_email_repository import (
    SqlAlchemySalesFiscalEmailRepository,
)
from app.infrastructure.repositories.sales_fiscal_repository import SqlAlchemySalesFiscalRepository
from app.infrastructure.repositories.sales_order_repository import SqlAlchemySalesOrderRepository

log = get_logger(__name__)

DTE_QUEUE = "arq:dte"
DTE_HEALTH_KEY = "erp:dte:health"
_MAX_ERROR = 2000

SessionScope = Callable[[], AbstractAsyncContextManager[AsyncSession]]
EmailQueued = Callable[[uuid.UUID], Awaitable[None]]


def dte_client() -> HttpDteServiceClient | None:
    if not (settings.DTE_SERVICE_URL and settings.DTE_SERVICE_API_KEY):
        return None
    return HttpDteServiceClient(
        settings.DTE_SERVICE_URL,
        settings.DTE_SERVICE_API_KEY,
        timeout_seconds=settings.DTE_SERVICE_TIMEOUT_SECONDS,
    )


def object_storage() -> S3ObjectStorage | None:
    return S3ObjectStorage(settings) if settings.OBJECT_STORAGE_ENABLED else None


async def _audit(session: AsyncSession, document: FiscalDocument, action: str) -> None:
    await AuditService(SqlAlchemyAuditRepository(session)).record(
        action=action,
        company_id=document.company_id,
        branch_id=document.branch_id,
        resource_type="sales_fiscal_document",
        resource_id=str(document.id),
        after_state={
            "status": document.status.value,
            "sale_id": str(document.sale_id),
            "document_type": document.document_type,
            "control_number": document.control_number,
            "generation_code": str(document.generation_code) if document.generation_code else None,
            "attempts": document.attempts,
            "error_code": document.error_code,
        },
        metadata={"actor": "dte-worker"},
    )


async def _save(
    scope: SessionScope, document: FiscalDocument, action: str | None = None
) -> FiscalDocument:
    async with scope() as session:
        saved = await SqlAlchemySalesFiscalRepository(session).save(document)
        if action:
            await _audit(session, saved, action)
    return saved


async def _enabled_types(scope: SessionScope, company_id: uuid.UUID) -> list[str]:
    async with scope() as session:
        settings_list = await SqlAlchemyFiscalRepository(session).list_document_types(company_id)
    return sorted(
        item.document_type
        for item in settings_list
        if item.is_enabled and item.document_type in INVOICEABLE_DOCUMENTS
    )


async def _credentials(scope: SessionScope, document: FiscalDocument) -> IssuerCredentials | None:
    """Fuera de simulado, el emisor se registra con sus credenciales de Hacienda (V3d)."""

    if document.mode == FiscalMode.SIMULATED.value:
        return None
    async with scope() as session:
        stored = await SqlAlchemyHaciendaCredentialsRepository(session).get(document.company_id)
    if stored is None:
        raise DteServiceError(
            "La empresa no tiene credenciales de Hacienda para emitir en "
            f"{document.mode}. Cárgalas en Configuración fiscal → Hacienda.",
            code="hacienda_credentials_missing",
            transient=False,
        )
    return decrypt_credentials(stored)


async def _store(
    storage: ObjectStorage | None, document: FiscalDocument, dte_json: dict[str, Any], pdf: bytes
) -> tuple[str | None, str | None]:
    if storage is None:
        return None, None
    base = f"companies/{document.company_id}/sales-fiscal/{document.id}/{document.control_number}"
    metadata = {"fiscal-document-id": str(document.id), "document-type": document.document_type}
    with tempfile.TemporaryDirectory() as folder:
        json_path = Path(folder) / "dte.json"
        json_path.write_text(json.dumps(dte_json, ensure_ascii=False), encoding="utf-8")
        pdf_path = Path(folder) / "dte.pdf"
        pdf_path.write_bytes(pdf)
        await storage.upload_from(
            f"{base}.json", json_path, content_type="application/json", metadata=metadata
        )
        await storage.upload_from(
            f"{base}.pdf", pdf_path, content_type="application/pdf", metadata=metadata
        )
    return f"{base}.json", f"{base}.pdf"


async def _totals(scope: SessionScope, document: FiscalDocument) -> Any:
    from app.application.sales_invoices import SalesInvoiceUseCases

    async with scope() as session:
        order = await SqlAlchemySalesOrderRepository(session).get(
            document.company_id, document.sale_id
        )
    return SalesInvoiceUseCases.totals(order) if order is not None else None


def _final_status(estado: str) -> FiscalDocumentStatus:
    status = service_status(estado)
    if status is None:
        # Firmado sin transmitir o en contingencia: el servicio lo termina después.
        raise DteServiceError(
            f"El servicio dejó el documento en {estado}.", code="dte_not_final", transient=True
        )
    return status


async def process_fiscal_document(
    document_id: uuid.UUID,
    *,
    client: DteService,
    storage: ObjectStorage | None,
    scope: SessionScope = session_scope,
    max_attempts: int | None = None,
    on_email: EmailQueued | None = None,
) -> FiscalDocument | None:
    """Emite un documento pendiente. Devuelve el documento guardado, o ``None`` si no le tocaba.

    Lanza ``DteServiceError`` reintentable cuando el documento quedó pendiente. Al quedar
    emitido crea el envío automático al cliente y avisa con ``on_email``.
    """

    limit = max_attempts or settings.DTE_MAX_ATTEMPTS
    async with scope() as session:
        document = await SqlAlchemySalesFiscalRepository(session).claim(document_id, limit)
    if document is None:
        return None
    if document.attempts > limit:
        document.status = FiscalDocumentStatus.FAILED
        document.error_code = document.error_code or "dte_attempts_exhausted"
        document.error_message = (
            f"Se agotaron los {limit} intentos de emisión. {document.error_message or ''}"
        ).strip()
        return await _save(scope, document, "FISCAL_DOCUMENT_FAILED")

    nit = str(document.issuer_snapshot["nit"])
    try:
        await client.register_issuer(
            nit,
            name=str(document.issuer_snapshot["legalName"]),
            mode=document.mode,
            document_types=await _enabled_types(scope, document.company_id),
            credentials=await _credentials(scope, document),
        )
        result = await client.issue(
            document.document_type,
            nit=nit,
            idempotency_key=document.idempotency_key,
            body=document.request_payload,
        )
        document.service_response = result.response
        if result.generation_code:
            document.generation_code = uuid.UUID(result.generation_code)
        document.control_number = result.control_number or document.control_number
        status = _final_status(result.status)
        if status is FiscalDocumentStatus.REJECTED:
            document.status = status
            document.error_code = "dte_rejected"
            document.error_message = json.dumps(
                result.response.get("respuestaHacienda") or result.response.get("simulacion"),
                ensure_ascii=False,
            )[:_MAX_ERROR]
            return await _save(scope, document, "FISCAL_DOCUMENT_REJECTED")
        code = result.generation_code or str(document.generation_code or "").upper()
        dte_json = await client.document_json(nit, code)
        pdf = await client.document_pdf(nit, code)
        document.json_object_key, document.pdf_object_key = await _store(
            storage, document, dte_json, pdf
        )
        document.dte_json = dte_json
        document.seal = result.seal
        document.status = status
        document.issued_at = datetime.now(UTC)
        document.error_code = None
        document.error_message = None
        totals = await _totals(scope, document)
        differences = dte_differences(dte_json, totals) if totals is not None else []
        if differences:
            document.error_code = "dte_totals_mismatch"
            document.error_message = "; ".join(differences)[:_MAX_ERROR]
        saved = await _save(scope, document, "FISCAL_DOCUMENT_ISSUED")
    except DteServiceError as error:
        document.error_code = error.code[:80]
        document.error_message = error.message[:_MAX_ERROR]
        if error.transient:
            await _save(scope, document)
            raise
        document.status = FiscalDocumentStatus.FAILED
        return await _save(scope, document, "FISCAL_DOCUMENT_FAILED")
    email_id = await queue_auto_email(scope, saved)
    if email_id is not None and on_email is not None:
        await on_email(email_id)
    return saved


# --- arq ----------------------------------------------------------------------------------------


async def issue_fiscal_document(ctx: dict[str, Any], document_id_text: str) -> None:
    async def queue_email(email_id: uuid.UUID) -> None:
        await ctx["redis"].enqueue_job(
            "send_fiscal_email", str(email_id), _job_id=f"dte-email:{email_id}"
        )

    try:
        await process_fiscal_document(
            uuid.UUID(document_id_text),
            client=ctx["dte"],
            storage=ctx["storage"],
            on_email=queue_email,
        )
    except DteServiceError as error:
        attempt = int(ctx.get("job_try") or 1)
        log.info("dte_issue_retry", code=error.code, attempt=attempt)
        raise Retry(defer=min(15 * (2 ** (attempt - 1)), 300)) from error


async def reconcile_fiscal_documents(ctx: dict[str, Any]) -> None:
    stale_before = datetime.now(UTC) - timedelta(minutes=settings.DTE_STALE_MINUTES)
    async with session_scope() as session:
        pending = await SqlAlchemySalesFiscalRepository(session).pending_ids(stale_before, 20)
        emails = await SqlAlchemySalesFiscalEmailRepository(session).pending_ids(stale_before, 20)
    for document_id in pending:
        await ctx["redis"].enqueue_job(
            "issue_fiscal_document", str(document_id), _job_id=f"dte:{document_id}"
        )
    for email_id in emails:
        await ctx["redis"].enqueue_job(
            "send_fiscal_email", str(email_id), _job_id=f"dte-email:{email_id}"
        )
    if pending or emails:
        log.info("dte_reconciled", pending_enqueued=len(pending), emails_enqueued=len(emails))


async def send_fiscal_email(ctx: dict[str, Any], email_id_text: str) -> None:
    try:
        await process_fiscal_email(
            uuid.UUID(email_id_text),
            sender=ctx["mailer"],
            storage=ctx["storage"],
            client=ctx["dte"],
            scope=session_scope,
        )
    except EmailDeliveryError as error:
        attempt = int(ctx.get("job_try") or 1)
        log.info("dte_email_retry", code=error.code, attempt=attempt)
        raise Retry(defer=min(30 * (2 ** (attempt - 1)), 600)) from error


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    ctx["dte"] = dte_client()
    ctx["storage"] = object_storage()
    ctx["mailer"] = email_sender()


_reconcile_seconds = set(range(0, 60, settings.DTE_RECONCILE_SECONDS))


class WorkerSettings:
    functions: ClassVar[list[Any]] = [issue_fiscal_document, send_fiscal_email]
    cron_jobs: ClassVar[list[Any]] = [
        cron(reconcile_fiscal_documents, second=_reconcile_seconds, run_at_startup=True)
    ]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL or "redis://localhost:6379/0")
    queue_name = DTE_QUEUE
    on_startup = startup
    max_jobs = 4
    max_tries = settings.DTE_MAX_ATTEMPTS + 1
    job_timeout = int(settings.DTE_SERVICE_TIMEOUT_SECONDS * 4) + 30
    keep_result = 0
    health_check_interval = 10
    health_check_key = DTE_HEALTH_KEY


# --- encolar desde la API -----------------------------------------------------------------------

_pool: ArqRedis | None = None


async def _enqueue(function: str, item_id: uuid.UUID, job_id: str) -> None:
    """Encola sin fallar la solicitud: la conciliación recoge lo que esto pierda."""

    if not (settings.REDIS_ENABLED and settings.DTE_SERVICE_URL):
        return
    global _pool  # noqa: PLW0603
    try:
        if _pool is None:
            _pool = await create_pool(
                RedisSettings.from_dsn(settings.REDIS_URL or "redis://localhost:6379/0"),
                default_queue_name=DTE_QUEUE,
            )
        await _pool.enqueue_job(function, str(item_id), _job_id=job_id, _queue_name=DTE_QUEUE)
    except Exception as exc:
        log.warning("dte_enqueue_failed", function=function, error_type=type(exc).__name__)


async def enqueue_fiscal_document(document_id: uuid.UUID) -> None:
    await _enqueue("issue_fiscal_document", document_id, f"dte:{document_id}")


async def enqueue_fiscal_email(email_id: uuid.UUID) -> None:
    await _enqueue("send_fiscal_email", email_id, f"dte-email:{email_id}")
