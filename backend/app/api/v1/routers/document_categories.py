"""Tenant-scoped document category catalog endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
    require_any_permission,
)
from app.api.v1.schemas.documents import (
    CreateDocumentCategoryIn,
    DocumentCategoryOut,
    UpdateDocumentCategoryIn,
)
from app.application.audit.audit_service import AuditService
from app.application.documents import DocumentRecordService
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.entities.document_record import DocumentCategory

router = APIRouter(prefix="/document-categories", tags=["document-categories"])

_CATEGORY_PERMISSIONS = (
    "documents:categories",
    "employee_documents:manage_categories",
)


def _requested_branch_id(request: Request) -> uuid.UUID | None:
    raw_branch = request.headers.get("X-Branch-ID")
    if not raw_branch:
        return None
    try:
        return uuid.UUID(raw_branch)
    except ValueError as exc:
        raise HTTPException(422, "El encabezado X-Branch-ID no es válido.") from exc


async def _ensure_module_scope(
    module: str,
    *,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
) -> None:
    if module == "general":
        await require_company_wide_scope(session, current, company_id)
    else:
        await resolve_branch_scope(session, current, company_id, _requested_branch_id(request))


async def _authorize_category_action(
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
        # Keep the same generic response for an unauthorized module as for an
        # unknown category so the catalog cannot be used for enumeration.
        raise NotFoundError("Categoría no encontrada.", code="document_category_not_found")


async def _can_view_restricted(
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    company_id: uuid.UUID,
) -> bool:
    if current.is_superuser:
        return True
    return (await checker.execute(current.id, company_id, "employee_documents:restricted")).allowed


def _out(category: DocumentCategory, count: int = 0) -> DocumentCategoryOut:
    return DocumentCategoryOut(
        id=category.id,
        company_id=category.company_id,
        module=category.module,
        code=category.code,
        name=category.name,
        group_name=category.group_name,
        description=category.description,
        sort_order=category.sort_order,
        is_active=category.is_active,
        document_count=count,
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


@router.get(
    "",
    response_model=list[DocumentCategoryOut],
    dependencies=[Depends(require_any_permission(*_CATEGORY_PERMISSIONS))],
)
async def list_categories(
    request: Request,
    session: SessionDep,
    service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    module: str | None = Query(None, pattern="^(general|employees)$"),
    include_inactive: bool = Query(False),
    group: str | None = Query(None, max_length=120),
) -> list[DocumentCategoryOut]:
    allowed = set(getattr(request.state, "granted_permission_codes", ()))
    allowed_modules = (
        {"general", "employees"}
        if current.is_superuser
        else {
            *({"general"} if "documents:categories" in allowed else set()),
            *({"employees"} if "employee_documents:manage_categories" in allowed else set()),
        }
    )
    if module and module not in allowed_modules:
        return []
    if not allowed_modules:
        return []
    company_id = effective_company_id(request)
    branch_id = _requested_branch_id(request)
    context = await resolve_branch_scope(session, current, company_id, branch_id)
    if module == "general" and not context.access_all_branches:
        raise HTTPException(403, "Las categorías generales requieren alcance empresarial completo.")
    if module is None and "general" in allowed_modules and not context.access_all_branches:
        allowed_modules.discard("general")
    if not allowed_modules:
        return []
    effective_module = (
        module if module else (next(iter(allowed_modules)) if len(allowed_modules) == 1 else None)
    )
    include_restricted = await _can_view_restricted(current, checker, company_id)
    categories = await service._records.categories(
        company_id, module=effective_module, include_inactive=include_inactive
    )
    if group:
        normalized = group.strip().casefold()
        categories = [item for item in categories if item.group_name.casefold() == normalized]
    return [
        _out(
            item,
            await service._records.count_category_documents(
                item.id, include_restricted=include_restricted, branch_id=branch_id
            ),
        )
        for item in categories
    ]


@router.post(
    "",
    response_model=DocumentCategoryOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_any_permission(*_CATEGORY_PERMISSIONS))],
)
async def create_category(
    body: CreateDocumentCategoryIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> DocumentCategoryOut:
    await _ensure_module_scope(
        body.module,
        request=request,
        session=session,
        current=current,
        company_id=effective_company_id(request),
    )
    await _authorize_category_action(
        body.module,
        current=current,
        checker=checker,
        company_id=effective_company_id(request),
    )
    try:
        category = await service._records.add_category(
            DocumentCategory(
                id=uuid.uuid4(),
                company_id=effective_company_id(request),
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
    return _out(category)


@router.patch(
    "/{category_id}",
    response_model=DocumentCategoryOut,
    dependencies=[Depends(require_any_permission(*_CATEGORY_PERMISSIONS))],
)
async def update_category(
    category_id: uuid.UUID,
    body: UpdateDocumentCategoryIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> DocumentCategoryOut:
    category = await service._records.get_category(
        category_id, effective_company_id(request), include_inactive=True
    )
    if category is None:
        raise NotFoundError("Categoría no encontrada.", code="document_category_not_found")
    await _ensure_module_scope(
        category.module,
        request=request,
        session=session,
        current=current,
        company_id=effective_company_id(request),
    )
    await _authorize_category_action(
        category.module,
        current=current,
        checker=checker,
        company_id=effective_company_id(request),
    )
    before = _category_state(category)
    for field in ("name", "group_name", "description", "sort_order", "is_active"):
        value = getattr(body, field)
        if value is not None:
            setattr(category, field, value.strip() if isinstance(value, str) else value)
    category.updated_by = current.id
    try:
        saved = await service._records.save_category(category)
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
    return _out(
        saved,
        await service._records.count_category_documents(
            category.id,
            include_restricted=await _can_view_restricted(
                current, checker, effective_company_id(request)
            ),
            branch_id=_requested_branch_id(request),
        ),
    )


async def _set_category_active(
    category_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: DocumentRecordService,
    value: bool,
    checker: CheckPermissionUseCase,
    audit: AuditService,
) -> DocumentCategoryOut:
    category = await service._records.get_category(
        category_id, effective_company_id(request), include_inactive=True
    )
    if category is None:
        raise NotFoundError("Categoría no encontrada.", code="document_category_not_found")
    await _ensure_module_scope(
        category.module,
        request=request,
        session=session,
        current=current,
        company_id=effective_company_id(request),
    )
    await _authorize_category_action(
        category.module,
        current=current,
        checker=checker,
        company_id=effective_company_id(request),
    )
    before = _category_state(category)
    category.is_active = value
    category.updated_by = current.id
    saved = await service._records.save_category(category)
    await audit.record(
        action=("DOCUMENT_CATEGORY_ACTIVATED" if value else "DOCUMENT_CATEGORY_DEACTIVATED"),
        user_id=current.id,
        company_id=saved.company_id,
        resource_type="document_categories",
        resource_id=str(saved.id),
        before_state=before,
        after_state=_category_state(saved),
        required=True,
    )
    return _out(
        saved,
        await service._records.count_category_documents(
            saved.id,
            include_restricted=await _can_view_restricted(
                current, checker, effective_company_id(request)
            ),
            branch_id=_requested_branch_id(request),
        ),
    )


@router.post(
    "/{category_id}/activate",
    response_model=DocumentCategoryOut,
    dependencies=[Depends(require_any_permission(*_CATEGORY_PERMISSIONS))],
)
async def activate_category(
    category_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> DocumentCategoryOut:
    return await _set_category_active(
        category_id, request, session, current, service, True, checker, audit
    )


@router.post(
    "/{category_id}/deactivate",
    response_model=DocumentCategoryOut,
    dependencies=[Depends(require_any_permission(*_CATEGORY_PERMISSIONS))],
)
async def deactivate_category(
    category_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    service: Annotated[DocumentRecordService, Depends(get_document_record_service)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> DocumentCategoryOut:
    return await _set_category_active(
        category_id, request, session, current, service, False, checker, audit
    )


__all__ = ["router"]
