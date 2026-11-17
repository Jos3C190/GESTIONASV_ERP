"""Entrega por correo del documento fiscal, dentro de ``dte-worker`` (bloque V3c).

- ``queue_auto_email`` crea el envío automático cuando el documento queda emitido y el cliente
  tiene un correo válido (a lo sumo uno por documento).
- ``process_fiscal_email`` toma un envío pendiente, arma el mensaje con el PDF y el JSON del DTE
  y lo entrega por SMTP. Un error temporal deja el envío pendiente para reintentarlo.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.audit.audit_service import AuditService
from app.core.config import settings
from app.domain.entities.sales_fiscal_document import FiscalDocumentStatus
from app.domain.entities.sales_fiscal_email import (
    EmailOrigin,
    EmailStatus,
    FiscalEmailContent,
    PrivacyNoticeText,
    compose,
    customer_recipients,
)
from app.domain.ports.dte_service import DteService
from app.domain.ports.email_sender import (
    EmailAttachment,
    EmailDeliveryError,
    EmailSender,
    OutgoingEmail,
)
from app.domain.ports.object_storage import ObjectStorage
from app.domain.ports.sales_fiscal_repository import FiscalDocument, FiscalDocumentEmail
from app.infrastructure.repositories.audit_repository import SqlAlchemyAuditRepository
from app.infrastructure.repositories.privacy_repository import SqlAlchemyPrivacyRepository
from app.infrastructure.repositories.sales_fiscal_email_repository import (
    SqlAlchemySalesFiscalEmailRepository,
)
from app.infrastructure.repositories.sales_fiscal_repository import SqlAlchemySalesFiscalRepository
from app.infrastructure.smtp_email_sender import SmtpEmailSender

SessionScope = Callable[[], AbstractAsyncContextManager[AsyncSession]]
_MAX_PDF_BYTES = 20 * 1024 * 1024
_MAX_ERROR = 2000


def email_sender() -> SmtpEmailSender | None:
    if not (settings.SMTP_HOST and settings.SMTP_FROM_ADDRESS):
        return None
    return SmtpEmailSender(
        settings.SMTP_HOST,
        settings.SMTP_PORT,
        settings.SMTP_FROM_ADDRESS,
        username=settings.SMTP_USERNAME,
        password=settings.SMTP_PASSWORD,
        security=settings.SMTP_SECURITY,
        timeout_seconds=settings.SMTP_TIMEOUT_SECONDS,
    )


async def _audit(
    session: AsyncSession, document: FiscalDocument, email: FiscalDocumentEmail, action: str
) -> None:
    await AuditService(SqlAlchemyAuditRepository(session)).record(
        action=action,
        company_id=document.company_id,
        branch_id=document.branch_id,
        resource_type="sales_fiscal_document",
        resource_id=str(document.id),
        after_state={
            "email_id": str(email.id),
            "origin": email.origin,
            "status": email.status,
            "recipients": list(email.recipients),
            "attempts": email.attempts,
            "message_id": email.message_id,
            "error_code": email.error_code,
        },
        metadata={"actor": "dte-worker"},
    )


async def queue_auto_email(scope: SessionScope, document: FiscalDocument) -> uuid.UUID | None:
    """Crea el envío automático de un documento recién emitido; ``None`` si no corresponde."""

    if not settings.SMTP_HOST or document.status not in (
        FiscalDocumentStatus.ISSUED,
        FiscalDocumentStatus.SIMULATED,
    ):
        return None
    recipients = customer_recipients(document.customer_email)
    if not recipients:
        return None
    async with scope() as session:
        repo = SqlAlchemySalesFiscalEmailRepository(session)
        if await repo.auto_exists(document.company_id, document.id):
            return None
        email = await repo.create(
            FiscalDocumentEmail(
                id=uuid.uuid4(),
                company_id=document.company_id,
                document_id=document.id,
                recipients=recipients,
                origin=EmailOrigin.AUTO.value,
                status=EmailStatus.PENDING.value,
            )
        )
    return email.id


async def _pdf(
    document: FiscalDocument, storage: ObjectStorage | None, client: DteService | None
) -> bytes:
    if storage is not None and document.pdf_object_key:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "dte.pdf"
            await storage.download_to(document.pdf_object_key, target, _MAX_PDF_BYTES)
            return target.read_bytes()
    if client is not None and document.generation_code:
        return await client.document_pdf(
            str(document.issuer_snapshot["nit"]), str(document.generation_code).upper()
        )
    raise EmailDeliveryError(
        "El PDF del documento no está disponible.", code="email_pdf_missing", transient=True
    )


async def _message(
    scope: SessionScope, document: FiscalDocument, email: FiscalDocumentEmail, pdf: bytes
) -> OutgoingEmail:
    async with scope() as session:
        notice = await SqlAlchemyPrivacyRepository(session).current_notice(document.company_id)
    issuer = document.issuer_snapshot
    company = str(issuer.get("tradeName") or issuer.get("legalName") or "")
    reply_to = issuer.get("email")
    composed = compose(
        FiscalEmailContent(
            company_name=company,
            document_type=document.document_type,
            control_number=document.control_number or str(document.id),
            generation_code=str(document.generation_code or ""),
            issued_at=document.issued_at or datetime.now(UTC),
            total=document.total,
            customer_name=document.customer_name or "cliente",
            simulated=document.status is FiscalDocumentStatus.SIMULATED,
            reply_to=str(reply_to) if reply_to else None,
            privacy_notice=PrivacyNoticeText(notice.title, notice.body) if notice else None,
        )
    )
    return OutgoingEmail(
        sender_name=company,
        recipients=email.recipients,
        subject=composed.subject,
        text=composed.text,
        html=composed.html,
        reply_to=str(reply_to) if reply_to else None,
        attachments=(
            EmailAttachment(composed.pdf_filename, "application/pdf", pdf),
            EmailAttachment(
                composed.json_filename,
                "application/json",
                json.dumps(document.dte_json or {}, ensure_ascii=False, indent=2).encode("utf-8"),
            ),
        ),
    )


async def _finish(
    scope: SessionScope, document: FiscalDocument, email: FiscalDocumentEmail, action: str | None
) -> FiscalDocumentEmail:
    async with scope() as session:
        saved = await SqlAlchemySalesFiscalEmailRepository(session).save(email)
        if action:
            await _audit(session, document, saved, action)
    return saved


async def process_fiscal_email(
    email_id: uuid.UUID,
    *,
    sender: EmailSender,
    storage: ObjectStorage | None,
    client: DteService | None,
    scope: SessionScope,
    max_attempts: int | None = None,
) -> FiscalDocumentEmail | None:
    """Entrega un envío pendiente. Lanza ``EmailDeliveryError`` reintentable si quedó pendiente."""

    limit = max_attempts or settings.DTE_MAX_ATTEMPTS
    async with scope() as session:
        email = await SqlAlchemySalesFiscalEmailRepository(session).claim(email_id)
        document = (
            await SqlAlchemySalesFiscalRepository(session).get(email.company_id, email.document_id)
            if email is not None
            else None
        )
    if email is None or document is None:
        return None
    if email.attempts > limit:
        email.status = EmailStatus.FAILED.value
        email.error_code = email.error_code or "email_attempts_exhausted"
        return await _finish(scope, document, email, "FISCAL_DOCUMENT_EMAIL_FAILED")
    try:
        message = await _message(scope, document, email, await _pdf(document, storage, client))
        email.message_id = await sender.send(message)
    except EmailDeliveryError as error:
        email.error_code = error.code
        email.error_message = error.message[:_MAX_ERROR]
        if error.transient:
            await _finish(scope, document, email, None)
            raise
        email.status = EmailStatus.FAILED.value
        return await _finish(scope, document, email, "FISCAL_DOCUMENT_EMAIL_FAILED")
    email.status = EmailStatus.SENT.value
    email.sent_at = datetime.now(UTC)
    email.error_code = None
    email.error_message = None
    return await _finish(scope, document, email, "FISCAL_DOCUMENT_EMAIL_SENT")
