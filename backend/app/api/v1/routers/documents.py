from __future__ import annotations

import uuid
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.company_access import (
    effective_company_id,
    require_company_wide_scope,
    resolve_branch_scope,
)
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    get_document_record_service,
    get_document_service,
    get_employee_repository,
    require_any_permission,
    require_permission,
)
from app.api.v1.schemas.common import PageMeta
from app.api.v1.schemas.documents import (
    CreateDocumentCategoryIn,
    DocumentBreadcrumbOut,
    DocumentCategoryOut,
    DocumentFolderOut,
    DocumentFolderParent,
    DocumentFoldersPage,
    DocumentMetadataIn,
    DocumentOut,
    DocumentRecordOut,
    DocumentRecordsPage,
    DocumentsPage,
    DocumentStatus,
    DownloadUrlOut,
    DownloadVariant,
    InitiateDocumentOut,
    InitiateRecordIn,
    OcrStatus,
    RecordStatus,
    UpdateDocumentCategoryIn,
    UpdateDocumentMetadataIn,
)
from app.api.v1.schemas.lifecycle import DeletedRecordOut, SoftDeleteRequest
from app.application.audit.audit_service import AuditService
from app.application.documents import (
    DocumentMetadataInput,
    DocumentRecordService,
    DocumentService,
    InitiateDocumentInput,
)
from app.application.lifecycle import LifecycleService
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.domain.entities.document import DocumentAsset
from app.domain.entities.document_folder import DocumentFolder
from app.domain.entities.document_record import DocumentCategory, DocumentRecord
from app.domain.ports.employee_repository import EmployeeRepository
from app.infrastructure.models.employee import EmployeeBranchAssignment
from app.infrastructure.observability import record_counter
from app.infrastructure.repositories import SqlAlchemyLifecycleRepository

router = APIRouter(prefix="/documents", tags=["documents"])


def _out(document: DocumentAsset, record: DocumentRecord | None = None) -> DocumentOut:
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
        ocr_status=cast(OcrStatus | None, document.ocr_status),
        ocr_available=document.ocr_available,
        ocr_failure_code=document.ocr_failure_code,
        ocr_completed_at=document.ocr_completed_at,
        module=cast(Literal["general", "employees"] | None, record.module if record else None),
        owner_type=record.owner_type if record else None,
        owner_id=record.owner_id if record else None,
        owner_label=record.owner_label if record else None,
        owner_deleted=record.owner_deleted if record else False,
        category_id=record.category_id if record else None,
        category_name=record.category_name if record else None,
        category_group=record.category_group if record else None,
        title=record.title if record else None,
        description=record.description if record else None,
        reference_code=record.reference_code if record else None,
        issuer=record.issuer if record else None,
        issued_on=record.issued_on if record else None,
        expires_on=record.expires_on if record else None,
        confidentiality=cast(
            Literal["internal", "restricted"] | None,
            record.confidentiality if record else None,
        ),
        tags=record.tags if record else [],
        business_status=cast(RecordStatus | None, record.business_status if record else None),
        version_group_id=record.version_group_id if record else None,
        version_number=record.version_number if record else None,
        is_current=record.is_current if record else None,
        replaces_document_id=record.replaces_document_id if record else None,
    )


def _metadata(body: DocumentMetadataIn) -> DocumentMetadataInput:
    return DocumentMetadataInput(
        category_id=body.category_id,
        title=body.title,
        description=body.description,
        reference_code=body.reference_code,
        issuer=body.issuer,
        issued_on=body.issued_on,
        expires_on=body.expires_on,
        confidentiality=body.confidentiality,
        tags=tuple(body.tags),
    )


def _metadata_for_record(body: DocumentMetadataIn, record: DocumentRecord) -> DocumentMetadataInput:
    """Build a complete metadata draft while preserving omitted PATCH fields.

    Upload and replacement payloads use defaults, but metadata updates are
    partial.  Pydantic's ``model_fields_set`` lets us distinguish an omitted
    field from an explicit value without weakening the public schema.
    """
    fields = body.model_fields_set
    return DocumentMetadataInput(
        category_id=body.category_id if body.category_id is not None else record.category_id,
        title=body.title if body.title is not None else record.title,
        description=(body.description if "description" in fields else record.description),
        reference_code=(
            body.reference_code if "reference_code" in fields else record.reference_code
        ),
        issuer=body.issuer if "issuer" in fields else record.issuer,
        issued_on=body.issued_on if "issued_on" in fields else record.issued_on,
        expires_on=body.expires_on if "expires_on" in fields else record.expires_on,
        confidentiality=(
            body.confidentiality if "confidentiality" in fields else record.confidentiality
        ),
        tags=tuple(body.tags) if "tags" in fields else tuple(record.tags),
    )


