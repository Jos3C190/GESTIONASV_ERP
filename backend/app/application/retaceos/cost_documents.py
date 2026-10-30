"""Secure file lifecycle for receipts attached to actual retaceo costs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.audit.audit_service import AuditService
from app.application.documents.service import DocumentService, InitiateDocumentInput, UploadTicket
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.document import DocumentAsset
from app.domain.entities.retaceo import RetaceoCostDocument, RetaceoStatus
from app.domain.ports.retaceo_repository import (
    RetaceoCostDocumentReference,
    RetaceoCostReference,
    RetaceoRepository,
)


@dataclass(frozen=True, slots=True)
class RetaceoCostDocumentUpload:
    ticket: UploadTicket
    attachment: RetaceoCostDocument


@dataclass(frozen=True, slots=True)
class RetaceoCostDocumentView:
    attachment: RetaceoCostDocument
    document: DocumentAsset


class RetaceoCostDocumentService:
    def __init__(
        self,
        repository: RetaceoRepository,
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
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
        data: InitiateDocumentInput,
    ) -> RetaceoCostDocumentUpload:
        await self._require_editable_cost(company_id, retaceo_id, cost_id)
        ticket = await self._documents.initiate(data)
        attachment = RetaceoCostDocument(
            id=uuid.uuid4(),
            retaceo_cost_id=cost_id,
            document_id=ticket.document.id,
            file_name=ticket.document.original_filename,
            file_type=ticket.document.declared_content_type,
        )
        attachment = await self._repository.add_cost_document(attachment, company_id)
        await self._audit.record(
            action="RETACEO_COST_DOCUMENT_INITIATED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="retaceo_costs",
            resource_id=str(cost_id),
            after_state={
                "retaceo_id": str(retaceo_id),
                "document_id": str(ticket.document.id),
                "file_name": attachment.file_name,
            },
            required=True,
        )
        return RetaceoCostDocumentUpload(ticket, attachment)

    async def complete(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> RetaceoCostDocumentView:
        reference = await self._require_attachment(company_id, retaceo_id, cost_id, document_id)
        if reference.status is not RetaceoStatus.DRAFT:
            raise BusinessRuleError(
                "Solo se pueden completar comprobantes mientras el retaceo está en borrador.",
                code="retaceo_cost_document_not_editable",
            )
        document = await self._documents.complete(company_id, document_id, actor_id)
        if reference.document.uploaded_at is not None:
            return RetaceoCostDocumentView(reference.document, document)
        uploaded_at = datetime.now(UTC)
        attachment = await self._repository.mark_cost_document_uploaded(
            company_id,
            retaceo_id,
            cost_id,
            document_id,
            file_type=document.detected_content_type or document.declared_content_type,
            uploaded_at=uploaded_at,
        )
        if attachment is None:
            raise NotFoundError(
                "Comprobante del gasto no encontrado.",
                code="retaceo_cost_document_not_found",
            )
        await self._audit.record(
            action="RETACEO_COST_DOCUMENT_COMPLETED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="retaceo_costs",
            resource_id=str(cost_id),
            after_state={
                "retaceo_id": str(retaceo_id),
                "document_id": str(document_id),
                "uploaded_at": uploaded_at.isoformat(),
            },
            required=True,
        )
        return RetaceoCostDocumentView(attachment, document)

    async def list_documents(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
    ) -> list[RetaceoCostDocumentView]:
        await self._require_cost(company_id, retaceo_id, cost_id)
        attachments = await self._repository.list_cost_documents(company_id, retaceo_id, cost_id)
        views: list[RetaceoCostDocumentView] = []
        for attachment in attachments:
            document = await self._documents.get(company_id, attachment.document_id)
            views.append(RetaceoCostDocumentView(attachment, document))
        return views

    async def remove(
        self,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> RetaceoCostDocument:
        await self._require_editable_cost(company_id, retaceo_id, cost_id)
        reference = await self._require_attachment(company_id, retaceo_id, cost_id, document_id)
        deleted_at = datetime.now(UTC)
        attachment = await self._repository.soft_delete_cost_document(
            company_id,
            retaceo_id,
            cost_id,
            document_id,
            deleted_at=deleted_at,
        )
        if attachment is None:
            raise NotFoundError(
                "Comprobante del gasto no encontrado.",
                code="retaceo_cost_document_not_found",
            )
        await self._audit.record(
            action="RETACEO_COST_DOCUMENT_DETACHED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="retaceo_costs",
            resource_id=str(cost_id),
            before_state={
                "retaceo_id": str(retaceo_id),
                "cost_id": str(cost_id),
                "document_id": str(document_id),
                "file_name": reference.document.file_name,
            },
            after_state={"detached_at": deleted_at.isoformat()},
            required=True,
        )
        return attachment

    async def download_url(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> tuple[str, datetime]:
        await self._require_attachment(company_id, retaceo_id, cost_id, document_id)
        return await self._documents.download_url(company_id, document_id, actor_id)

    async def _require_editable_cost(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
    ) -> RetaceoCostReference:
        reference = await self._require_cost(company_id, retaceo_id, cost_id)
        if reference.status is not RetaceoStatus.DRAFT or not reference.is_active:
            raise BusinessRuleError(
                "Solo se pueden adjuntar comprobantes a un gasto activo de un retaceo en borrador.",
                code="retaceo_cost_document_not_editable",
            )
        return reference

    async def _require_cost(
        self, company_id: uuid.UUID, retaceo_id: uuid.UUID, cost_id: uuid.UUID
    ) -> RetaceoCostReference:
        reference = await self._repository.get_cost_reference(company_id, retaceo_id, cost_id)
        if reference is None:
            raise NotFoundError("Gasto de retaceo no encontrado.", code="retaceo_cost_not_found")
        return reference

    async def _require_attachment(
        self,
        company_id: uuid.UUID,
        retaceo_id: uuid.UUID,
        cost_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> RetaceoCostDocumentReference:
        reference = await self._repository.get_cost_document(
            company_id, retaceo_id, cost_id, document_id
        )
        if reference is None:
            raise NotFoundError(
                "Comprobante del gasto no encontrado.",
                code="retaceo_cost_document_not_found",
            )
        return reference
