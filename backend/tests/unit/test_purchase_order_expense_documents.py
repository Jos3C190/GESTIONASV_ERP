from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.application.documents.service import InitiateDocumentInput, UploadTicket
from app.application.purchase_orders.expense_documents import PurchaseOrderExpenseDocumentService
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.document import DocumentAsset
from app.domain.entities.purchase_order import PurchaseOrderStatus
from app.domain.entities.purchase_order_expense_document import PurchaseOrderExpenseDocument
from app.domain.ports.purchase_order_expense_document_repository import (
    PurchaseOrderExpenseReference,
)


class FakeExpenseDocumentRepository:
    def __init__(self) -> None:
        self.references: dict[
            tuple[uuid.UUID, uuid.UUID, uuid.UUID], PurchaseOrderExpenseReference
        ] = {}
        self.attachments: dict[uuid.UUID, PurchaseOrderExpenseDocument] = {}

    async def get_expense_reference(self, company_id, order_id, expense_id):
        return self.references.get((company_id, order_id, expense_id))

    async def add_document(self, attachment):
        self.attachments[attachment.document_id] = attachment
        return attachment

    async def get_document(self, company_id, order_id, expense_id, document_id):
        attachment = self.attachments.get(document_id)
        if (
            attachment is None
            or attachment.company_id != company_id
            or attachment.purchase_order_expense_id != expense_id
        ):
            return None
        reference = self.references.get((company_id, order_id, expense_id))
        return attachment if reference is not None else None

    async def list_documents(self, company_id, order_id, expense_id):
        reference = self.references.get((company_id, order_id, expense_id))
        if reference is None:
            return ()
        return tuple(
            attachment
            for attachment in self.attachments.values()
            if attachment.company_id == company_id
            and attachment.purchase_order_expense_id == expense_id
        )

    async def mark_uploaded(
        self,
        company_id,
        order_id,
        expense_id,
        document_id,
        *,
        file_type,
        uploaded_at,
    ):
        attachment = await self.get_document(
            company_id,
            order_id,
            expense_id,
            document_id,
        )
        if attachment is None:
            return None
        updated = replace(
            attachment,
            file_type=file_type,
            uploaded_at=uploaded_at,
        )
        self.attachments[document_id] = updated
        return updated


