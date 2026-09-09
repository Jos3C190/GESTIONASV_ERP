from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.company_access import effective_company_id, require_company_wide_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_document_general_service,
    require_permission,
)
from app.api.v1.schemas.common import PageMeta
from app.api.v1.schemas.document_general import (
    GeneralBreadcrumbOut,
    GeneralBatchMoveIn,
    GeneralContentsPage,
    GeneralDeletionBatchOut,
    GeneralDeletionBatchPage,
    GeneralDeletionOut,
    GeneralEntryMoveIn,
    GeneralEntryOut,
    GeneralFolderCreateIn,
    GeneralFolderRenameIn,
    GeneralFolderTreeOut,
)
from app.application.documents.general_service import DocumentGeneralService
from app.domain.entities.document_general_entry import DocumentGeneralEntry

router = APIRouter(prefix="/documents/general", tags=["document-general"])


def _out(entry: DocumentGeneralEntry) -> GeneralEntryOut:
    return GeneralEntryOut(
        id=entry.id,
        company_id=entry.company_id,
        kind=entry.kind,
        name=entry.name,
        parent_id=entry.parent_id,
        document_id=entry.document_id,
        created_by=entry.created_by,
        updated_by=entry.updated_by,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        deleted_at=entry.deleted_at,
        title=entry.document_title,
        original_filename=entry.original_filename,
        extension=entry.extension,
        content_type=entry.content_type,
        size_bytes=entry.size_bytes,
        technical_status=entry.technical_status,
        category_id=entry.category_id,
        category_name=entry.category_name,
        business_status=entry.business_status,
        version_number=entry.version_number,
        is_current=entry.is_current,
    )


async def _scope(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> uuid.UUID:
    company_id = effective_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    return company_id


@router.get(
    "",
    response_model=GeneralContentsPage,
    dependencies=[Depends(require_permission("documents:read"))],
)
async def list_general_contents(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralService, Depends(get_document_general_service)],
    folder_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None, max_length=120),
    category_id: uuid.UUID | None = Query(None),
    document_status: str | None = Query(None, alias="status", max_length=24),
    sort: Literal["name", "created_at", "updated_at", "size"] = Query("name"),
    descending: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
) -> GeneralContentsPage:
    company_id = await _scope(request, session, current)
    contents = await service.contents(
        company_id,
        folder_id=folder_id,
        search=search,
        category_id=category_id,
        status=document_status,
        sort=sort,
        descending=descending,
        page=page,
        size=size,
    )
    breadcrumbs = await service.breadcrumbs(company_id, folder_id)
    return GeneralContentsPage(
        items=[_out(item) for item in contents.items],
        meta=PageMeta(
            page=page,
            size=size,
            total=contents.total,
            pages=(contents.total + size - 1) // size if contents.total else 1,
        ),
        breadcrumbs=[
            GeneralBreadcrumbOut(id=item["id"], label=item["label"], href=item["href"])
            for item in breadcrumbs
        ],
    )


@router.post(
    "/folders",
    response_model=GeneralEntryOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("documents:manage_folders"))],
)
async def create_general_folder(
    body: GeneralFolderCreateIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralService, Depends(get_document_general_service)],
) -> GeneralEntryOut:
    company_id = await _scope(request, session, current)
    return _out(await service.create_folder(company_id, current.id, body.name, body.parent_id))


@router.patch(
    "/folders/{folder_id}",
    response_model=GeneralEntryOut,
    dependencies=[Depends(require_permission("documents:manage_folders"))],
)
async def rename_general_folder(
    folder_id: uuid.UUID,
    body: GeneralFolderRenameIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralService, Depends(get_document_general_service)],
) -> GeneralEntryOut:
    company_id = await _scope(request, session, current)
    return _out(await service.rename_folder(company_id, current.id, folder_id, body.name))


@router.post(
    "/folders/{folder_id}/move",
    response_model=GeneralEntryOut,
    dependencies=[Depends(require_permission("documents:manage_folders"))],
)
async def move_general_folder(
    folder_id: uuid.UUID,
    body: GeneralEntryMoveIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralService, Depends(get_document_general_service)],
) -> GeneralEntryOut:
    company_id = await _scope(request, session, current)
    return _out(await service.move_folder(company_id, current.id, folder_id, body.parent_id))


