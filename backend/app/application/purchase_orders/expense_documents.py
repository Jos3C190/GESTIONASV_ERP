"""Use cases for documents attached to purchase-order expenses."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.audit.audit_service import AuditService
from app.application.documents.service import DocumentService, InitiateDocumentInput, UploadTicket
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.document import DocumentAsset
from app.domain.entities.purchase_order import PurchaseOrderStatus
from app.domain.entities.purchase_order_expense_document import PurchaseOrderExpenseDocument
from app.domain.ports.purchase_order_expense_document_repository import (
    PurchaseOrderExpenseDocumentRepository,
    PurchaseOrderExpenseReference,
)


@dataclass(frozen=True, slots=True)
class PurchaseOrderExpenseDocumentUpload:
    ticket: UploadTicket
    attachment: PurchaseOrderExpenseDocument


@dataclass(frozen=True, slots=True)
class PurchaseOrderExpenseDocumentView:
    attachment: PurchaseOrderExpenseDocument
    document: DocumentAsset


class PurchaseOrderExpenseDocumentService:
    def __init__(
        self,
        repository: PurchaseOrderExpenseDocumentRepository,
        documents: DocumentService,
        audit: AuditService,
    ) -> None:
        self._repository = repository
        self._documents = documents
        self._audit = audit

    async def initiate(
        self,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
        data: InitiateDocumentInput,
    ) -> PurchaseOrderExpenseDocumentUpload:
        reference = await self._require_expense(data.company_id, order_id, expense_id)
        if reference.status is PurchaseOrderStatus.DRAFT:
            raise BusinessRuleError(
                "La orden debe enviarse a aprobación antes de adjuntar documentos al gasto.",
                code="purchase_order_expense_document_requires_stable_expense",
            )

        ticket = await self._documents.initiate(data)
        attachment = PurchaseOrderExpenseDocument(
            id=uuid.uuid4(),
            company_id=data.company_id,
            purchase_order_expense_id=expense_id,
            document_id=ticket.document.id,
            file_name=ticket.document.original_filename,
            file_type=ticket.document.declared_content_type,
        )
        attachment = await self._repository.add_document(attachment)
        await self._audit.record(
            action="PURCHASE_ORDER_EXPENSE_DOCUMENT_INITIATED",
            user_id=data.actor_id,
            company_id=data.company_id,
            resource_type="purchase_order_expenses",
            resource_id=str(expense_id),
            after_state={
                "order_id": str(order_id),
                "document_id": str(ticket.document.id),
                "file_name": attachment.file_name,
            },
            required=True,
        )
        return PurchaseOrderExpenseDocumentUpload(ticket=ticket, attachment=attachment)

    async def complete(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> PurchaseOrderExpenseDocumentView:
        attachment = await self._require_attachment(company_id, order_id, expense_id, document_id)
        document = await self._documents.complete(company_id, document_id, actor_id)
        if attachment.uploaded_at is not None:
            return PurchaseOrderExpenseDocumentView(
                attachment=attachment,
                document=document,
            )
        uploaded_at = datetime.now(UTC)
        saved_attachment = await self._repository.mark_uploaded(
            company_id,
            order_id,
            expense_id,
            document_id,
            file_type=document.detected_content_type or document.declared_content_type,
            uploaded_at=uploaded_at,
        )
        if saved_attachment is None:
            raise NotFoundError(
                "Documento del gasto no encontrado.",
                code="purchase_order_expense_document_not_found",
            )
        await self._audit.record(
            action="PURCHASE_ORDER_EXPENSE_DOCUMENT_COMPLETED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="purchase_order_expenses",
            resource_id=str(expense_id),
            after_state={
                "order_id": str(order_id),
                "document_id": str(document_id),
                "uploaded_at": uploaded_at.isoformat(),
            },
            required=True,
        )
        return PurchaseOrderExpenseDocumentView(attachment=saved_attachment, document=document)

    async def list_documents(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
    ) -> list[PurchaseOrderExpenseDocumentView]:
        await self._require_expense(company_id, order_id, expense_id)
        attachments = await self._repository.list_documents(company_id, order_id, expense_id)
        views: list[PurchaseOrderExpenseDocumentView] = []
        for attachment in attachments:
            document = await self._documents.get(company_id, attachment.document_id)
            views.append(PurchaseOrderExpenseDocumentView(attachment, document))
        return views

    async def download_url(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> tuple[str, datetime]:
        await self._require_attachment(company_id, order_id, expense_id, document_id)
        return await self._documents.download_url(company_id, document_id, actor_id)

    async def _require_expense(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
    ) -> PurchaseOrderExpenseReference:
        reference = await self._repository.get_expense_reference(company_id, order_id, expense_id)
        if reference is None:
            raise NotFoundError(
                "Gasto de orden de compra no encontrado.",
                code="purchase_order_expense_not_found",
            )
        return reference

    async def _require_attachment(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> PurchaseOrderExpenseDocument:
        attachment = await self._repository.get_document(
            company_id,
            order_id,
            expense_id,
            document_id,
        )
        if attachment is None:
            raise NotFoundError(
                "Documento del gasto no encontrado.",
                code="purchase_order_expense_document_not_found",
            )
        return attachment
