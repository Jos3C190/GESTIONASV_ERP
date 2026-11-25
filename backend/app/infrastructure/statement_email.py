"""Envío del estado de cuenta al cliente con el SMTP de la empresa o el del servidor (V5b)."""

from __future__ import annotations

import uuid
from html import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessRuleError
from app.domain.ports.email_sender import (
    EmailAttachment,
    EmailDeliveryError,
    EmailSender,
    OutgoingEmail,
)
from app.infrastructure.dte_email import company_email_sender, email_sender
from app.infrastructure.repositories.company_email_repository import (
    SqlAlchemyCompanyEmailRepository,
)


async def send_statement(
    session: AsyncSession,
    company_id: uuid.UUID,
    *,
    company_name: str,
    recipient: str,
    customer_name: str,
    pdf: bytes,
    sender: EmailSender | None = None,
) -> str:
    """Envía el estado de cuenta y devuelve el ``Message-ID``."""

    stored = await SqlAlchemyCompanyEmailRepository(session).get(company_id)
    if stored is not None and not stored.settings.is_enabled:
        stored = None
    chosen = sender or (company_email_sender(stored) if stored else email_sender())
    if chosen is None:
        raise BusinessRuleError(
            "No hay servidor de correo configurado para la empresa.",
            code="sales_statement_email_unavailable",
        )
    sender_name = (
        stored.settings.from_name if stored and stored.settings.from_name else company_name
    )
    text = (
        f"Estimado cliente {customer_name}:\n\n"
        "Le compartimos su estado de cuenta en el archivo adjunto. Si ya realizó el pago, por "
        "favor ignore este mensaje o envíenos el comprobante.\n\n"
        f"{company_name}"
    )
    html = (
        f"<p>Estimado cliente {escape(customer_name)}:</p><p>Le compartimos su estado de cuenta en el "
        "archivo adjunto. Si ya realizó el pago, por favor ignore este mensaje o envíenos el "
        f"comprobante.</p><p>{escape(company_name)}</p>"
    )
    try:
        return await chosen.send(
            OutgoingEmail(
                sender_name=sender_name,
                recipients=(recipient,),
                subject=f"Estado de cuenta · {company_name}",
                text=text,
                html=html,
                attachments=(EmailAttachment("estado-de-cuenta.pdf", "application/pdf", pdf),),
            )
        )
    except EmailDeliveryError as error:
        raise BusinessRuleError(
            f"No se pudo enviar el estado de cuenta: {error.message}",
            code="sales_statement_email_failed",
        ) from error
