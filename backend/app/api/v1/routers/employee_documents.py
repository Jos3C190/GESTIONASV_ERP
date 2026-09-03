"""Employee expediente endpoints.

These routes deliberately sit beside the generic document library.  They
provide a stable, discoverable contract for HR while reusing the same object
storage, antivirus, OCR and versioning use cases.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select

from app.api.v1.company_access import effective_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_check_permission_use_case,
    get_document_record_service,
    get_employee_repository,
    require_any_permission,
)
from app.api.v1.routers.documents import (
    _authorize_record_action,
    _ensure_employee_confidentiality,
    _metadata,
    _metadata_for_record,
    _record_out,
)
from app.api.v1.schemas.common import PageMeta
from app.api.v1.schemas.documents import (
    DocumentRecordOut,
    DocumentRecordsPage,
    DownloadUrlOut,
    DownloadVariant,
    InitiateDocumentOut,
    InitiateRecordIn,
    UpdateDocumentMetadataIn,
)
from app.application.documents import (
    DocumentRecordService,
    InitiateDocumentInput,
)
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import AuthorizationError
from app.domain.entities.document_record import DocumentRecord
from app.domain.ports.employee_repository import EmployeeRepository
from app.infrastructure.models.employee import EmployeeBranchAssignment

router = APIRouter(prefix="/employees", tags=["employee-documents"])

READ_PERMISSIONS = ("employee_documents:read",)
UPLOAD_PERMISSIONS = ("employee_documents:upload",)
UPDATE_PERMISSIONS = ("employee_documents:update",)
DOWNLOAD_PERMISSIONS = ("employee_documents:download",)
PROCESS_PERMISSIONS = ("employee_documents:process",)


async def _ensure_restricted_allowed(
    confidentiality: str,
    *,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    company_id: uuid.UUID,
) -> None:
    if confidentiality != "restricted" or current.is_superuser:
        return
    result = await checker.execute(current.id, company_id, "employee_documents:restricted")
    if not result.allowed:
        raise AuthorizationError(
            "No tiene permiso para gestionar documentos restringidos.",
            code="employee_document_restricted_forbidden",
        )


async def _employee_scope(
    employee_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    employees: Annotated[EmployeeRepository, Depends(get_employee_repository)],
) -> tuple[uuid.UUID, uuid.UUID | None]:
    employee = await employees.get_by_id(employee_id)
    company_id = effective_company_id(request)
    if employee is None or employee.company_id != company_id:
        raise HTTPException(404, "Empleado no encontrado.")
    raw_branch = request.headers.get("X-Branch-ID")
    branch_id: uuid.UUID | None = None
    if raw_branch:
        try:
            branch_id = uuid.UUID(raw_branch)
        except ValueError as exc:
            raise HTTPException(422, "El encabezado X-Branch-ID no es válido.") from exc
    await resolve_branch_scope(session, current, company_id, branch_id)
    if branch_id is not None:
        assignment = await session.scalar(
            select(EmployeeBranchAssignment.id).where(
                EmployeeBranchAssignment.employee_id == employee_id,
                EmployeeBranchAssignment.branch_id == branch_id,
                EmployeeBranchAssignment.is_active.is_(True),
                EmployeeBranchAssignment.assigned_until.is_(None),
            )
        )
        if assignment is None:
            raise HTTPException(404, "Empleado no encontrado en la sucursal seleccionada.")
    return company_id, branch_id


async def _get_owned_record(
    employee_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    service: DocumentRecordService,
) -> DocumentRecord:
    record = await service.get(effective_company_id(request), document_id)
    if (
        record.module != "employees"
        or record.owner_type != "employee"
        or record.owner_id != employee_id
    ):
        raise HTTPException(404, "Documento no encontrado.")
    return record


async def _owned_record(
    employee_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    service: DocumentRecordService,
) -> DocumentRecordOut:
    return _record_out(await _get_owned_record(employee_id, document_id, request, service))


@router.get(
    "/{employee_id}/documents",
    response_model=DocumentRecordsPage,
    dependencies=[Depends(require_any_permission(*READ_PERMISSIONS))],
)
async def list_employee_documents(
    employee_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    employees: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    page: int = Query(1, ge=1),
    size: int = Query(24, ge=1, le=100),
    category_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None, max_length=120),
    document_status: str | None = Query(None, alias="status"),
    confidentiality: Literal["internal", "restricted"] | None = Query(None),
    expires_within_days: int | None = Query(None, ge=0, le=3650),
    include_versions: bool = Query(False),
) -> DocumentRecordsPage:
    company_id, _branch_id = await _employee_scope(
        employee_id, request, session, current, employees
    )
    items, total = await record_service.list(
        company_id,
        page=page,
        size=size,
        module="employees",
        owner_id=employee_id,
        category_id=category_id,
        search=search,
        include_versions=include_versions,
        document_status=document_status,
        confidentiality=confidentiality,
        expires_within_days=expires_within_days,
        include_restricted=(
            current.is_superuser
            or (
                await checker.execute(current.id, company_id, "employee_documents:restricted")
            ).allowed
        ),
    )
    return DocumentRecordsPage(
        items=[_record_out(item) for item in items],
        meta=PageMeta(
            page=page,
            size=size,
            total=total,
            pages=(total + size - 1) // size if total else 1,
        ),
    )


@router.post(
    "/{employee_id}/documents/uploads",
    response_model=InitiateDocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission(*UPLOAD_PERMISSIONS))],
)
async def initiate_employee_document(
    employee_id: uuid.UUID,
    body: InitiateRecordIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    employees: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> InitiateDocumentOut:
    company_id, _branch_id = await _employee_scope(
        employee_id, request, session, current, employees
    )
    await _ensure_restricted_allowed(
        body.confidentiality, current=current, checker=checker, company_id=company_id
    )
    upload = await record_service.initiate_employee(
        employee_id,
        InitiateDocumentInput(
            company_id=company_id,
            actor_id=current.id,
            filename=body.file_name,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
            checksum_sha256=body.checksum_sha256,
        ),
        _metadata(body),
    )
    return InitiateDocumentOut(
        document_id=upload.ticket.document.id,
        upload_url=upload.ticket.upload_url,
        required_headers=upload.ticket.required_headers,
        expires_at=upload.ticket.expires_at,
    )


@router.get(
    "/{employee_id}/documents/{document_id}",
    response_model=DocumentRecordOut,
    dependencies=[Depends(require_any_permission(*READ_PERMISSIONS))],
)
async def get_employee_document(
    employee_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    employees: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> DocumentRecordOut:
    await _employee_scope(employee_id, request, session, current, employees)
    record = await _get_owned_record(employee_id, document_id, request, record_service)
    await _authorize_record_action(
        record,
        current=current,
        checker=checker,
        company_id=effective_company_id(request),
        action="read",
    )
    return _record_out(record)


@router.post(
    "/{employee_id}/documents/{document_id}/complete",
    response_model=DocumentRecordOut,
    dependencies=[Depends(require_any_permission(*UPLOAD_PERMISSIONS))],
)
async def complete_employee_document(
    employee_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    employees: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> DocumentRecordOut:
    await _employee_scope(employee_id, request, session, current, employees)
    record = await record_service.get(effective_company_id(request), document_id)
    if record.owner_id != employee_id or record.module != "employees":
        raise HTTPException(404, "Documento no encontrado.")
    await _authorize_record_action(
        record,
        current=current,
        checker=checker,
        company_id=effective_company_id(request),
        action="upload",
    )
    return _record_out(
        await record_service.activate_version(
            effective_company_id(request), document_id, current.id
        )
    )


@router.post(
    "/{employee_id}/documents/{document_id}/replace",
    response_model=InitiateDocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission(*UPLOAD_PERMISSIONS))],
)
async def replace_employee_document(
    employee_id: uuid.UUID,
    document_id: uuid.UUID,
    body: InitiateRecordIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    employees: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> InitiateDocumentOut:
    company_id, _branch_id = await _employee_scope(
        employee_id, request, session, current, employees
    )
    record = await record_service.get(company_id, document_id)
    if record.owner_id != employee_id or record.module != "employees":
        raise HTTPException(404, "Documento no encontrado.")
    await _authorize_record_action(
        record,
        current=current,
        checker=checker,
        company_id=company_id,
        action="upload",
    )
    metadata = _metadata_for_record(body, record)
    await _ensure_employee_confidentiality(
        record,
        metadata.confidentiality,
        current=current,
        checker=checker,
        company_id=company_id,
    )
    upload = await record_service.replace(
        company_id,
        document_id,
        current.id,
        InitiateDocumentInput(
            company_id=company_id,
            actor_id=current.id,
            filename=body.file_name,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
            checksum_sha256=body.checksum_sha256,
        ),
        metadata,
    )
    return InitiateDocumentOut(
        document_id=upload.ticket.document.id,
        upload_url=upload.ticket.upload_url,
        required_headers=upload.ticket.required_headers,
        expires_at=upload.ticket.expires_at,
    )


@router.patch(
    "/{employee_id}/documents/{document_id}",
    response_model=DocumentRecordOut,
    dependencies=[Depends(require_any_permission(*UPDATE_PERMISSIONS))],
)
async def update_employee_document(
    employee_id: uuid.UUID,
    document_id: uuid.UUID,
    body: UpdateDocumentMetadataIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    employees: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> DocumentRecordOut:
    await _employee_scope(employee_id, request, session, current, employees)
    record = await record_service.get(effective_company_id(request), document_id)
    if record.owner_id != employee_id or record.module != "employees":
        raise HTTPException(404, "Documento no encontrado.")
    await _authorize_record_action(
        record,
        current=current,
        checker=checker,
        company_id=effective_company_id(request),
        action="update",
    )
    return _record_out(
        await record_service.update_metadata(
            effective_company_id(request),
            document_id,
            current.id,
            _metadata_for_record(body, record),
        )
    )


@router.get(
    "/{employee_id}/documents/{document_id}/versions",
    response_model=list[DocumentRecordOut],
    dependencies=[Depends(require_any_permission(*READ_PERMISSIONS))],
)
async def list_employee_document_versions(
    employee_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    employees: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> list[DocumentRecordOut]:
    await _employee_scope(employee_id, request, session, current, employees)
    record = await record_service.get(effective_company_id(request), document_id)
    if record.owner_id != employee_id or record.module != "employees":
        raise HTTPException(404, "Documento no encontrado.")
    await _authorize_record_action(
        record,
        current=current,
        checker=checker,
        company_id=effective_company_id(request),
        action="versions",
    )
    version_items = await record_service.versions(effective_company_id(request), document_id)
    return [_record_out(item) for item in version_items]


@router.post(
    "/{employee_id}/documents/{document_id}/preview-url",
    response_model=DownloadUrlOut,
    dependencies=[Depends(require_any_permission(*DOWNLOAD_PERMISSIONS))],
)
async def preview_employee_document(
    employee_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    employees: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    variant: DownloadVariant = Query("original"),
) -> DownloadUrlOut:
    await _employee_scope(employee_id, request, session, current, employees)
    record = await record_service.get(effective_company_id(request), document_id)
    if record.owner_id != employee_id or record.module != "employees":
        raise HTTPException(404, "Documento no encontrado.")
    await _authorize_record_action(
        record,
        current=current,
        checker=checker,
        company_id=effective_company_id(request),
        action="download",
    )
    url, expires_at = await record_service.preview_url(
        effective_company_id(request), document_id, current.id, variant=variant
    )
    return DownloadUrlOut(url=url, expires_at=expires_at)


@router.post(
    "/{employee_id}/documents/{document_id}/download-url",
    response_model=DownloadUrlOut,
    dependencies=[Depends(require_any_permission(*DOWNLOAD_PERMISSIONS))],
)
async def download_employee_document(
    employee_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    session: SessionDep,
    employees: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    variant: str = Query("original", pattern="^(original|ocr)$"),
) -> DownloadUrlOut:
    await _employee_scope(employee_id, request, session, current, employees)
    record = await record_service.get(effective_company_id(request), document_id)
    if record.owner_id != employee_id or record.module != "employees":
        raise HTTPException(404, "Documento no encontrado.")
    await _authorize_record_action(
        record,
        current=current,
        checker=checker,
        company_id=effective_company_id(request),
        action="download",
    )
    url, expires_at = await record_service.download_url(
        effective_company_id(request), document_id, current.id, variant=variant
    )
    return DownloadUrlOut(url=url, expires_at=expires_at)


@router.post(
    "/{employee_id}/documents/{document_id}/ocr/retry",
    response_model=DocumentRecordOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_any_permission(*PROCESS_PERMISSIONS))],
)
async def retry_employee_document_ocr(
    employee_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    employees: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> DocumentRecordOut:
    await _employee_scope(employee_id, request, session, current, employees)
    record = await record_service.get(effective_company_id(request), document_id)
    if record.owner_id != employee_id or record.module != "employees":
        raise HTTPException(404, "Documento no encontrado.")
    await _authorize_record_action(
        record,
        current=current,
        checker=checker,
        company_id=effective_company_id(request),
        action="process",
    )
    asset = await record_service._documents.retry_ocr(
        effective_company_id(request), document_id, current.id
    )
    record.asset = asset
    return _record_out(record)


__all__ = ["router"]
