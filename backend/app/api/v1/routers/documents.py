from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Query, Request, status

from app.api.v1.company_access import effective_company_id
from app.api.v1.deps import CurrentUser, get_document_service, require_permission
from app.api.v1.schemas.common import PageMeta
from app.api.v1.schemas.documents import (
    DocumentOut,
    DocumentsPage,
    DocumentStatus,
    DownloadUrlOut,
    InitiateDocumentIn,
    InitiateDocumentOut,
)
from app.application.documents import DocumentService, InitiateDocumentInput
from app.domain.entities.document import DocumentAsset

router = APIRouter(prefix="/documents", tags=["documents"])


def _out(document: DocumentAsset) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        company_id=document.company_id,
        original_filename=document.original_filename,
        extension=document.extension,
        content_type=document.detected_content_type or document.declared_content_type,
        size_bytes=document.size_bytes,
        checksum_sha256=document.checksum_sha256,
        status=cast(DocumentStatus, document.status),
        failure_code=document.failure_code,
        upload_expires_at=document.upload_expires_at,
        scanned_at=document.scanned_at,
        uploaded_by=document.uploaded_by,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post(
    "/uploads",
    response_model=InitiateDocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("documents:upload"))],
)
async def initiate_upload(
    body: InitiateDocumentIn,
    request: Request,
    current: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
    x_company_id: Annotated[uuid.UUID, Header(alias="X-Company-ID")],
) -> InitiateDocumentOut:
    company_id = effective_company_id(request)
    if x_company_id != company_id:
        # The permission dependency resolves and validates the same header;
        # keep this guard explicit so document uploads can never use a fallback tenant.
        raise RuntimeError("Resolved company context differs from X-Company-ID")
    ticket = await service.initiate(
        InitiateDocumentInput(
            company_id=company_id,
            actor_id=current.id,
            filename=body.file_name,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
            checksum_sha256=body.checksum_sha256,
        )
    )
    return InitiateDocumentOut(
        document_id=ticket.document.id,
        upload_url=ticket.upload_url,
        required_headers=ticket.required_headers,
        expires_at=ticket.expires_at,
    )


@router.get(
    "",
    response_model=DocumentsPage,
    dependencies=[Depends(require_permission("documents:read"))],
)
async def list_documents(
    request: Request,
    service: Annotated[DocumentService, Depends(get_document_service)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
    document_status: DocumentStatus | None = Query(None, alias="status"),
) -> DocumentsPage:
    items, total = await service.list(
        effective_company_id(request),
        page=page,
        size=size,
        search=search,
        status=document_status,
    )
    return DocumentsPage(
        items=[_out(item) for item in items],
        meta=PageMeta(
            page=page, size=size, total=total, pages=(total + size - 1) // size if total else 1
        ),
    )


@router.post(
    "/{document_id}/complete",
    response_model=DocumentOut,
    dependencies=[Depends(require_permission("documents:upload"))],
)
async def complete_upload(
    document_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentOut:
    document = await service.complete(effective_company_id(request), document_id, current.id)
    return _out(document)


@router.post(
    "/{document_id}/download-url",
    response_model=DownloadUrlOut,
    dependencies=[Depends(require_permission("documents:download"))],
)
async def create_download_url(
    document_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DownloadUrlOut:
    url, expires_at = await service.download_url(
        effective_company_id(request), document_id, current.id
    )
    return DownloadUrlOut(url=url, expires_at=expires_at)


@router.get(
    "/{document_id}",
    response_model=DocumentOut,
    dependencies=[Depends(require_permission("documents:read"))],
)
async def get_document(
    document_id: uuid.UUID,
    request: Request,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentOut:
    return _out(await service.get(effective_company_id(request), document_id))