def _category_state(category: DocumentCategory) -> dict[str, object]:
    return {
        "id": str(category.id),
        "module": category.module,
        "code": category.code,
        "name": category.name,
        "group_name": category.group_name,
        "is_active": category.is_active,
    }


def _record_out(record: DocumentRecord) -> DocumentRecordOut:
    asset = record.asset
    if asset is None:
        raise RuntimeError("Document record returned without its technical asset")
    return DocumentRecordOut(
        id=record.document_id,
        company_id=record.company_id,
        module=record.module,
        owner_type=record.owner_type,
        owner_id=record.owner_id,
        owner_label=record.owner_label,
        owner_deleted=record.owner_deleted,
        category_id=record.category_id,
        category_name=record.category_name,
        category_group=record.category_group,
        title=record.title,
        description=record.description,
        reference_code=record.reference_code,
        issuer=record.issuer,
        issued_on=record.issued_on,
        expires_on=record.expires_on,
        confidentiality=cast(Literal["internal", "restricted"], record.confidentiality),
        tags=record.tags,
        version_group_id=record.version_group_id,
        version_number=record.version_number,
        is_current=record.is_current,
        replaces_document_id=record.replaces_document_id,
        business_status=cast(RecordStatus, record.business_status),
        original_filename=asset.original_filename,
        extension=asset.extension,
        content_type=asset.detected_content_type or asset.declared_content_type,
        size_bytes=asset.size_bytes,
        checksum_sha256=asset.checksum_sha256,
        technical_status=cast(DocumentStatus, asset.status),
        failure_code=asset.failure_code,
        upload_expires_at=asset.upload_expires_at,
        scanned_at=asset.scanned_at,
        uploaded_by=asset.uploaded_by,
        created_by=record.created_by,
        updated_by=record.updated_by,
        created_at=record.created_at or asset.created_at,
        updated_at=record.updated_at or asset.updated_at,
        ocr_status=cast(OcrStatus | None, asset.ocr_status),
        ocr_available=asset.ocr_available,
        ocr_failure_code=asset.ocr_failure_code,
        ocr_completed_at=asset.ocr_completed_at,
    )


def _folder_out(folder: DocumentFolder) -> DocumentFolderOut:
    return DocumentFolderOut(
        id=folder.id,
        kind=cast(
            Literal["module", "employee", "category"],
            folder.kind,
        ),
        name=folder.name,
        module=cast(Literal["general", "employees"], folder.module),
        parent_id=folder.parent_id,
        employee_id=folder.employee_id,
        category_id=folder.category_id,
        employee_code=folder.employee_code,
        employee_status=folder.employee_status,
        document_count=folder.document_count,
        active_count=folder.active_count,
        expiring_count=folder.expiring_count,
        expired_count=folder.expired_count,
        latest_document_at=folder.latest_document_at,
        can_upload=folder.can_upload,
    )


def _allowed_document_modules(request: Request, current: CurrentUser) -> set[str]:
    """Return module capabilities without relying on client-visible state.

    The permission dependency records the granted codes on the request for
    ordinary users.  Superusers are authorized by the RBAC use case before
    that state is materialized, so keep the explicit superuser path here as
    well; this also makes direct route invocation behave consistently.
    """
    if current.is_superuser:
        return {"general", "employees"}
    granted = set(getattr(request.state, "granted_permission_codes", ()))
    return {
        *({"general"} if "documents:read" in granted else set()),
        *({"employees"} if "employee_documents:read" in granted else set()),
    }