class FakeDocumentService:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, DocumentAsset] = {}
        self.initiated = 0

    async def initiate(self, data: InitiateDocumentInput) -> UploadTicket:
        self.initiated += 1
        document = DocumentAsset(
            id=uuid.uuid4(),
            company_id=data.company_id,
            original_filename=data.filename,
            extension=".pdf",
            declared_content_type=data.content_type,
            size_bytes=data.size_bytes,
            checksum_sha256=data.checksum_sha256,
            bucket="documents",
            object_key=f"documents/{uuid.uuid4()}",
            uploaded_by=data.actor_id,
            upload_expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        self.items[document.id] = document
        return UploadTicket(
            document=document,
            upload_url="https://storage.test/upload",
            required_headers={"content-type": data.content_type},
            expires_at=document.upload_expires_at,
        )

    async def get(self, company_id: uuid.UUID, document_id: uuid.UUID) -> DocumentAsset:
        document = self.items.get(document_id)
        if document is None or document.company_id != company_id:
            raise NotFoundError("Documento no encontrado.", code="document_not_found")
        return document

    async def complete(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> DocumentAsset:
        del actor_id
        document = await self.get(company_id, document_id)
        document.status = "active"
        document.detected_content_type = "application/pdf"
        document.scanned_at = datetime.now(UTC)
        return document

    async def download_url(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> tuple[str, datetime]:
        del actor_id
        document = await self.get(company_id, document_id)
        if document.status != "active":
            raise BusinessRuleError("Documento no disponible.", code="document_not_active")
        return (
            f"https://storage.test/download/{document.id}",
            datetime.now(UTC) + timedelta(minutes=5),
        )


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def record(self, **kwargs) -> None:
        self.events.append(kwargs)


def _input(company_id: uuid.UUID, actor_id: uuid.UUID) -> InitiateDocumentInput:
    return InitiateDocumentInput(
        company_id=company_id,
        actor_id=actor_id,
        filename="flete.pdf",
        content_type="application/pdf",
        size_bytes=128,
        checksum_sha256="a" * 64,
    )


@pytest.mark.asyncio
async def test_expense_document_requires_stable_expense_before_upload() -> None:
    company_id = uuid.uuid4()
    order_id = uuid.uuid4()
    expense_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    repository = FakeExpenseDocumentRepository()
    repository.references[(company_id, order_id, expense_id)] = PurchaseOrderExpenseReference(
        order_id=order_id,
        expense_id=expense_id,
        status=PurchaseOrderStatus.DRAFT,
    )
    documents = FakeDocumentService()
    service = PurchaseOrderExpenseDocumentService(repository, documents, FakeAudit())

    with pytest.raises(BusinessRuleError) as exc_info:
        await service.initiate(order_id, expense_id, _input(company_id, actor_id))

    assert exc_info.value.code == "purchase_order_expense_document_requires_stable_expense"
    assert documents.initiated == 0


@pytest.mark.asyncio
async def test_expense_document_upload_complete_list_and_download() -> None:
    company_id = uuid.uuid4()
    order_id = uuid.uuid4()
    expense_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    repository = FakeExpenseDocumentRepository()
    repository.references[(company_id, order_id, expense_id)] = PurchaseOrderExpenseReference(
        order_id=order_id,
        expense_id=expense_id,
        status=PurchaseOrderStatus.PENDING_APPROVAL,
    )
    documents = FakeDocumentService()
    audit = FakeAudit()
    service = PurchaseOrderExpenseDocumentService(repository, documents, audit)

    initiated = await service.initiate(order_id, expense_id, _input(company_id, actor_id))
    completed = await service.complete(
        company_id,
        order_id,
        expense_id,
        initiated.ticket.document.id,
        actor_id,
    )
    listed = await service.list_documents(company_id, order_id, expense_id)
    url, _expires = await service.download_url(
        company_id,
        order_id,
        expense_id,
        initiated.ticket.document.id,
        actor_id,
    )

    assert initiated.attachment.uploaded_at is None
    assert completed.attachment.uploaded_at is not None
    assert completed.attachment.file_type == "application/pdf"
    assert completed.document.status == "active"
    assert [item.attachment.document_id for item in listed] == [initiated.ticket.document.id]
    assert str(initiated.ticket.document.id) in url
    assert {event["action"] for event in audit.events} == {
        "PURCHASE_ORDER_EXPENSE_DOCUMENT_INITIATED",
        "PURCHASE_ORDER_EXPENSE_DOCUMENT_COMPLETED",
    }


@pytest.mark.asyncio
async def test_expense_document_scope_fails_closed() -> None:
    company_id = uuid.uuid4()
    order_id = uuid.uuid4()
    expense_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    service = PurchaseOrderExpenseDocumentService(
        FakeExpenseDocumentRepository(),
        FakeDocumentService(),
        FakeAudit(),
    )

    with pytest.raises(NotFoundError) as exc_info:
        await service.initiate(order_id, expense_id, _input(company_id, actor_id))

    assert exc_info.value.code == "purchase_order_expense_not_found"


@pytest.mark.asyncio
async def test_expense_document_complete_is_idempotent() -> None:
    company_id = uuid.uuid4()
    order_id = uuid.uuid4()
    expense_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    repository = FakeExpenseDocumentRepository()
    repository.references[(company_id, order_id, expense_id)] = PurchaseOrderExpenseReference(
        order_id=order_id,
        expense_id=expense_id,
        status=PurchaseOrderStatus.PENDING_APPROVAL,
    )
    documents = FakeDocumentService()
    audit = FakeAudit()
    service = PurchaseOrderExpenseDocumentService(repository, documents, audit)

    initiated = await service.initiate(order_id, expense_id, _input(company_id, actor_id))
    first = await service.complete(
        company_id,
        order_id,
        expense_id,
        initiated.ticket.document.id,
        actor_id,
    )
    second = await service.complete(
        company_id,
        order_id,
        expense_id,
        initiated.ticket.document.id,
        actor_id,
    )

    assert second.attachment.uploaded_at == first.attachment.uploaded_at
    completed_events = [
        event
        for event in audit.events
        if event["action"] == "PURCHASE_ORDER_EXPENSE_DOCUMENT_COMPLETED"
    ]
    assert len(completed_events) == 1
