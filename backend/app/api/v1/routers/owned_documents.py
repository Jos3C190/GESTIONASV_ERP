"""Document routes for business entities that own a file of documents.

Vehicles (``fleet`` module) and drivers (their employee's driving documents)
reuse the Documents module — storage, antivirus, OCR, versions and expiry —
through this factory. Each owner supplies a resolver that loads the owner
inside the caller's company and branch scope; every route re-checks that the
document belongs to that owner so ids cannot be mixed between owners.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_check_permission_use_case,
    get_document_record_service,
    require_any_permission,
)
from app.api.v1.routers.documents import _metadata, _metadata_for_record, _record_out
from app.api.v1.schemas.common import PageMeta
from app.api.v1.schemas.documents import (
    DocumentCategoryOut,
    DocumentRecordOut,
    DocumentRecordsPage,
    DownloadUrlOut,
    DownloadVariant,
    InitiateDocumentOut,
    InitiateRecordIn,
    UpdateDocumentMetadataIn,
)
from app.application.documents import (
    DocumentMetadataInput,
    DocumentRecordService,
    InitiateDocumentInput,
)
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import NotFoundError
from app.domain.entities.document_record import DocumentRecord

Service = Annotated[DocumentRecordService, Depends(get_document_record_service)]
Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
_EPOCH = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class OwnerContext:
    company_id: uuid.UUID
    owner_id: uuid.UUID


OwnerResolver = Callable[
    [uuid.UUID, Request, SessionDep, CurrentUser, CheckPermissionUseCase],
    Awaitable[OwnerContext],
]


@dataclass(frozen=True, slots=True)
class OwnedDocumentsSpec:
    path: str
    module: str
    owner_type: str
    read: str
    upload: str
    update: str
    download: str
    resolve: OwnerResolver
    #: Category codes the owner may use; ``None`` = every category of the module.
    category_codes: frozenset[str] | None = None


def build_owned_documents_router(spec: OwnedDocumentsSpec, *, prefix: str, tag: str) -> APIRouter:  # noqa: C901
    router = APIRouter(prefix=prefix, tags=[tag])
    base = f"{spec.path}/{{owner_id}}/documents"

    def _internal(metadata: DocumentMetadataInput) -> DocumentMetadataInput:
        # Estos expedientes son operativos: la confidencialidad la controla el permiso del módulo.
        return DocumentMetadataInput(
            category_id=metadata.category_id,
            title=metadata.title,
            description=metadata.description,
            reference_code=metadata.reference_code,
            issuer=metadata.issuer,
            issued_on=metadata.issued_on,
            expires_on=metadata.expires_on,
            confidentiality="internal",
            tags=metadata.tags,
        )

    async def _owned(
        context: OwnerContext, document_id: uuid.UUID, service: DocumentRecordService
    ) -> DocumentRecord:
        record = await service.get(context.company_id, document_id)
        if (
            record.module != spec.module
            or record.owner_type != spec.owner_type
            or record.owner_id != context.owner_id
        ):
            raise NotFoundError("Documento no encontrado.", code="document_not_found")
        if spec.category_codes is not None:
            category = await service._records.get_category(
                record.category_id, context.company_id, include_inactive=True
            )
            if category is None or category.code not in spec.category_codes:
                raise NotFoundError("Documento no encontrado.", code="document_not_found")
        return record

    async def _category_ids(
        context: OwnerContext, service: DocumentRecordService
    ) -> list[uuid.UUID] | None:
        if spec.category_codes is None:
            return None
        categories = await service._records.categories(context.company_id, module=spec.module)
        return [item.id for item in categories if item.code in spec.category_codes]

    @router.get(
        f"{base}/categories",
        response_model=list[DocumentCategoryOut],
        dependencies=[Depends(require_any_permission(spec.read))],
    )
    async def list_categories(
        owner_id: uuid.UUID,
        request: Request,
        session: SessionDep,
        current: CurrentUser,
        checker: Checker,
        service: Service,
    ) -> list[DocumentCategoryOut]:
        context = await spec.resolve(owner_id, request, session, current, checker)
        categories = await service._records.categories(context.company_id, module=spec.module)
        return [
            DocumentCategoryOut(
                id=item.id,
                company_id=item.company_id,
                module=item.module,
                code=item.code,
                name=item.name,
                group_name=item.group_name,
                description=item.description,
                sort_order=item.sort_order,
                is_active=item.is_active,
                requires_expiry=item.requires_expiry,
                compliance_required=item.compliance_required,
            )
            for item in categories
            if item.is_active and (spec.category_codes is None or item.code in spec.category_codes)
        ]

    @router.get(
        base,
        response_model=DocumentRecordsPage,
        dependencies=[Depends(require_any_permission(spec.read))],
    )
    async def list_documents(
        owner_id: uuid.UUID,
        request: Request,
        session: SessionDep,
        current: CurrentUser,
        checker: Checker,
        service: Service,
        page: int = Query(1, ge=1),
        size: int = Query(24, ge=1, le=100),
        category_id: uuid.UUID | None = Query(None),
        search: str | None = Query(None, max_length=120),
        document_status: str | None = Query(None, alias="status"),
        expires_within_days: int | None = Query(None, ge=0, le=3650),
        include_versions: bool = Query(False),
    ) -> DocumentRecordsPage:
        context = await spec.resolve(owner_id, request, session, current, checker)
        allowed = await _category_ids(context, service)
        if allowed is not None and category_id is not None and category_id not in allowed:
            allowed = []
        if allowed is not None and not allowed:
            return DocumentRecordsPage(
                items=[], meta=PageMeta(page=page, size=size, total=0, pages=1)
            )
        # Con filtro de categorías del dueño se consulta cada una y se combinan.
        if allowed is not None and category_id is None:
            items: list[DocumentRecord] = []
            for allowed_id in allowed:
                found, _ = await service.list(
                    context.company_id,
                    page=1,
                    size=100,
                    module=spec.module,
                    owner_type=spec.owner_type,
                    owner_id=context.owner_id,
                    category_id=allowed_id,
                    search=search,
                    include_versions=include_versions,
                    document_status=document_status,
                    expires_within_days=expires_within_days,
                    include_restricted=False,
                )
                items.extend(found)
            items.sort(key=lambda record: record.created_at or _EPOCH, reverse=True)
            total = len(items)
            items = items[(page - 1) * size : page * size]
        else:
            items, total = await service.list(
                context.company_id,
                page=page,
                size=size,
                module=spec.module,
                owner_type=spec.owner_type,
                owner_id=context.owner_id,
                category_id=category_id,
                search=search,
                include_versions=include_versions,
                document_status=document_status,
                expires_within_days=expires_within_days,
                include_restricted=spec.module != "employees",
            )
        return DocumentRecordsPage(
            items=[_record_out(item) for item in items],
            meta=PageMeta(
                page=page, size=size, total=total, pages=(total + size - 1) // size if total else 1
            ),
        )

    @router.post(
        f"{base}/uploads",
        response_model=InitiateDocumentOut,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_any_permission(spec.upload))],
    )
    async def initiate_upload(
        owner_id: uuid.UUID,
        body: InitiateRecordIn,
        request: Request,
        session: SessionDep,
        current: CurrentUser,
        checker: Checker,
        service: Service,
    ) -> InitiateDocumentOut:
        context = await spec.resolve(owner_id, request, session, current, checker)
        upload = await service.initiate_owned(
            spec.module,
            spec.owner_type,
            context.owner_id,
            InitiateDocumentInput(
                company_id=context.company_id,
                actor_id=current.id,
                filename=body.file_name,
                content_type=body.content_type,
                size_bytes=body.size_bytes,
                checksum_sha256=body.checksum_sha256,
            ),
            _internal(_metadata(body)),
            allowed_category_codes=spec.category_codes,
        )
        return InitiateDocumentOut(
            document_id=upload.ticket.document.id,
            upload_url=upload.ticket.upload_url,
            required_headers=upload.ticket.required_headers,
            expires_at=upload.ticket.expires_at,
        )

    @router.get(
        f"{base}/{{document_id}}",
        response_model=DocumentRecordOut,
        dependencies=[Depends(require_any_permission(spec.read))],
    )
    async def get_document(
        owner_id: uuid.UUID,
        document_id: uuid.UUID,
        request: Request,
        session: SessionDep,
        current: CurrentUser,
        checker: Checker,
        service: Service,
    ) -> DocumentRecordOut:
        context = await spec.resolve(owner_id, request, session, current, checker)
        return _record_out(await _owned(context, document_id, service))

    @router.post(
        f"{base}/{{document_id}}/complete",
        response_model=DocumentRecordOut,
        dependencies=[Depends(require_any_permission(spec.upload))],
    )
    async def complete_upload(
        owner_id: uuid.UUID,
        document_id: uuid.UUID,
        request: Request,
        session: SessionDep,
        current: CurrentUser,
        checker: Checker,
        service: Service,
    ) -> DocumentRecordOut:
        context = await spec.resolve(owner_id, request, session, current, checker)
        await _owned(context, document_id, service)
        return _record_out(
            await service.activate_version(context.company_id, document_id, current.id)
        )

    @router.post(
        f"{base}/{{document_id}}/replace",
        response_model=InitiateDocumentOut,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_any_permission(spec.upload))],
    )
    async def replace_document(
        owner_id: uuid.UUID,
        document_id: uuid.UUID,
        body: InitiateRecordIn,
        request: Request,
        session: SessionDep,
        current: CurrentUser,
        checker: Checker,
        service: Service,
    ) -> InitiateDocumentOut:
        context = await spec.resolve(owner_id, request, session, current, checker)
        record = await _owned(context, document_id, service)
        if spec.category_codes is not None and body.category_id is not None:
            allowed = await _category_ids(context, service) or []
            if body.category_id not in allowed:
                raise NotFoundError("Categoría no disponible.", code="document_category_invalid")
        upload = await service.replace(
            context.company_id,
            document_id,
            current.id,
            InitiateDocumentInput(
                company_id=context.company_id,
                actor_id=current.id,
                filename=body.file_name,
                content_type=body.content_type,
                size_bytes=body.size_bytes,
                checksum_sha256=body.checksum_sha256,
            ),
            _internal(_metadata_for_record(body, record)),
        )
        return InitiateDocumentOut(
            document_id=upload.ticket.document.id,
            upload_url=upload.ticket.upload_url,
            required_headers=upload.ticket.required_headers,
            expires_at=upload.ticket.expires_at,
        )

    @router.patch(
        f"{base}/{{document_id}}",
        response_model=DocumentRecordOut,
        dependencies=[Depends(require_any_permission(spec.update))],
    )
    async def update_document(
        owner_id: uuid.UUID,
        document_id: uuid.UUID,
        body: UpdateDocumentMetadataIn,
        request: Request,
        session: SessionDep,
        current: CurrentUser,
        checker: Checker,
        service: Service,
    ) -> DocumentRecordOut:
        context = await spec.resolve(owner_id, request, session, current, checker)
        record = await _owned(context, document_id, service)
        if spec.category_codes is not None and body.category_id is not None:
            allowed = await _category_ids(context, service) or []
            if body.category_id not in allowed:
                raise NotFoundError("Categoría no disponible.", code="document_category_invalid")
        return _record_out(
            await service.update_metadata(
                context.company_id,
                document_id,
                current.id,
                _internal(_metadata_for_record(body, record)),
            )
        )

    @router.get(
        f"{base}/{{document_id}}/versions",
        response_model=list[DocumentRecordOut],
        dependencies=[Depends(require_any_permission(spec.read))],
    )
    async def list_versions(
        owner_id: uuid.UUID,
        document_id: uuid.UUID,
        request: Request,
        session: SessionDep,
        current: CurrentUser,
        checker: Checker,
        service: Service,
    ) -> list[DocumentRecordOut]:
        context = await spec.resolve(owner_id, request, session, current, checker)
        await _owned(context, document_id, service)
        return [
            _record_out(item) for item in await service.versions(context.company_id, document_id)
        ]

    async def _url(
        owner_id: uuid.UUID,
        document_id: uuid.UUID,
        request: Request,
        session: SessionDep,
        current: CurrentUser,
        checker: CheckPermissionUseCase,
        service: DocumentRecordService,
        *,
        preview: bool,
        variant: str,
    ) -> DownloadUrlOut:
        context = await spec.resolve(owner_id, request, session, current, checker)
        await _owned(context, document_id, service)
        build = service.preview_url if preview else service.download_url
        url, expires_at = await build(context.company_id, document_id, current.id, variant=variant)
        return DownloadUrlOut(url=url, expires_at=expires_at)

    @router.post(
        f"{base}/{{document_id}}/preview-url",
        response_model=DownloadUrlOut,
        dependencies=[Depends(require_any_permission(spec.download))],
    )
    async def preview_document(
        owner_id: uuid.UUID,
        document_id: uuid.UUID,
        request: Request,
        session: SessionDep,
        current: CurrentUser,
        checker: Checker,
        service: Service,
        variant: DownloadVariant = Query("original"),
    ) -> DownloadUrlOut:
        return await _url(
            owner_id,
            document_id,
            request,
            session,
            current,
            checker,
            service,
            preview=True,
            variant=variant,
        )

    @router.post(
        f"{base}/{{document_id}}/download-url",
        response_model=DownloadUrlOut,
        dependencies=[Depends(require_any_permission(spec.download))],
    )
    async def download_document(
        owner_id: uuid.UUID,
        document_id: uuid.UUID,
        request: Request,
        session: SessionDep,
        current: CurrentUser,
        checker: Checker,
        service: Service,
        variant: DownloadVariant = Query("original"),
    ) -> DownloadUrlOut:
        return await _url(
            owner_id,
            document_id,
            request,
            session,
            current,
            checker,
            service,
            preview=False,
            variant=variant,
        )

    return router
