from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.company_access import effective_company_id, require_company_wide_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_document_general_import_service,
    require_permission,
)
from app.api.v1.schemas.common import PageMeta
from app.api.v1.schemas.document_general import (
    GeneralImportItemOut,
    GeneralImportOut,
    GeneralImportPrepareIn,
    GeneralImportTicketIn,
    GeneralImportTicketOut,
)
from app.api.v1.schemas.documents import InitiateDocumentOut
from app.application.documents.general_import_service import DocumentGeneralImportService
from app.domain.entities.document_general_import import (
    DocumentGeneralImport,
    DocumentGeneralImportItem,
)

router = APIRouter(
    prefix="/documents/general/imports",
    tags=["document-general-imports"],
    dependencies=[
        Depends(require_permission("documents:upload")),
        Depends(require_permission("documents:manage_folders")),
    ],
)


async def _company(request: Request, session: SessionDep, current: CurrentUser) -> uuid.UUID:
    company_id = effective_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    return company_id


def _item(item: DocumentGeneralImportItem) -> GeneralImportItemOut:
    value = item
    return GeneralImportItemOut(
        id=value.id,
        kind=value.kind,
        source_path=value.source_path,
        source_name=value.source_name,
        resolved_path=value.resolved_path,
        resolved_name=value.resolved_name,
        parent_folder_id=value.parent_folder_id,
        entry_id=value.entry_id,
        document_id=value.document_id,
        size_bytes=value.size_bytes,
        content_type=value.content_type,
        extension=value.extension,
        status=value.status,
        failure_code=value.failure_code,
        failure_message=value.failure_message,
        attempts=value.attempts,
    )


def _out(
    import_row: DocumentGeneralImport,
    items: Sequence[DocumentGeneralImportItem],
    total: int,
    page: int,
    size: int,
) -> GeneralImportOut:
    return GeneralImportOut(
        id=import_row.id,
        parent_id=import_row.parent_id,
        root_entry_id=import_row.root_entry_id,
        status=import_row.status,
        total_files=import_row.total_files,
        total_folders=import_row.total_folders,
        total_entries=import_row.total_entries,
        total_bytes=import_row.total_bytes,
        completed_files=import_row.completed_files,
        skipped_files=import_row.skipped_files,
        failed_files=import_row.failed_files,
        created_at=import_row.created_at,
        updated_at=import_row.updated_at,
        completed_at=import_row.completed_at,
        expires_at=import_row.expires_at,
        items=[_item(item) for item in items],
        meta=PageMeta(
            page=page, size=size, total=total, pages=(total + size - 1) // size if total else 1
        ),
    )


@router.post("", response_model=GeneralImportOut, status_code=status.HTTP_201_CREATED)
async def prepare_import(
    body: GeneralImportPrepareIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralImportService, Depends(get_document_general_import_service)],
) -> GeneralImportOut:
    company_id = await _company(request, session, current)
    metadata = body.metadata.model_dump(mode="json", exclude_none=True)
    import_row, items = await service.prepare(
        company_id,
        current.id,
        body.parent_id,
        metadata,
        [item.model_dump() for item in body.items],
    )
    return _out(import_row, list(items), len(items), 1, len(items))


@router.get("/{import_id}", response_model=GeneralImportOut)
async def get_import(
    import_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralImportService, Depends(get_document_general_import_service)],
    page: int = Query(1, ge=1),
    size: int = Query(200, ge=1, le=1000),
) -> GeneralImportOut:
    company_id = await _company(request, session, current)
    import_row, items, total = await service.get(company_id, import_id, page=page, size=size)
    return _out(import_row, list(items), total, page, size)


@router.post("/{import_id}/items/{item_id}/ticket", response_model=GeneralImportTicketOut)
async def authorize_item(
    import_id: uuid.UUID,
    item_id: uuid.UUID,
    body: GeneralImportTicketIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralImportService, Depends(get_document_general_import_service)],
) -> GeneralImportTicketOut:
    company_id = await _company(request, session, current)
    checksum = body.checksum_sha256
    item, ticket = await service.ticket(company_id, current.id, import_id, item_id, checksum)
    return GeneralImportTicketOut(
        item=_item(item),
        ticket=InitiateDocumentOut(
            document_id=ticket.document.id,
            upload_url=ticket.upload_url,
            method="PUT",
            required_headers=ticket.required_headers,
            expires_at=ticket.expires_at,
        ),
    )


@router.post("/{import_id}/items/{item_id}/complete", response_model=GeneralImportItemOut)
async def complete_item(
    import_id: uuid.UUID,
    item_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralImportService, Depends(get_document_general_import_service)],
) -> GeneralImportItemOut:
    company_id = await _company(request, session, current)
    return _item(await service.complete(company_id, current.id, import_id, item_id))


@router.post("/{import_id}/cancel", response_model=GeneralImportOut)
async def cancel_import(
    import_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralImportService, Depends(get_document_general_import_service)],
) -> GeneralImportOut:
    company_id = await _company(request, session, current)
    await service.cancel(company_id, current.id, import_id)
    import_row, items, total = await service.get(company_id, import_id)
    return _out(import_row, list(items), total, 1, total or 1)


__all__ = ["router"]
