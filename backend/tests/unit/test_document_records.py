from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from app.api.v1.schemas.documents import CreateDocumentCategoryIn
from app.application.documents import (
    DocumentMetadataInput,
    DocumentRecordService,
    InitiateDocumentInput,
    UploadTicket,
)
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.entities.document import DocumentAsset
from app.domain.entities.document_record import DocumentCategory, DocumentRecord
from app.domain.entities.employee import Employee
from pydantic import ValidationError as PydanticValidationError

COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_COMPANY_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ACTOR_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
EMPLOYEE_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


def category(module: str, code: str = "other") -> DocumentCategory:
    return DocumentCategory(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"{module}:{code}"),
        company_id=COMPANY_ID,
        module=module,
        code=code,
        name=code.title(),
        group_name="General",
    )


def asset(document_id: uuid.UUID, *, status: str = "pending_upload") -> DocumentAsset:
    return DocumentAsset(
        id=document_id,
        company_id=COMPANY_ID,
        original_filename="contrato.pdf",
        extension=".pdf",
        declared_content_type="application/pdf",
        size_bytes=10,
        checksum_sha256="a" * 64,
        bucket="erp-documents",
        object_key=f"companies/{COMPANY_ID}/documents/{document_id}/payload",
        status=status,
        upload_expires_at=datetime.now(UTC) + timedelta(hours=1),
        uploaded_by=ACTOR_ID,
    )


class FakeDocumentService:
    def __init__(self) -> None:
        self.assets: dict[uuid.UUID, DocumentAsset] = {}

    async def initiate(self, data: InitiateDocumentInput) -> UploadTicket:
        document_id = uuid.uuid4()
        document = asset(document_id)
        document.company_id = data.company_id
        document.original_filename = data.filename
        document.extension = ".pdf"
        self.assets[document_id] = document
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        return UploadTicket(
            document, "https://storage/upload", {"Content-Type": data.content_type}, expires_at
        )

    async def enrich(self, document: DocumentAsset) -> DocumentAsset:
        return document

    async def complete(
        self, company_id: uuid.UUID, document_id: uuid.UUID, actor_id: uuid.UUID
    ) -> DocumentAsset:
        document = self.assets[document_id]
        document.status = "active"
        return document


class FakeRecords:
    def __init__(self) -> None:
        self.categories_by_module = {
            "general": [category("general")],
            "employees": [category("employees")],
        }
        self.items: dict[uuid.UUID, DocumentRecord] = {}

    async def categories(
        self, company_id: uuid.UUID, *, module: str | None = None, include_inactive: bool = False
    ):
        del company_id
        items = self.categories_by_module.get(module or "general", [])
        return items if include_inactive else [item for item in items if item.is_active]

    async def get_category(
        self, category_id: uuid.UUID, company_id: uuid.UUID, *, include_inactive: bool = False
    ):
        for item in sum(self.categories_by_module.values(), []):
            if (
                item.id == category_id
                and item.company_id == company_id
                and (include_inactive or item.is_active)
            ):
                return item
        return None

    async def add(self, record: DocumentRecord) -> DocumentRecord:
        self.items[record.document_id] = record
        return record

    async def get(self, document_id: uuid.UUID, *, include_deleted: bool = False):
        del include_deleted
        return self.items.get(document_id)

    async def save(self, record: DocumentRecord) -> DocumentRecord:
        self.items[record.document_id] = record
        return record

    async def list(self, company_id: uuid.UUID, **filters):
        items = [item for item in self.items.values() if item.company_id == company_id]
        if filters.get("module"):
            items = [item for item in items if item.module == filters["module"]]
        return items, len(items)

    async def list_versions(self, document_id: uuid.UUID):
        group = self.items[document_id].version_group_id
        return [item for item in self.items.values() if item.version_group_id == group]

    async def next_version_number(self, version_group_id: uuid.UUID) -> int:
        return (
            max(
                (
                    item.version_number
                    for item in self.items.values()
                    if item.version_group_id == version_group_id
                ),
                default=0,
            )
            + 1
        )

    async def set_current_version(self, *, version_group_id: uuid.UUID, document_id: uuid.UUID):
        for item in self.items.values():
            if item.version_group_id == version_group_id:
                item.is_current = item.document_id == document_id
        return self.items[document_id]