async def _authorize_record_action(
    record: DocumentRecord,
    *,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    company_id: uuid.UUID,
    action: str,
) -> None:
    """Bind an operation to the permission family of the persisted module."""
    if current.is_superuser:
        return
    family = "employee_documents" if record.module == "employees" else "documents"
    if action == "versions":
        # Version history is part of read access; it is intentionally not a
        # separate capability in the public RBAC catalogue.
        action = "read"
    code = f"{family}:{action}"
    result = await checker.execute(current.id, company_id, code)
    if not result.allowed:
        raise AuthorizationError("No tiene permiso para este documento.", code="forbidden")
    if record.module == "employees" and record.is_restricted and not current.is_superuser:
        restricted = await checker.execute(current.id, company_id, "employee_documents:restricted")
        if not restricted.allowed:
            # Do not disclose the existence of a restricted employee record to
            # a caller who may otherwise read the employee expediente.
            raise NotFoundError("Documento no encontrado.", code="document_not_found")


async def _can_view_restricted(
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    company_id: uuid.UUID,
) -> bool:
    if current.is_superuser:
        return True
    result = await checker.execute(current.id, company_id, "employee_documents:restricted")
    return result.allowed


def _requested_branch_id(request: Request) -> uuid.UUID | None:
    """Parse the optional branch context without trusting raw header values."""
    raw_branch = request.headers.get("X-Branch-ID")
    if not raw_branch:
        return None
    try:
        return uuid.UUID(raw_branch)
    except ValueError as exc:
        raise HTTPException(422, "El encabezado X-Branch-ID no es válido.") from exc


async def _resolve_library_scope(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    *,
    module: str | None,
    allowed_modules: set[str],
) -> tuple[uuid.UUID, uuid.UUID | None, set[str]]:
    """Apply company/branch policy before querying the central library.

    General documents are company-wide and therefore require access to every
    branch.  A user limited to one branch may still use the central library
    for employee records, but only after selecting that branch.
    """
    company_id = effective_company_id(request)
    if (module and module not in allowed_modules) or not allowed_modules:
        return company_id, None, allowed_modules
    branch_id = _requested_branch_id(request)
    context = await resolve_branch_scope(session, current, company_id, branch_id)
    if module == "general" and not context.access_all_branches:
        raise HTTPException(403, "Los documentos generales requieren alcance empresarial completo.")
    if module is None and "general" in allowed_modules and not context.access_all_branches:
        allowed_modules.discard("general")
    return company_id, branch_id, allowed_modules


