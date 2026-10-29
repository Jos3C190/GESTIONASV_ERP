from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.application.documents.service import InitiateDocumentInput, UploadTicket
from app.application.purchase_quotations.documents import PurchaseQuotationDocumentService
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.document import DocumentAsset
from app.domain.entities.purchase_quotation import PurchaseQuotationStatus
from app.domain.entities.purchase_quotation_document import PurchaseQuotationDocument
from app.domain.ports.purchase_quotation_document_repository import (
    PurchaseQuotationDocumentReference,
)


class FakeQuotationDocumentRepository:
    def __init__(self) -> None:
        self.references: dict[tuple[uuid.UUID, uuid.UUID], PurchaseQuotationDocumentReference] = {}
        self.attachments: dict[uuid.UUID, PurchaseQuotationDocument] = {}

    async def get_quotation_reference(self, company_id, quotation_id):
        return self.references.get((company_id, quotation_id))

    async def add_document(self, attachment):
        self.attachments[attachment.document_id] = attachment
        return attachment

    async def get_document(self, company_id, quotation_id, document_id):
        attachment = self.attachments.get(document_id)
        if (
            attachment is None
            or attachment.company_id != company_id
            or attachment.purchase_quotation_id != quotation_id
            or attachment.deleted_at is not None
        ):
            return None
        return attachment

    async def list_documents(self, company_id, quotation_id):
        return tuple(
            attachment
            for attachment in self.attachments.values()
            if attachment.company_id == company_id
            and attachment.purchase_quotation_id == quotation_id
            and attachment.deleted_at is None
        )

    async def mark_uploaded(
        self, company_id, quotation_id, document_id, *, file_type, uploaded_at
    ):
        attachment = await self.get_document(company_id, quotation_id, document_id)
        if attachment is None:
            return None
        updated = replace(attachment, file_type=file_type, uploaded_at=uploaded_at)
        self.attachments[document_id] = updated
        return updated

    async def detach_document(
        self, company_id, quotation_id, document_id, *, deleted_at
    ):
        attachment = await self.get_document(company_id, quotation_id, document_id)
        if attachment is None:
            return None
        detached = replace(attachment, deleted_at=deleted_at)
        self.attachments[document_id] = detached
        return detached


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

    async def get(self, company_id, document_id):
        document = self.items.get(document_id)
        if document is None or document.company_id != company_id:
            raise NotFoundError("Documento no encontrado.", code="document_not_found")
        return document

    async def complete(self, company_id, document_id, actor_id):
        del actor_id
        document = await self.get(company_id, document_id)
        document.status = "active"
        document.detected_content_type = "application/pdf"
        document.scanned_at = datetime.now(UTC)
        return document

    async def download_url(self, company_id, document_id, actor_id):
        del actor_id
        document = await self.get(company_id, document_id)
        if document.status != "active":
            raise BusinessRuleError("Documento no disponible.", code="document_not_active")
        return f"https://storage.test/download/{document.id}", datetime.now(UTC) + timedelta(minutes=5)


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def record(self, **kwargs) -> None:
        self.events.append(kwargs)


def _input(company_id: uuid.UUID, actor_id: uuid.UUID) -> InitiateDocumentInput:
    return InitiateDocumentInput(
        company_id=company_id,
        actor_id=actor_id,
        filename="oferta.pdf",
        content_type="application/pdf",
        size_bytes=128,
        checksum_sha256="a" * 64,
    )


@pytest.mark.asyncio
async def test_supplier_offer_document_upload_complete_list_and_download() -> None:
    company_id = uuid.uuid4()
    quotation_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    repository = FakeQuotationDocumentRepository()
    repository.references[(company_id, quotation_id)] = PurchaseQuotationDocumentReference(
        quotation_id=quotation_id,
        status=PurchaseQuotationStatus.REQUESTED,
    )
    documents = FakeDocumentService()
    audit = FakeAudit()
    service = PurchaseQuotationDocumentService(repository, documents, audit)

    initiated = await service.initiate(
        company_id, actor_id, quotation_id, _input(company_id, actor_id)
    )
    completed = await service.complete(
        company_id, actor_id, quotation_id, initiated.ticket.document.id
    )
    listed = await service.list_documents(company_id, quotation_id)
    url, _expires = await service.download_url(
        company_id, actor_id, quotation_id, initiated.ticket.document.id
    )

    assert initiated.attachment.uploaded_at is None
    assert completed.attachment.uploaded_at is not None
    assert completed.document.status == "active"
    assert [item.attachment.document_id for item in listed] == [initiated.ticket.document.id]
    assert str(initiated.ticket.document.id) in url
    assert {event["action"] for event in audit.events} == {
        "PURCHASE_QUOTATION_DOCUMENT_INITIATED",
        "PURCHASE_QUOTATION_DOCUMENT_COMPLETED",
    }


