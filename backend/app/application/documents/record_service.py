"""Business use cases for the document library and employee expedientes.

The technical upload/scanning lifecycle lives in :mod:`service`.  This module
adds the business projection: ownership, categories, metadata and immutable
versions.  Keeping the two layers separate makes the same library reusable by
branches, products and suppliers in later phases.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import TypedDict

from app.application.audit.audit_service import AuditService
from app.application.documents.service import DocumentService, InitiateDocumentInput, UploadTicket
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.entities.document import DocumentAsset
from app.domain.entities.document_folder import DocumentFolder
from app.domain.entities.document_record import DocumentCategory, DocumentRecord
from app.domain.ports.document_record_repository import DocumentRecordRepository
from app.domain.ports.employee_repository import EmployeeRepository

_TAG_RE = re.compile(r"^[\w .:/+#-]{1,40}$", re.UNICODE)
_MAX_TAGS = 10
_MIN_PRINTABLE = 32
_MAX_TITLE = 200


@dataclass(frozen=True, slots=True)
class DocumentMetadataInput:
    category_id: uuid.UUID | None = None
    title: str | None = None
    description: str | None = None
    reference_code: str | None = None
    issuer: str | None = None
    issued_on: date | None = None
    expires_on: date | None = None
    confidentiality: str = "restricted"
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentRecordUpload:
    ticket: UploadTicket
    record: DocumentRecord


class _MetadataValues(TypedDict):
    title: str
    description: str | None
    reference_code: str | None
    issuer: str | None
    issued_on: date | None
    expires_on: date | None
    confidentiality: str
    tags: list[str]


def _clean_text(value: str | None, *, max_length: int, field: str) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return None
    if len(cleaned) > max_length or any(ord(char) < _MIN_PRINTABLE for char in cleaned):
        raise ValidationError(f"El campo {field} no es válido.", code="document_metadata_invalid")
    return cleaned


def _clean_tags(tags: tuple[str, ...]) -> list[str]:
    cleaned: list[str] = []
    for raw in tags:
        value = " ".join(raw.strip().split())
        if not value or not _TAG_RE.fullmatch(value):
            raise ValidationError("Una etiqueta no es válida.", code="document_metadata_invalid")
        if value.casefold() not in {item.casefold() for item in cleaned}:
            cleaned.append(value)
    if len(cleaned) > _MAX_TAGS:
        raise ValidationError(
            "Un documento puede tener como máximo 10 etiquetas.", code="document_metadata_invalid"
        )
    return cleaned


#: Dueño por defecto de cada módulo con expedientes por entidad.
_OWNER_TYPES = {"employees": "employee", "fleet": "vehicle"}

#: Solo se crean al confirmar una captura guiada: de ellas depende si alguien puede
#: conducir o si un vehículo puede salir, y cualquier otra vía se saltaría sus validaciones.
_LICENSE_ONLY = "La licencia de conducir solo se registra con la captura guiada de Conductores."
_CARD_ONLY = "La tarjeta de circulación solo se registra con la captura guiada del vehículo."
_CAPTURE_ONLY_MESSAGES = {
    "driver_license": _LICENSE_ONLY,
    "driver_license_back": _LICENSE_ONLY,
    "circulation_card": _CARD_ONLY,
    "circulation_card_back": _CARD_ONLY,
}
CAPTURE_ONLY_CATEGORY_CODES = frozenset(_CAPTURE_ONLY_MESSAGES)


def _require_not_capture_only(category: DocumentCategory) -> None:
    message = _CAPTURE_ONLY_MESSAGES.get(category.code)
    if message is not None:
        raise ConflictError(message, code="document_category_capture_only")


class DocumentRecordService:
    def __init__(
        self,
        documents: DocumentService,
        records: DocumentRecordRepository,
        employees: EmployeeRepository,
        audit: AuditService,
    ) -> None:
        self._documents = documents
        self._records = records
        self._employees = employees
        self._audit = audit

    async def _category(
        self,
        company_id: uuid.UUID,
        module: str,
        category_id: uuid.UUID | None,
        *,
        allow_inactive: bool = False,
    ) -> DocumentCategory:
        if category_id is not None:
            category = await self._records.get_category(
                category_id, company_id, include_inactive=allow_inactive
            )
            if category is None and not allow_inactive:
                inactive = await self._records.get_category(
                    category_id, company_id, include_inactive=True
                )
                if inactive is not None and inactive.module == module and not inactive.is_active:
                    raise ValidationError(
                        "La categoría está desactivada para nuevas cargas.",
                        code="document_category_inactive",
                    )
            if category is None or category.module != module:
                raise ValidationError(
                    "La categoría no pertenece a la empresa o módulo seleccionado.",
                    code="document_category_invalid",
                )
            return category
        categories = await self._records.categories(company_id, module=module)
        category = next((item for item in categories if item.code == "other"), None)
        if category is None:
            raise ConflictError(
                "No hay categorías configuradas para el módulo.",
                code="document_category_unavailable",
            )
        return category

    @staticmethod
    def _metadata(
        metadata: DocumentMetadataInput,
        *,
        filename: str,
    ) -> _MetadataValues:
        title = _clean_text(metadata.title, max_length=_MAX_TITLE, field="título") or filename
        if len(title) > _MAX_TITLE:
            title = title[:_MAX_TITLE]
        if metadata.confidentiality not in {"internal", "restricted"}:
            raise ValidationError(
                "La confidencialidad no es válida.", code="document_metadata_invalid"
            )
        if metadata.expires_on and metadata.issued_on and metadata.expires_on < metadata.issued_on:
            raise ValidationError(
                "La fecha de vencimiento no puede ser anterior a la emisión.",
                code="document_metadata_invalid",
            )
        return {
            "title": title,
            "description": _clean_text(metadata.description, max_length=4000, field="descripción"),
            "reference_code": _clean_text(
                metadata.reference_code, max_length=120, field="referencia"
            ),
            "issuer": _clean_text(metadata.issuer, max_length=180, field="emisor"),
            "issued_on": metadata.issued_on,
            "expires_on": metadata.expires_on,
            "confidentiality": metadata.confidentiality,
            "tags": _clean_tags(metadata.tags),
        }

    async def _record_from_asset(
        self,
        asset: DocumentAsset,
        *,
        module: str,
        owner_type: str | None,
        owner_id: uuid.UUID | None,
        category: DocumentCategory,
        metadata: DocumentMetadataInput,
        actor_id: uuid.UUID,
        version_group_id: uuid.UUID | None = None,
        version_number: int = 1,
        is_current: bool = True,
        replaces_document_id: uuid.UUID | None = None,
    ) -> DocumentRecord:
        values = self._metadata(metadata, filename=asset.original_filename)
        self._require_expiry(category, values["expires_on"])
        record = DocumentRecord(
            document_id=asset.id,
            company_id=asset.company_id,
            module=module,
            owner_type=owner_type,
            owner_id=owner_id,
            category_id=category.id,
            version_group_id=version_group_id or uuid.uuid4(),
            version_number=version_number,
            is_current=is_current,
            replaces_document_id=replaces_document_id,
            created_by=actor_id,
            updated_by=actor_id,
            title=values["title"],
            description=values["description"],
            reference_code=values["reference_code"],
            issuer=values["issuer"],
            issued_on=values["issued_on"],
            expires_on=values["expires_on"],
            confidentiality=values["confidentiality"],
            tags=values["tags"],
        )
        await self._records.add(record)
        loaded = await self._records.get(record.document_id, include_deleted=True)
        if loaded is None:
            raise ConflictError(
                "No se pudo registrar el documento.", code="document_record_unavailable"
            )
        return loaded

    async def initiate_general(
        self,
        data: InitiateDocumentInput,
        metadata: DocumentMetadataInput,
    ) -> DocumentRecordUpload:
        category = await self._category(data.company_id, "general", metadata.category_id)
        ticket = await self._documents.initiate(data)
        record = await self._record_from_asset(
            ticket.document,
            module="general",
            owner_type=None,
            owner_id=None,
            category=category,
            metadata=metadata,
            actor_id=data.actor_id,
        )
        return DocumentRecordUpload(ticket, record)

    async def initiate_employee(
        self,
        employee_id: uuid.UUID,
        data: InitiateDocumentInput,
        metadata: DocumentMetadataInput,
        *,
        allowed_category_codes: frozenset[str] | None = None,
    ) -> DocumentRecordUpload:
        employee = await self._employees.get_by_id(employee_id)
        if employee is None or employee.company_id != data.company_id:
            raise NotFoundError("Empleado no encontrado.", code="employee_not_found")
        return await self.initiate_owned(
            "employees",
            "employee",
            employee_id,
            data,
            metadata,
            allowed_category_codes=allowed_category_codes,
        )

    async def initiate_owned(
        self,
        module: str,
        owner_type: str,
        owner_id: uuid.UUID,
        data: InitiateDocumentInput,
        metadata: DocumentMetadataInput,
        *,
        allowed_category_codes: frozenset[str] | None = None,
    ) -> DocumentRecordUpload:
        """Start an upload for a document owned by a business entity.

        The caller must already have verified that the owner belongs to
        ``data.company_id`` and is inside the caller's branch scope.
        """
        category = await self._category(data.company_id, module, metadata.category_id)
        if allowed_category_codes is not None and category.code not in allowed_category_codes:
            raise ValidationError(
                "La categoría no está disponible en este módulo.",
                code="document_category_invalid",
            )
        _require_not_capture_only(category)
        self._require_expiry(category, metadata.expires_on)
        ticket = await self._documents.initiate(data)
        record = await self._record_from_asset(
            ticket.document,
            module=module,
            owner_type=owner_type,
            owner_id=owner_id,
            category=category,
            metadata=metadata,
            actor_id=data.actor_id,
        )
        return DocumentRecordUpload(ticket, record)

    async def adopt_asset(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: uuid.UUID,
        *,
        module: str,
        owner_type: str,
        owner_id: uuid.UUID,
        category_code: str,
        metadata: DocumentMetadataInput,
    ) -> DocumentRecord:
        """Give an already scanned asset its record, replacing what the owner had.

        The new record becomes the only current one of that owner and category:
        compliance takes the furthest expiry among current records, so an older
        license left current would outrank the one being confirmed.
        """
        asset = await self._documents.get(company_id, document_id)
        if asset.status != "active":
            raise ConflictError(
                "El documento todavía no está disponible.", code="document_not_active"
            )
        categories = await self._records.categories(company_id, module=module)
        category = next((item for item in categories if item.code == category_code), None)
        if category is None:
            raise ConflictError(
                "La categoría no está disponible.", code="document_category_unavailable"
            )
        current = await self._records.current_for_owner(
            company_id,
            module=module,
            owner_type=owner_type,
            owner_id=owner_id,
            category_id=category.id,
        )
        previous = max(
            (item for item in current if item.asset and item.asset.deleted_at is None),
            key=lambda item: item.expires_on or date.min,
            default=None,
        )
        record = await self._record_from_asset(
            asset,
            module=module,
            owner_type=owner_type,
            owner_id=owner_id,
            category=category,
            metadata=metadata,
            actor_id=actor_id,
            version_group_id=previous.version_group_id if previous else None,
            version_number=(
                await self._records.next_version_number(previous.version_group_id)
                if previous
                else 1
            ),
            is_current=previous is None,
            replaces_document_id=previous.document_id if previous else None,
        )
        if previous is not None:
            await self._records.set_current_version(
                version_group_id=previous.version_group_id,
                document_id=record.document_id,
            )
        retired = [
            item.document_id
            for item in current
            if previous is None or item.version_group_id != previous.version_group_id
        ]
        await self._records.retire(retired, actor_id=actor_id)
        await self._audit.record(
            action="DOCUMENT_ADOPTED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="documents",
            resource_id=str(document_id),
            after_state={
                "category": category_code,
                "replaces": str(previous.document_id) if previous else None,
                "retired": [str(item) for item in retired],
            },
            required=True,
        )
        return await self.get(company_id, document_id)

    @staticmethod
    def _require_expiry(category: DocumentCategory, expires_on: object) -> None:
        if category.requires_expiry and expires_on is None:
            raise ValidationError(
                f"Los documentos de «{category.name}» requieren fecha de vencimiento.",
                code="document_expiry_required",
            )

    async def get(
        self, company_id: uuid.UUID, document_id: uuid.UUID, *, include_deleted: bool = False
    ) -> DocumentRecord:
        record = await self._records.get(document_id, include_deleted=include_deleted)
        if record is None or record.company_id != company_id:
            raise NotFoundError("Documento no encontrado.", code="document_not_found")
        if record.asset is not None:
            record.asset = await self._documents.enrich(record.asset)
        return record

    async def list(
        self,
        company_id: uuid.UUID,
        *,
        page: int,
        size: int,
        module: str | None = None,
        owner_type: str | None = None,
        owner_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        search: str | None = None,
        include_versions: bool = False,
        include_deleted: bool = False,
        document_status: str | None = None,
        storage_status: str | None = None,
        confidentiality: str | None = None,
        expires_within_days: int | None = None,
        include_restricted: bool = True,
        branch_id: uuid.UUID | None = None,
        modules: set[str] | None = None,
    ) -> tuple[list[DocumentRecord], int]:
        items, total = await self._records.list(
            company_id,
            page=page,
            size=size,
            module=module,
            owner_type=owner_type or _OWNER_TYPES.get(module or ""),
            owner_id=owner_id,
            category_id=category_id,
            search=search,
            include_versions=include_versions,
            include_deleted=include_deleted,
            document_status=document_status,
            storage_status=storage_status,
            confidentiality=confidentiality,
            expires_within_days=expires_within_days,
            include_restricted=include_restricted,
            branch_id=branch_id,
            modules=modules,
        )
        records = list(items)
        assets = [item.asset for item in records if item.asset is not None]
        for asset in assets:
            await self._documents.enrich(asset)
        return records, total

    async def list_folders(
        self,
        company_id: uuid.UUID,
        *,
        parent: str,
        employee_id: uuid.UUID | None = None,
        page: int,
        size: int,
        search: str | None = None,
        branch_id: uuid.UUID | None = None,
        include_restricted: bool = True,
        allowed_modules: set[str] | None = None,
        upload_modules: set[str] | None = None,
    ) -> tuple[Sequence[DocumentFolder], int]:
        folders, total = await self._records.list_folders(
            company_id,
            parent=parent,
            employee_id=employee_id,
            page=page,
            size=size,
            search=search,
            branch_id=branch_id,
            include_restricted=include_restricted,
            allowed_modules=allowed_modules,
            upload_modules=upload_modules,
        )
        return list(folders), total

    async def complete(
        self, company_id: uuid.UUID, document_id: uuid.UUID, actor_id: uuid.UUID
    ) -> DocumentRecord:
        record = await self.get(company_id, document_id)
        asset = await self._documents.complete(company_id, document_id, actor_id)
        record.asset = asset
        return record

    async def update_metadata(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: uuid.UUID,
        metadata: DocumentMetadataInput,
    ) -> DocumentRecord:
        record = await self.get(company_id, document_id)
        if record.asset is None or record.asset.deleted_at is not None:
            raise NotFoundError("Documento no encontrado.", code="document_not_found")
        if metadata.title is not None and not metadata.title.strip():
            raise ValidationError(
                "El título del documento no puede estar vacío.",
                code="document_metadata_invalid",
            )
        requested_category_id = metadata.category_id
        category = await self._category(
            company_id,
            record.module,
            requested_category_id or record.category_id,
            # Deactivating a category must not make historical records
            # impossible to edit. A newly selected category still has to be
            # active so deactivated entries cannot be reused for new data.
            allow_inactive=requested_category_id in (None, record.category_id),
        )
        _require_not_capture_only(category)
        current_category = await self._records.get_category(
            record.category_id, company_id, include_inactive=True
        )
        if current_category is not None:
            _require_not_capture_only(current_category)
        values = self._metadata(metadata, filename=record.asset.original_filename)
        self._require_expiry(category, values["expires_on"])
        for key, value in values.items():
            setattr(record, key, value)
        record.category_id = category.id
        record.updated_by = actor_id
        saved = await self._records.save(record)
        await self._audit.record(
            action="DOCUMENT_METADATA_UPDATED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="documents",
            resource_id=str(document_id),
            after_state={"category_id": str(category.id)},
            required=True,
        )
        return await self.get(company_id, saved.document_id)

    async def versions(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> Sequence[DocumentRecord]:
        record = await self.get(company_id, document_id, include_deleted=True)
        records = list(await self._records.list_versions(record.document_id))
        for item in records:
            if item.asset is not None:
                await self._documents.enrich(item.asset)
        return records

    async def replace(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: uuid.UUID,
        data: InitiateDocumentInput,
        metadata: DocumentMetadataInput,
    ) -> DocumentRecordUpload:
        previous = await self.get(company_id, document_id)
        if data.company_id != company_id:
            raise NotFoundError("Documento no encontrado.", code="document_not_found")
        if metadata.title is not None and not metadata.title.strip():
            raise ValidationError(
                "El título del documento no puede estar vacío.",
                code="document_metadata_invalid",
            )
        if previous.asset is None or previous.asset.status != "active" or not previous.is_current:
            raise ConflictError(
                "Solo se puede versionar el documento vigente y activo.",
                code="document_version_not_allowed",
            )
        if metadata.category_id is None:
            metadata = DocumentMetadataInput(
                category_id=previous.category_id,
                title=metadata.title or previous.title,
                description=metadata.description
                if metadata.description is not None
                else previous.description,
                reference_code=metadata.reference_code
                if metadata.reference_code is not None
                else previous.reference_code,
                issuer=metadata.issuer if metadata.issuer is not None else previous.issuer,
                issued_on=metadata.issued_on or previous.issued_on,
                expires_on=metadata.expires_on or previous.expires_on,
                confidentiality=metadata.confidentiality or previous.confidentiality,
                tags=metadata.tags or tuple(previous.tags),
            )
        next_number = await self._records.next_version_number(previous.version_group_id)
        category = await self._category(
            company_id,
            previous.module,
            metadata.category_id,
            allow_inactive=metadata.category_id in (None, previous.category_id),
        )
        _require_not_capture_only(category)
        previous_category = await self._records.get_category(
            previous.category_id, company_id, include_inactive=True
        )
        if previous_category is not None:
            _require_not_capture_only(previous_category)
        ticket = await self._documents.initiate(data)
        record = await self._record_from_asset(
            ticket.document,
            module=previous.module,
            owner_type=previous.owner_type,
            owner_id=previous.owner_id,
            category=category,
            metadata=metadata,
            actor_id=actor_id,
            version_group_id=previous.version_group_id,
            version_number=next_number,
            is_current=False,
            replaces_document_id=previous.document_id,
        )
        await self._audit.record(
            action="DOCUMENT_VERSION_INITIATED",
            user_id=actor_id,
            company_id=company_id,
            resource_type="documents",
            resource_id=str(record.document_id),
            after_state={"version_number": next_number, "replaces": str(previous.document_id)},
            required=True,
        )
        return DocumentRecordUpload(ticket, record)

    async def activate_version(
        self, company_id: uuid.UUID, document_id: uuid.UUID, actor_id: uuid.UUID
    ) -> DocumentRecord:
        record = await self.get(company_id, document_id)
        asset = await self._documents.complete(company_id, document_id, actor_id)
        if asset.status == "active" and not record.is_current:
            current = await self._records.set_current_version(
                version_group_id=record.version_group_id,
                document_id=record.document_id,
            )
            if current is not None:
                record = current
            await self._audit.record(
                action="DOCUMENT_VERSION_ACTIVATED",
                user_id=actor_id,
                company_id=company_id,
                resource_type="documents",
                resource_id=str(document_id),
                after_state={"version_number": record.version_number},
                required=True,
            )
        record.asset = asset
        return record

    async def download_url(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: uuid.UUID,
        *,
        variant: str = "original",
    ) -> tuple[str, datetime]:
        record = await self.get(company_id, document_id)
        if record.asset is None:
            raise ConflictError(
                "La versión solicitada no está disponible.", code="document_not_downloadable"
            )
        return await self._documents.download_url(
            company_id, document_id, actor_id, variant=variant
        )

    async def preview_url(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        actor_id: uuid.UUID,
        *,
        variant: str = "original",
    ) -> tuple[str, datetime]:
        await self.get(company_id, document_id)
        return await self._documents.preview_url(company_id, document_id, actor_id, variant=variant)


__all__ = ["DocumentMetadataInput", "DocumentRecordService", "DocumentRecordUpload"]