async def _ensure_record_scope(
    record: DocumentRecord,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> None:
    """Enforce branch scope after resolving a record's persisted module."""
    company_id = effective_company_id(request)
    branch_id = _requested_branch_id(request)
    context = await resolve_branch_scope(session, current, company_id, branch_id)
    if record.module == "general":
        if not context.access_all_branches:
            raise HTTPException(
                403, "Los documentos generales requieren alcance empresarial completo."
            )
        return
    if record.module != "employees" or branch_id is None:
        return
    assignment = await session.scalar(
        select(EmployeeBranchAssignment.id).where(
            EmployeeBranchAssignment.employee_id == record.owner_id,
            EmployeeBranchAssignment.branch_id == branch_id,
            EmployeeBranchAssignment.is_active.is_(True),
            EmployeeBranchAssignment.assigned_until.is_(None),
        )
    )
    if assignment is None:
        raise NotFoundError("Documento no encontrado.", code="document_not_found")


async def _authorize_category_management(
    module: str,
    *,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    company_id: uuid.UUID,
) -> None:
    if current.is_superuser:
        return
    code = (
        "employee_documents:manage_categories" if module == "employees" else "documents:categories"
    )
    result = await checker.execute(current.id, company_id, code)
    if not result.allowed:
        raise AuthorizationError(
            "No tiene permiso para gestionar esta categoría.", code="forbidden"
        )


async def _ensure_employee_confidentiality(
    record: DocumentRecord,
    confidentiality: str,
    *,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    company_id: uuid.UUID,
) -> None:
    """Prevent a replacement from escalating an employee record to restricted."""
    if record.module != "employees" or confidentiality != "restricted" or current.is_superuser:
        return
    result = await checker.execute(current.id, company_id, "employee_documents:restricted")
    if not result.allowed:
        raise AuthorizationError(
            "No tiene permiso para gestionar documentos restringidos.",
            code="employee_document_restricted_forbidden",
        )


@router.post(
    "/uploads",
    response_model=InitiateDocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("documents:upload"))],
)
async def initiate_upload(
    body: InitiateRecordIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    x_company_id: Annotated[uuid.UUID, Header(alias="X-Company-ID")],
) -> InitiateDocumentOut:
    company_id = effective_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    if x_company_id != company_id:
        # The permission dependency resolves and validates the same header;
        # keep this guard explicit so document uploads can never use a fallback tenant.
        raise AuthorizationError(
            "El contexto de empresa no coincide con el encabezado enviado.",
            code="invalid_company_context",
        )
    upload = await record_service.initiate_general(
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
    "",
    response_model=DocumentsPage,
    dependencies=[Depends(require_any_permission("documents:read", "employee_documents:read"))],
)
async def list_documents(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
    module: str | None = Query(None, pattern="^(general|employees)$"),
    owner_type: str | None = Query(None, max_length=32),
    owner_id: uuid.UUID | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    storage_status: DocumentStatus | None = Query(None),
    legacy_status: DocumentStatus | None = Query(None, alias="status"),
    document_status: RecordStatus | None = Query(None),
    confidentiality: str | None = Query(None, pattern="^(internal|restricted)$"),
    expires_within_days: int | None = Query(None, ge=0, le=3650),
    include_versions: bool = Query(False),
    include_deleted: bool = Query(False),
) -> DocumentsPage:
    allowed_modules = _allowed_document_modules(request, current)
    # A caller may ask for one module explicitly, but an unauthorized module
    # must look empty rather than revealing its existence through a count.
    company_id, branch_id, allowed_modules = await _resolve_library_scope(
        request,
        session,
        current,
        module=module,
        allowed_modules=allowed_modules,
    )
    if module and module not in allowed_modules:
        return DocumentsPage(
            items=[],
            meta=PageMeta(page=page, size=size, total=0, pages=1),
        )
    if not allowed_modules:
        return DocumentsPage(
            items=[],
            meta=PageMeta(page=page, size=size, total=0, pages=1),
        )
    effective_module = (
        module if module else (next(iter(allowed_modules)) if len(allowed_modules) == 1 else None)
    )
    items, total = await record_service.list(
        company_id,
        page=page,
        size=size,
        module=effective_module,
        owner_type=owner_type,
        owner_id=owner_id,
        search=search,
        category_id=category_id,
        include_versions=include_versions,
        include_deleted=include_deleted,
        document_status=document_status,
        storage_status=storage_status or legacy_status,
        confidentiality=confidentiality,
        expires_within_days=expires_within_days,
        include_restricted=await _can_view_restricted(current, checker, company_id),
        branch_id=branch_id,
    )
    return DocumentsPage(
        items=[_out(item.asset, item) for item in items if item.asset is not None],
        meta=PageMeta(
            page=page, size=size, total=total, pages=(total + size - 1) // size if total else 1
        ),
    )


@router.post(
    "/library/uploads",
    response_model=InitiateDocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("documents:upload"))],
)
async def initiate_library_upload(
    body: InitiateRecordIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> InitiateDocumentOut:
    company_id = effective_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    upload = await record_service.initiate_general(
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
    "/library",
    response_model=DocumentRecordsPage,
    dependencies=[Depends(require_any_permission("documents:read", "employee_documents:read"))],
)
async def list_library_documents(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    page: int = Query(1, ge=1),
    size: int = Query(24, ge=1, le=100),
    module: str | None = Query(None, pattern="^(general|employees)$"),
    category_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None, max_length=120),
    document_status: str | None = Query(
        None,
        alias="status",
        pattern="^(processing|active|current|expiring|expired|replaced|quarantined|rejected)$",
    ),
    confidentiality: Literal["internal", "restricted"] | None = Query(None),
    include_versions: bool = Query(False),
    expires_within_days: int | None = Query(None, ge=0, le=3650),
) -> DocumentRecordsPage:
    allowed_modules = _allowed_document_modules(request, current)
    company_id, branch_id, allowed_modules = await _resolve_library_scope(
        request,
        session,
        current,
        module=module,
        allowed_modules=allowed_modules,
    )
    if module and module not in allowed_modules:
        return DocumentRecordsPage(items=[], meta=PageMeta(page=page, size=size, total=0, pages=1))
    if not allowed_modules:
        return DocumentRecordsPage(items=[], meta=PageMeta(page=page, size=size, total=0, pages=1))
    effective_module = (
        module if module else (next(iter(allowed_modules)) if len(allowed_modules) == 1 else None)
    )
    items, total = await record_service.list(
        company_id,
        page=page,
        size=size,
        module=effective_module,
        category_id=category_id,
        search=search,
        include_versions=include_versions,
        document_status=document_status,
        expires_within_days=expires_within_days,
        include_restricted=await _can_view_restricted(current, checker, company_id),
        confidentiality=confidentiality,
        branch_id=branch_id,
    )
    return DocumentRecordsPage(
        items=[_record_out(item) for item in items],
        meta=PageMeta(
            page=page, size=size, total=total, pages=(total + size - 1) // size if total else 1
        ),
    )