class FakeEmployees:
    async def get_by_id(self, employee_id: uuid.UUID):
        if employee_id != EMPLOYEE_ID:
            return None
        return Employee(
            id=EMPLOYEE_ID,
            company_id=COMPANY_ID,
            employee_code="EMP-001",
            first_name="Ana",
            last_name="Pérez",
        )


class FakeAudit:
    def __init__(self) -> None:
        self.actions: list[str] = []

    async def record(self, *, action: str, **kwargs: object) -> None:
        del kwargs
        self.actions.append(action)


def make_service() -> tuple[DocumentRecordService, FakeRecords, FakeDocumentService, FakeAudit]:
    records = FakeRecords()
    documents = FakeDocumentService()
    audit = FakeAudit()
    return (
        DocumentRecordService(documents, records, FakeEmployees(), audit),
        records,
        documents,
        audit,
    )


def input_data(company_id: uuid.UUID = COMPANY_ID) -> InitiateDocumentInput:
    return InitiateDocumentInput(
        company_id=company_id,
        actor_id=ACTOR_ID,
        filename="contrato.pdf",
        content_type="application/pdf",
        size_bytes=10,
        checksum_sha256="a" * 64,
    )


@pytest.mark.parametrize(
    ("issued_on", "expires_on"),
    [(date(2026, 2, 1), date(2026, 1, 31)), (date(2026, 2, 1), date(2026, 2, 1))],
)
async def test_metadata_rejects_expiry_before_issue(issued_on: date, expires_on: date) -> None:
    service, _records, _documents, _audit = make_service()
    metadata = DocumentMetadataInput(issued_on=issued_on, expires_on=expires_on)
    if expires_on == issued_on:
        await service.initiate_general(input_data(), metadata)
    else:
        with pytest.raises(ValidationError, match="vencimiento"):
            await service.initiate_general(input_data(), metadata)


async def test_employee_record_has_owner_and_normalized_unique_tags() -> None:
    service, records, _documents, _audit = make_service()
    upload = await service.initiate_employee(
        EMPLOYEE_ID,
        input_data(),
        DocumentMetadataInput(
            tags=("  contrato  ", "Contrato", "2026"), confidentiality="internal"
        ),
    )
    assert upload.record.module == "employees"
    assert upload.record.owner_id == EMPLOYEE_ID
    assert upload.record.tags == ["contrato", "2026"]
    assert upload.record.title == "contrato.pdf"
    assert records.items[upload.record.document_id].confidentiality == "internal"


async def test_metadata_rejects_more_than_ten_tags() -> None:
    service, _records, _documents, _audit = make_service()
    with pytest.raises(ValidationError, match="máximo 10"):
        await service.initiate_general(
            input_data(), DocumentMetadataInput(tags=tuple(f"tag-{index}" for index in range(11)))
        )


async def test_employee_category_cannot_be_used_for_general_document() -> None:
    service, _records, _documents, _audit = make_service()
    with pytest.raises(ValidationError, match="categoría"):
        await service.initiate_general(
            input_data(), DocumentMetadataInput(category_id=category("employees").id)
        )


async def test_replace_serializes_version_number_and_preserves_previous() -> None:
    service, records, documents, audit = make_service()
    first = await service.initiate_general(
        input_data(), DocumentMetadataInput(title="Contrato 2026")
    )
    documents.assets[first.record.document_id].status = "active"
    records.items[first.record.document_id].asset = documents.assets[first.record.document_id]

    replacement = await service.replace(
        COMPANY_ID,
        first.record.document_id,
        ACTOR_ID,
        input_data(),
        DocumentMetadataInput(title="Contrato 2027"),
    )
    assert replacement.record.version_group_id == first.record.version_group_id
    assert replacement.record.version_number == 2
    assert replacement.record.is_current is False
    assert replacement.record.replaces_document_id == first.record.document_id
    assert records.items[first.record.document_id].is_current is True
    assert "DOCUMENT_VERSION_INITIATED" in audit.actions