@pytest.mark.asyncio
async def test_supplier_offer_document_can_be_detached_with_audit_history() -> None:
    company_id = uuid.uuid4()
    quotation_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    repository = FakeQuotationDocumentRepository()
    repository.references[(company_id, quotation_id)] = PurchaseQuotationDocumentReference(
        quotation_id=quotation_id,
        status=PurchaseQuotationStatus.UNDER_EVALUATION,
    )
    documents = FakeDocumentService()
    audit = FakeAudit()
    service = PurchaseQuotationDocumentService(repository, documents, audit)

    initiated = await service.initiate(
        company_id, actor_id, quotation_id, _input(company_id, actor_id)
    )
    await service.complete(company_id, actor_id, quotation_id, initiated.ticket.document.id)
    detached = await service.remove(
        company_id, actor_id, quotation_id, initiated.ticket.document.id
    )

    assert detached.deleted_at is not None
    assert await service.list_documents(company_id, quotation_id) == []
    detach_event = next(
        event for event in audit.events if event["action"] == "PURCHASE_QUOTATION_DOCUMENT_DETACHED"
    )
    assert detach_event["user_id"] == actor_id
    assert detach_event["before_state"] == {
        "document_id": str(initiated.ticket.document.id),
        "file_name": "oferta.pdf",
    }
    assert detach_event["after_state"]["detached_at"] == detached.deleted_at.isoformat()

    with pytest.raises(NotFoundError) as exc_info:
        await service.remove(company_id, actor_id, quotation_id, initiated.ticket.document.id)

    assert exc_info.value.code == "purchase_quotation_document_not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [PurchaseQuotationStatus.DRAFT, PurchaseQuotationStatus.SELECTED],
)
async def test_supplier_offer_document_detach_rejects_closed_or_unsent_quotes(status) -> None:
    company_id = uuid.uuid4()
    quotation_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    repository = FakeQuotationDocumentRepository()
    repository.references[(company_id, quotation_id)] = PurchaseQuotationDocumentReference(
        quotation_id=quotation_id,
        status=status,
    )
    service = PurchaseQuotationDocumentService(
        repository, FakeDocumentService(), FakeAudit()
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        await service.remove(company_id, actor_id, quotation_id, uuid.uuid4())

    assert exc_info.value.code == "purchase_quotation_document_not_editable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [PurchaseQuotationStatus.DRAFT, PurchaseQuotationStatus.SELECTED],
)
async def test_supplier_offer_document_upload_rejects_closed_or_unsent_quotes(status) -> None:
    company_id = uuid.uuid4()
    quotation_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    repository = FakeQuotationDocumentRepository()
    repository.references[(company_id, quotation_id)] = PurchaseQuotationDocumentReference(
        quotation_id=quotation_id,
        status=status,
    )
    documents = FakeDocumentService()
    service = PurchaseQuotationDocumentService(repository, documents, FakeAudit())

    with pytest.raises(BusinessRuleError) as exc_info:
        await service.initiate(company_id, actor_id, quotation_id, _input(company_id, actor_id))

    assert exc_info.value.code == "purchase_quotation_document_not_editable"
    assert documents.initiated == 0


@pytest.mark.asyncio
async def test_supplier_offer_document_scope_fails_closed() -> None:
    company_id = uuid.uuid4()
    quotation_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    service = PurchaseQuotationDocumentService(
        FakeQuotationDocumentRepository(), FakeDocumentService(), FakeAudit()
    )

    with pytest.raises(NotFoundError) as exc_info:
        await service.initiate(company_id, actor_id, quotation_id, _input(company_id, actor_id))

    assert exc_info.value.code == "purchase_quotation_not_found"