@router.get(
    "/library/categories",
    response_model=list[DocumentCategoryOut],
    dependencies=[Depends(require_any_permission("documents:read", "employee_documents:read"))],
)
async def list_document_categories(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    module: str | None = Query(None, pattern="^(general|employees)$"),
) -> list[DocumentCategoryOut]:
    allowed_modules = _allowed_document_modules(request, current)
    company_id, branch_id, allowed_modules = await _resolve_library_scope(
        request,
        session,
        current,
        module=module,
        allowed_modules=allowed_modules,
    )
    if module and module not in allowed_modules:
        return []
    if not allowed_modules:
        return []
    effective_module = (
        module if module else (next(iter(allowed_modules)) if len(allowed_modules) == 1 else None)
    )
    include_restricted = await _can_view_restricted(current, checker, company_id)
    categories = await record_service._records.categories(company_id, module=effective_module)
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
            document_count=await record_service._records.count_category_documents(
                item.id, include_restricted=include_restricted, branch_id=branch_id
            ),
        )
        for item in categories
    ]


@router.get(
    "/library/folders",
    response_model=DocumentFoldersPage,
    dependencies=[Depends(require_any_permission("documents:read", "employee_documents:read"))],
)
async def list_library_folders(  # noqa: C901
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    employees: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    parent: DocumentFolderParent = Query("root"),
    employee_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None, max_length=120),
    page: int = Query(1, ge=1),
    size: int = Query(24, ge=1, le=100),
) -> DocumentFoldersPage:
    """List safe, virtual folders for the authorized document library.

    Folder summaries are deliberately separate from the file listing.  This
    lets the UI render a hierarchy without downloading every document and
    keeps all tenant, branch and restricted-document checks in one place.
    """
    allowed_modules = _allowed_document_modules(request, current)
    company_id, branch_id, allowed_modules = await _resolve_library_scope(
        request,
        session,
        current,
        module=(None if parent == "root" else ("employees" if parent == "employee" else parent)),
        allowed_modules=allowed_modules,
    )

    requested_module = (
        None if parent == "root" else ("employees" if parent == "employee" else parent)
    )
    if requested_module is not None and requested_module not in allowed_modules:
        # Explicit folder URLs must not disclose whether an unauthorized
        # module exists for this company.
        raise HTTPException(404, "Carpeta no encontrada.")

    employee_label: str | None = None
    if parent == "employee":
        if employee_id is None:
            raise HTTPException(422, "employee_id es obligatorio para esta carpeta.")
        employee = await employees.get_by_id(employee_id)
        if employee is None or employee.company_id != company_id:
            raise HTTPException(404, "Carpeta no encontrada.")
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
                raise HTTPException(404, "Carpeta no encontrada.")
        employee_label = f"{employee.first_name} {employee.last_name}"
    elif employee_id is not None:
        raise HTTPException(422, "employee_id solo aplica a carpetas de empleado.")

    include_restricted = await _can_view_restricted(current, checker, company_id)
    if current.is_superuser:
        upload_modules = {"general", "employees"}
    else:
        granted = set(getattr(request.state, "granted_permission_codes", ()))
        upload_modules = {
            *({"general"} if "documents:upload" in granted else set()),
            *({"employees"} if "employee_documents:upload" in granted else set()),
        }
    upload_modules.intersection_update(allowed_modules)
    folders, total = await record_service.list_folders(
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

    breadcrumbs = [DocumentBreadcrumbOut(label="Documentos", href="/documents")]
    if parent in {"general", "employees", "employee"}:
        if parent == "general":
            breadcrumbs.append(DocumentBreadcrumbOut(label="General", href="/documents/general"))
        else:
            breadcrumbs.append(
                DocumentBreadcrumbOut(label="Empleados", href="/documents/employees")
            )
            if parent == "employee" and employee_id is not None and employee_label is not None:
                breadcrumbs.append(
                    DocumentBreadcrumbOut(
                        label=employee_label,
                        href=f"/documents/employees/{employee_id}",
                    )
                )
    return DocumentFoldersPage(
        items=[_folder_out(folder) for folder in folders],
        meta=PageMeta(
            page=page,
            size=size,
            total=total,
            pages=(total + size - 1) // size if total else 1,
        ),
        breadcrumbs=breadcrumbs,
    )


@router.post(
    "/library/categories",
    response_model=DocumentCategoryOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_any_permission("documents:categories", "employee_documents:manage_categories")
        )
    ],
)
async def create_document_category(
    body: CreateDocumentCategoryIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> DocumentCategoryOut:
    company_id = effective_company_id(request)
    if body.module == "general":
        await require_company_wide_scope(session, current, company_id)
    else:
        await resolve_branch_scope(session, current, company_id, _requested_branch_id(request))
    await _authorize_category_management(
        body.module, current=current, checker=checker, company_id=company_id
    )
    try:
        category = await record_service._records.add_category(
            DocumentCategory(
                id=uuid.uuid4(),
                company_id=company_id,
                module=body.module,
                code=body.code,
                name=body.name.strip(),
                group_name=body.group_name.strip(),
                description=body.description,
                sort_order=body.sort_order,
                created_by=current.id,
                updated_by=current.id,
            )
        )
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "Ya existe una categoría con ese código o nombre.",
            code="document_category_conflict",
        ) from exc
    await audit.record(
        action="DOCUMENT_CATEGORY_CREATED",
        user_id=current.id,
        company_id=category.company_id,
        resource_type="document_categories",
        resource_id=str(category.id),
        after_state=_category_state(category),
        required=True,
    )
    return DocumentCategoryOut.model_validate(category, from_attributes=True)