async def test_replace_rejects_cross_tenant_input() -> None:
    service, records, documents, _audit = make_service()
    first = await service.initiate_general(input_data(), DocumentMetadataInput())
    documents.assets[first.record.document_id].status = "active"
    records.items[first.record.document_id].asset = documents.assets[first.record.document_id]
    with pytest.raises(NotFoundError):
        await service.replace(
            COMPANY_ID,
            first.record.document_id,
            ACTOR_ID,
            input_data(OTHER_COMPANY_ID),
            DocumentMetadataInput(),
        )


async def test_employee_lookup_is_tenant_scoped() -> None:
    service, _records, _documents, _audit = make_service()
    with pytest.raises(NotFoundError, match="Empleado"):
        await service.initiate_employee(
            EMPLOYEE_ID,
            input_data(OTHER_COMPANY_ID),
            DocumentMetadataInput(),
        )


async def test_replace_requires_active_current_version() -> None:
    service, _records, _documents, _audit = make_service()
    upload = await service.initiate_general(input_data(), DocumentMetadataInput())
    with pytest.raises(ConflictError, match="vigente"):
        await service.replace(
            COMPANY_ID,
            upload.record.document_id,
            ACTOR_ID,
            input_data(),
            DocumentMetadataInput(),
        )


async def test_existing_record_remains_editable_when_category_is_deactivated() -> None:
    service, records, documents, _audit = make_service()
    first = await service.initiate_general(
        input_data(), DocumentMetadataInput(title="Documento histórico")
    )
    documents.assets[first.record.document_id].status = "active"
    records.items[first.record.document_id].asset = documents.assets[first.record.document_id]
    records.categories_by_module["general"][0].is_active = False

    updated = await service.update_metadata(
        COMPANY_ID,
        first.record.document_id,
        ACTOR_ID,
        DocumentMetadataInput(title="Documento actualizado", category_id=first.record.category_id),
    )

    assert updated.title == "Documento actualizado"
    assert updated.category_id == first.record.category_id


async def test_new_record_cannot_select_deactivated_category() -> None:
    service, records, _documents, _audit = make_service()
    records.categories_by_module["general"][0].is_active = False

    with pytest.raises(ConflictError, match="categorías"):
        await service.initiate_general(input_data(), DocumentMetadataInput())


async def test_explicit_deactivated_category_returns_stable_error_code() -> None:
    service, records, _documents, _audit = make_service()
    records.categories_by_module["general"][0].is_active = False

    with pytest.raises(ValidationError) as error:
        await service.initiate_general(
            input_data(),
            DocumentMetadataInput(category_id=records.categories_by_module["general"][0].id),
        )

    assert error.value.code == "document_category_inactive"


async def test_metadata_update_rejects_blank_title() -> None:
    service, records, documents, _audit = make_service()
    first = await service.initiate_general(
        input_data(), DocumentMetadataInput(title="Documento vigente")
    )
    documents.assets[first.record.document_id].status = "active"
    records.items[first.record.document_id].asset = documents.assets[first.record.document_id]

    with pytest.raises(ValidationError, match="título"):
        await service.update_metadata(
            COMPANY_ID,
            first.record.document_id,
            ACTOR_ID,
            DocumentMetadataInput(title="   "),
        )


def test_category_labels_are_normalized_before_validation() -> None:
    category_input = CreateDocumentCategoryIn(
        module="employees",
        code="medical",
        name="  Constancia   médica  ",
        group_name="  Seguimiento   médico ",
        description="  Documento   emitido  ",
    )

    assert category_input.name == "Constancia médica"
    assert category_input.group_name == "Seguimiento médico"
    assert category_input.description == "Documento emitido"


def test_category_labels_reject_whitespace_only_values() -> None:
    with pytest.raises(PydanticValidationError, match="at least 2 characters"):
        CreateDocumentCategoryIn(
            module="employees", code="medical", name="   ", group_name="General"
        )