@router.post(
    "/move",
    response_model=list[GeneralEntryOut],
    dependencies=[Depends(require_permission("documents:manage_folders"))],
)
async def move_general_batch(
    body: GeneralBatchMoveIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralService, Depends(get_document_general_service)],
) -> list[GeneralEntryOut]:
    company_id = await _scope(request, session, current)
    async with session.begin_nested():
        entries = await service.move_batch(
            company_id,
            current.id,
            [(item.entry_id, item.kind) for item in body.items],
            body.parent_id,
        )
    return [_out(entry) for entry in entries]

@router.delete(
    "/folders/{folder_id}",
    response_model=GeneralDeletionOut,
    dependencies=[Depends(require_permission("documents:manage_folders"))],
)
async def delete_general_folder(
    folder_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralService, Depends(get_document_general_service)],
) -> GeneralDeletionOut:
    company_id = await _scope(request, session, current)
    batch_id = await service.delete_folder(company_id, current.id, folder_id)
    return GeneralDeletionOut(batch_id=batch_id)


@router.post(
    "/folders/{folder_id}/restore",
    response_model=GeneralEntryOut,
    dependencies=[Depends(require_permission("documents:manage_folders"))],
)
async def restore_general_folder(
    folder_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralService, Depends(get_document_general_service)],
) -> GeneralEntryOut:
    company_id = await _scope(request, session, current)
    return _out(await service.restore_folder(company_id, current.id, folder_id))


@router.patch(
    "/files/{document_id}/name",
    response_model=GeneralEntryOut,
    dependencies=[Depends(require_permission("documents:update"))],
)
async def rename_general_file(
    document_id: uuid.UUID,
    body: GeneralFolderRenameIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralService, Depends(get_document_general_service)],
) -> GeneralEntryOut:
    company_id = await _scope(request, session, current)
    return _out(await service.rename_file(company_id, current.id, document_id, body.name))


@router.post(
    "/files/{document_id}/move",
    response_model=GeneralEntryOut,
    dependencies=[Depends(require_permission("documents:manage_folders"))],
)
async def move_general_file(
    document_id: uuid.UUID,
    body: GeneralEntryMoveIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralService, Depends(get_document_general_service)],
) -> GeneralEntryOut:
    company_id = await _scope(request, session, current)
    return _out(await service.move_file(company_id, current.id, document_id, body.parent_id))


@router.get(
    "/trash",
    response_model=GeneralDeletionBatchPage,
    dependencies=[Depends(require_permission("documents:manage_folders"))],
)
async def list_general_trash(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralService, Depends(get_document_general_service)],
    search: str | None = Query(None, max_length=120),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> GeneralDeletionBatchPage:
    company_id = await _scope(request, session, current)
    batches, total = await service.deletion_batches(
        company_id, search=search, page=page, size=size
    )
    return GeneralDeletionBatchPage(
        items=[
            GeneralDeletionBatchOut(
                id=batch.id,
                company_id=batch.company_id,
                root_folder_id=batch.root_folder_id,
                label=batch.label,
                entry_count=batch.entry_count,
                created_at=batch.created_at,
                actor_id=batch.actor_id,
            )
            for batch in batches
        ],
        meta=PageMeta(
            page=page,
            size=size,
            total=total,
            pages=(total + size - 1) // size if total else 1,
        ),
    )


@router.post(
    "/trash/{batch_id}/restore",
    response_model=GeneralEntryOut,
    dependencies=[Depends(require_permission("documents:manage_folders"))],
)
async def restore_general_trash_batch(
    batch_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralService, Depends(get_document_general_service)],
) -> GeneralEntryOut:
    company_id = await _scope(request, session, current)
    return _out(await service.restore_deletion_batch(company_id, current.id, batch_id))

@router.get(
    "/folders/tree",
    response_model=GeneralFolderTreeOut,
    dependencies=[Depends(require_permission("documents:read"))],
)
async def get_general_folder_tree(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: Annotated[DocumentGeneralService, Depends(get_document_general_service)],
) -> GeneralFolderTreeOut:
    company_id = await _scope(request, session, current)
    entries = await service.tree(company_id)
    return GeneralFolderTreeOut(items=[_out(item) for item in entries if item.kind == "folder"])


__all__ = ["router"]