@router.patch(
    "/library/categories/{category_id}",
    response_model=DocumentCategoryOut,
    dependencies=[
        Depends(
            require_any_permission("documents:categories", "employee_documents:manage_categories")
        )
    ],
)
async def update_document_category(
    category_id: uuid.UUID,
    body: UpdateDocumentCategoryIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> DocumentCategoryOut:
    company_id = effective_company_id(request)
    category = await record_service._records.get_category(
        category_id, company_id, include_inactive=True
    )
    if category is None:
        raise NotFoundError("Categoría no encontrada.", code="document_category_not_found")
    if category.module == "general":
        await require_company_wide_scope(session, current, company_id)
    else:
        await resolve_branch_scope(session, current, company_id, _requested_branch_id(request))
    await _authorize_category_management(
        category.module, current=current, checker=checker, company_id=company_id
    )
    before = _category_state(category)
    for field in ("name", "group_name", "description", "sort_order", "is_active"):
        value = getattr(body, field)
        if value is not None:
            setattr(category, field, value.strip() if isinstance(value, str) else value)
    category.updated_by = current.id
    try:
        saved = await record_service._records.save_category(category)
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "Ya existe una categoría con ese nombre.", code="document_category_conflict"
        ) from exc
    await audit.record(
        action="DOCUMENT_CATEGORY_UPDATED",
        user_id=current.id,
        company_id=saved.company_id,
        resource_type="document_categories",
        resource_id=str(saved.id),
        before_state=before,
        after_state=_category_state(saved),
        required=True,
    )
    return DocumentCategoryOut.model_validate(saved, from_attributes=True)


@router.get(
    "/library/{document_id}",
    response_model=DocumentRecordOut,
    dependencies=[Depends(require_any_permission("documents:read", "employee_documents:read"))],
)
async def get_library_document(
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> DocumentRecordOut:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id)
    await _ensure_record_scope(record, request, session, current)
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action="read"
    )
    return _record_out(record)


@router.patch(
    "/library/{document_id}",
    response_model=DocumentRecordOut,
    dependencies=[Depends(require_any_permission("documents:update", "employee_documents:update"))],
)
async def update_library_document(
    document_id: uuid.UUID,
    body: UpdateDocumentMetadataIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> DocumentRecordOut:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id)
    await _ensure_record_scope(record, request, session, current)
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action="update"
    )
    return _record_out(
        await record_service.update_metadata(
            company_id,
            document_id,
            current.id,
            _metadata_for_record(body, record),
        )
    )


