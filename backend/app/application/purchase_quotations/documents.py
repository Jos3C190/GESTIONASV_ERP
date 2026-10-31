"""Secure upload and retrieval of original supplier quotation documents."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.audit.audit_service import AuditService
from app.application.documents.service import DocumentService, InitiateDocumentInput, UploadTicket
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.document import DocumentAsset
from app.domain.entities.purchase_quotation import PurchaseQuotationStatus
from app.domain.entities.purchase_quotation_document import PurchaseQuotationDocument
from app.domain.ports.purchase_quotation_document_repository import (
    PurchaseQuotationDocumentReference,
    PurchaseQuotationDocumentRepository,
)

UPLOADABLE_STATUSES = frozenset(
    {
        PurchaseQuotationStatus.REQUESTED,
        PurchaseQuotationStatus.RECEIVED,
        PurchaseQuotationStatus.UNDER_EVALUATION,
    }
)


@dataclass(frozen=True, slots=True)
class PurchaseQuotationDocumentUpload:
    ticket: UploadTicket
    attachment: PurchaseQuotationDocument


@dataclass(frozen=True, slots=True)
class PurchaseQuotationDocumentView:
    attachment: PurchaseQuotationDocument
    document: DocumentAsset


class PurchaseQuotationDocumentService:
    def __init__(
        self,
        repository: PurchaseQuotationDocumentRepository,
        documents: DocumentService,
        audit: AuditService,
    ) -> None:
        self._repository = repository
        self._documents = documents
        self._audit = audit

    async def initiate(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        quotation_id: uuid.UUID,
        data: InitiateDocumentInput,
    ) -> PurchaseQuotationDocumentUpload:
        reference = await self._require_uploadable(company_id, quotation_id)
        ticket = await self._documents.initiate(data)
        attachment = PurchaseQuotationDocument(
            id=uuid.uuid4(),
            company_id=company_id,
            purchase_quotation_id=reference.quotation_id,
            document_id=ticket.document.id,
            file_name=ticket.document.original_filename,
            file_type=ticket.document.declared_content_type,
        )
        attachment = await self._repository.add_document(attachment)
        await self._audit.record(
            action="PURCHASE_QUOTATION_DOCUMENT_INITIATED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="purchase_quotations",
            resource_id=str(quotation_id),
            after_state={"document_id": str(ticket.document.id), "file_name": attachment.file_name},
            required=True,
        )
        return PurchaseQuotationDocumentUpload(ticket, attachment)

    async def complete(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        quotation_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> PurchaseQuotationDocumentView:
        await self._require_uploadable(company_id, quotation_id)
        attachment = await self._require_attachment(company_id, quotation_id, document_id)
        document = await self._documents.complete(company_id, document_id, actor_id)
        if attachment.uploaded_at is not None:
            return PurchaseQuotationDocumentView(attachment, document)

        uploaded_at = datetime.now(UTC)
        saved = await self._repository.mark_uploaded(
            company_id,
            quotation_id,
            document_id,
            file_type=document.detected_content_type or document.declared_content_type,
            uploaded_at=uploaded_at,
        )
        if saved is None:
            raise NotFoundError(
                "Documento adjunto a la cotización no encontrado.",
                code="purchase_quotation_document_not_found",
            )
        await self._audit.record(
            action="PURCHASE_QUOTATION_DOCUMENT_COMPLETED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="purchase_quotations",
            resource_id=str(quotation_id),
            after_state={
                "document_id": str(document_id),
                "uploaded_at": uploaded_at.isoformat(),
            },
            required=True,
        )
        return PurchaseQuotationDocumentView(saved, document)

    async def list_documents(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID
    ) -> list[PurchaseQuotationDocumentView]:
        await self._require_quotation(company_id, quotation_id)
        attachments = await self._repository.list_documents(company_id, quotation_id)
        views = []
        for attachment in attachments:
            document = await self._documents.get(company_id, attachment.document_id)
            views.append(PurchaseQuotationDocumentView(attachment, document))
        return views

    async def download_url(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        quotation_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> tuple[str, datetime]:
        await self._require_attachment(company_id, quotation_id, document_id)
        return await self._documents.download_url(company_id, document_id, actor_id)

    async def remove(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        quotation_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> PurchaseQuotationDocument:
        await self._require_uploadable(company_id, quotation_id)
        attachment = await self._require_attachment(company_id, quotation_id, document_id)
        detached_at = datetime.now(UTC)
        detached = await self._repository.detach_document(
            company_id,
            quotation_id,
            document_id,
            deleted_at=detached_at,
        )
        if detached is None:
            raise NotFoundError(
                "Documento adjunto a la cotización no encontrado.",
                code="purchase_quotation_document_not_found",
            )
        await self._audit.record(
            action="PURCHASE_QUOTATION_DOCUMENT_DETACHED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="purchase_quotations",
            resource_id=str(quotation_id),
            before_state={
                "document_id": str(document_id),
                "file_name": attachment.file_name,
            },
            after_state={"detached_at": detached_at.isoformat()},
            required=True,
        )
        return detached

    async def _require_uploadable(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID
    ) -> PurchaseQuotationDocumentReference:
        reference = await self._require_quotation(company_id, quotation_id)
        if reference.status not in UPLOADABLE_STATUSES:
            raise BusinessRuleError(
                "Los documentos solo se pueden modificar mientras la cotización está enviada o en evaluación.",
                code="purchase_quotation_document_not_editable",
            )
        return reference

    async def _require_quotation(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID
    ) -> PurchaseQuotationDocumentReference:
        reference = await self._repository.get_quotation_reference(company_id, quotation_id)
        if reference is None:
            raise NotFoundError(
                "Cotización de compra no encontrada.", code="purchase_quotation_not_found"
            )
        return reference

    async def _require_attachment(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> PurchaseQuotationDocument:
        attachment = await self._repository.get_document(company_id, quotation_id, document_id)
        if attachment is None:
            raise NotFoundError(
                "Documento adjunto a la cotización no encontrado.",
                code="purchase_quotation_document_not_found",
            )
        return attachment
