"""Enviar por correo el documento fiscal (bloque V3c).

El envío automático lo crea el trabajador al emitirse el documento; aquí están el envío que pide
un usuario y el historial. Ambos quedan ``pending`` y los entrega ``dte-worker``.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.sales_fiscal_email import (
    EmailOrigin,
    EmailStatus,
    customer_recipients,
    normalize_recipients,
    require_sendable,
)
from app.domain.ports.sales_fiscal_repository import (
    FiscalDocument,
    FiscalDocumentEmail,
    SalesFiscalEmailRepository,
    SalesFiscalRepository,
)


class SalesInvoiceEmailUseCases:
    def __init__(
        self,
        documents: SalesFiscalRepository,
        emails: SalesFiscalEmailRepository,
        available: Callable[[uuid.UUID], Awaitable[bool]],
    ) -> None:
        self._documents = documents
        self._emails = emails
        self._available = available

    async def available(self, company_id: uuid.UUID) -> bool:
        """Si la empresa tiene SMTP propio activo o el servidor tiene uno."""
        return await self._available(company_id)

    async def _document(self, company_id: uuid.UUID, document_id: uuid.UUID) -> FiscalDocument:
        document = await self._documents.get(company_id, document_id)
        if document is None:
            raise NotFoundError("El documento fiscal no existe.", code="sales_invoice_not_found")
        return document

    async def history(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[FiscalDocumentEmail]:
        await self._document(company_id, document_id)
        return await self._emails.list_for_document(company_id, document_id)

    async def request(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: uuid.UUID,
        recipients: list[str] | None,
    ) -> tuple[FiscalDocument, FiscalDocumentEmail]:
        document = await self._document(company_id, document_id)
        if not await self._available(company_id):
            raise BusinessRuleError(
                "Configura el correo saliente de la empresa (Configuración fiscal → Correo) "
                "para enviar documentos.",
                code="sales_invoice_email_unavailable",
            )
        require_sendable(document.status.value)
        if recipients:
            addresses = normalize_recipients(recipients)
        else:
            addresses = customer_recipients(document.customer_email)
            if not addresses:
                raise BusinessRuleError(
                    "El cliente no tiene un correo válido en su ficha. Escribe a quién enviarlo.",
                    code="sales_invoice_email_required",
                )
        email = await self._emails.create(
            FiscalDocumentEmail(
                id=uuid.uuid4(),
                company_id=company_id,
                document_id=document.id,
                recipients=addresses,
                origin=EmailOrigin.MANUAL.value,
                status=EmailStatus.PENDING.value,
                requested_by_id=actor_id,
            )
        )
        return document, email