@router.get(
    "/library/{document_id}/versions",
    response_model=list[DocumentRecordOut],
    dependencies=[Depends(require_any_permission("documents:read", "employee_documents:read"))],
)
async def list_library_versions(
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> list[DocumentRecordOut]:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id)
    await _ensure_record_scope(record, request, session, current)
    action = "versions" if record.module == "employees" else "read"
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action=action
    )
    version_items = await record_service.versions(company_id, document_id)
    return [_record_out(item) for item in version_items]


@router.post(
    "/library/{document_id}/complete",
    response_model=DocumentRecordOut,
    dependencies=[Depends(require_any_permission("documents:upload", "employee_documents:upload"))],
)
async def complete_library_document(
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> DocumentRecordOut:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id)
    await _ensure_record_scope(record, request, session, current)
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action="upload"
    )
    return _record_out(await record_service.activate_version(company_id, document_id, current.id))


@router.post(
    "/library/{document_id}/replace",
    response_model=InitiateDocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("documents:upload", "employee_documents:upload"))],
)
async def replace_library_document(
    document_id: uuid.UUID,
    body: InitiateRecordIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> InitiateDocumentOut:
    company_id = effective_company_id(request)
    previous = await record_service.get(company_id, document_id)
    await _ensure_record_scope(previous, request, session, current)
    await _authorize_record_action(
        previous, current=current, checker=checker, company_id=company_id, action="upload"
    )
    metadata = _metadata_for_record(body, previous)
    await _ensure_employee_confidentiality(
        previous,
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


@router.post(
    "/library/{document_id}/preview-url",
    response_model=DownloadUrlOut,
    dependencies=[
        Depends(require_any_permission("documents:download", "employee_documents:download"))
    ],
)
async def create_preview_url(
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    variant: DownloadVariant = Query("original"),
) -> DownloadUrlOut:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id)
    await _ensure_record_scope(record, request, session, current)
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action="download"
    )
    url, expires_at = await record_service.preview_url(
        company_id, document_id, current.id, variant=variant
    )
    return DownloadUrlOut(url=url, expires_at=expires_at)


@router.post(
    "/library/{document_id}/download-url",
    response_model=DownloadUrlOut,
    dependencies=[
        Depends(require_any_permission("documents:download", "employee_documents:download"))
    ],
)
async def create_library_download_url(
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    variant: DownloadVariant = Query("original"),
) -> DownloadUrlOut:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id)
    await _ensure_record_scope(record, request, session, current)
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action="download"
    )
    url, expires_at = await record_service.download_url(
        company_id, document_id, current.id, variant=variant
    )
    return DownloadUrlOut(url=url, expires_at=expires_at)


# Stable, module-aware aliases for clients that do not use the central
# ``/library`` namespace.  They intentionally delegate to the same record
# service and never expose storage bucket/key details.
@router.patch(
    "/{document_id}/metadata",
    response_model=DocumentRecordOut,
    dependencies=[Depends(require_any_permission("documents:update", "employee_documents:update"))],
)
async def update_document_metadata(
    document_id: uuid.UUID,
    body: UpdateDocumentMetadataIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> DocumentRecordOut:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id)
    await _ensure_record_scope(record, request, session, current)
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action="update"
    )
    return _record_out(
        await record_service.update_metadata(
            company_id,
            document_id,
            current.id,
            _metadata_for_record(body, record),
        )
    )


@router.get(
    "/{document_id}/versions",
    response_model=list[DocumentRecordOut],
    dependencies=[Depends(require_any_permission("documents:read", "employee_documents:read"))],
)
async def list_document_versions(
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> list[DocumentRecordOut]:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id)
    await _ensure_record_scope(record, request, session, current)
    action = "versions" if record.module == "employees" else "read"
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action=action
    )
    version_items = await record_service.versions(company_id, document_id)
    return [_record_out(item) for item in version_items]


@router.post(
    "/{document_id}/replacements/uploads",
    response_model=InitiateDocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission("documents:upload", "employee_documents:upload"))],
)
async def initiate_document_replacement(
    document_id: uuid.UUID,
    body: InitiateRecordIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> InitiateDocumentOut:
    company_id = effective_company_id(request)
    previous = await record_service.get(company_id, document_id)
    await _ensure_record_scope(previous, request, session, current)
    await _authorize_record_action(
        previous, current=current, checker=checker, company_id=company_id, action="upload"
    )
    metadata = _metadata_for_record(body, previous)
    await _ensure_employee_confidentiality(
        previous,
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


@router.post(
    "/{document_id}/preview-url",
    response_model=DownloadUrlOut,
    dependencies=[
        Depends(require_any_permission("documents:download", "employee_documents:download"))
    ],
)
async def preview_document(
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    variant: DownloadVariant = Query("original"),
) -> DownloadUrlOut:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id)
    await _ensure_record_scope(record, request, session, current)
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action="download"
    )
    url, expires_at = await record_service.preview_url(
        company_id, document_id, current.id, variant=variant
    )
    return DownloadUrlOut(url=url, expires_at=expires_at)


@router.delete("/{document_id}", response_model=DeletedRecordOut)
async def delete_document(
    document_id: uuid.UUID,
    body: SoftDeleteRequest,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> DeletedRecordOut:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id, include_deleted=True)
    await _ensure_record_scope(record, request, session, current)
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action="delete"
    )
    deleted = await LifecycleService(SqlAlchemyLifecycleRepository(session)).delete(
        "documents",
        str(document_id),
        company_id=company_id,
        actor_id=current.id,
        reason=body.reason,
        allow_global=current.is_superuser,
    )
    if deleted.operation_applied:
        await audit.record(
            action="LOGICAL_DELETE",
            user_id=current.id,
            company_id=deleted.company_id,
            resource_type="documents",
            resource_id=str(document_id),
            after_state={"deletion_reason": deleted.deletion_reason},
            required=True,
        )
    return DeletedRecordOut.model_validate(deleted, from_attributes=True)


@router.post("/{document_id}/restore", response_model=DeletedRecordOut)
async def restore_document(
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> DeletedRecordOut:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id, include_deleted=True)
    await _ensure_record_scope(record, request, session, current)
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action="restore"
    )
    restored = await LifecycleService(SqlAlchemyLifecycleRepository(session)).restore(
        "documents",
        str(document_id),
        company_id=company_id,
        actor_id=current.id,
        allow_global=current.is_superuser,
    )
    if restored.operation_applied:
        await audit.record(
            action="RESTORE",
            user_id=current.id,
            company_id=restored.company_id,
            resource_type="documents",
            resource_id=str(document_id),
            after_state={"deleted_at": None},
            required=True,
        )
    return DeletedRecordOut.model_validate(restored, from_attributes=True)


@router.post(
    "/{document_id}/complete",
    response_model=DocumentOut,
    dependencies=[Depends(require_any_permission("documents:upload", "employee_documents:upload"))],
)
async def complete_upload(
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> DocumentOut:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id)
    await _ensure_record_scope(record, request, session, current)
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action="upload"
    )
    record = await record_service.activate_version(company_id, document_id, current.id)
    if record.asset is None:
        raise RuntimeError("Document record returned without its technical asset")
    return _out(record.asset, record)


@router.post(
    "/{document_id}/download-url",
    response_model=DownloadUrlOut,
    dependencies=[
        Depends(require_any_permission("documents:download", "employee_documents:download"))
    ],
)
async def create_download_url(
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    variant: DownloadVariant = Query("original"),
) -> DownloadUrlOut:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id)
    await _ensure_record_scope(record, request, session, current)
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action="download"
    )
    url, expires_at = await service.download_url(
        company_id, document_id, current.id, variant=variant
    )
    record_counter(
        "erp.documents.downloads",
        attributes={"variant": str(variant), "status": "issued"},
    )
    return DownloadUrlOut(url=url, expires_at=expires_at)


@router.post(
    "/{document_id}/ocr/retry",
    response_model=DocumentOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(require_any_permission("documents:process", "employee_documents:process"))
    ],
)
async def retry_ocr(
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> DocumentOut:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id)
    await _ensure_record_scope(record, request, session, current)
    action = "process"
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action=action
    )
    asset = await service.retry_ocr(company_id, document_id, current.id)
    record.asset = asset
    return _out(asset, record)


@router.get(
    "/{document_id}",
    response_model=DocumentOut,
    dependencies=[Depends(require_any_permission("documents:read", "employee_documents:read"))],
)
async def get_document(
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    record_service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
) -> DocumentOut:
    company_id = effective_company_id(request)
    record = await record_service.get(company_id, document_id)
    await _ensure_record_scope(record, request, session, current)
    await _authorize_record_action(
        record, current=current, checker=checker, company_id=company_id, action="read"
    )
    asset = await service.get(company_id, document_id)
    record.asset = asset
    return _out(asset, record)
