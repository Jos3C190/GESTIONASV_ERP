"""Enterprise lifecycle endpoints: trash, soft-delete and restore."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.api.v1.company_access import request_company_id, require_company_wide_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
)
from app.api.v1.schemas.common import PageMeta
from app.api.v1.schemas.lifecycle import DeletedRecordOut, DeletedRecordsPage, SoftDeleteRequest
from app.application.audit.audit_service import AuditService
from app.application.lifecycle import LifecycleService
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import AuthorizationError, NotFoundError
from app.infrastructure.models.document_record import DocumentRecordModel
from app.infrastructure.repositories import SqlAlchemyLifecycleRepository

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])


RESOURCE_PERMISSIONS: dict[str, tuple[str, str]] = {
    "companies": ("companies.delete", "companies.restore"),
    "branches": ("branches.delete", "branches.restore"),
    "warehouse_categories": ("warehouse_categories.delete", "warehouse_categories.restore"),
    "warehouses": ("warehouses.delete", "warehouses.restore"),
    "locations": ("locations.delete", "locations.restore"),
    "departments": ("departments:delete", "departments:restore"),
    "employees": ("employees:delete", "employees:restore"),
    "users": ("users:delete", "users:restore"),
    "roles": ("roles:delete", "roles:restore"),
    "permissions": ("permissions:delete", "permissions:restore"),
    "product_categories": ("product_categories:delete", "product_categories:restore"),
    "product_subcategories": ("product_categories:delete", "product_categories:restore"),
    "units": ("units:delete", "units:restore"),
    "products": ("products:delete", "products:restore"),
    "suppliers": ("suppliers:delete", "suppliers:restore"),
    "supplier_contacts": ("suppliers:delete", "suppliers:restore"),
    "documents": ("documents:delete", "documents:restore"),
}


def _service(session: SessionDep) -> LifecycleService:
    return LifecycleService(SqlAlchemyLifecycleRepository(session))


async def _require_resource_permission(
    resource: str,
    action_index: int,
    *,
    current: CurrentUser,
    company_id: uuid.UUID,
    checker: CheckPermissionUseCase,
    document_module: str | None = None,
) -> None:
    codes = RESOURCE_PERMISSIONS.get(resource)
    if codes is None:
        raise AuthorizationError(
            "Este recurso no admite la operación.", code="lifecycle_resource_forbidden"
        )
    if current.is_superuser:
        return
    required_code = codes[action_index]
    if resource == "documents" and document_module == "employees":
        employee_code = ("employee_documents:delete", "employee_documents:restore")[action_index]
        result = await checker.execute(current.id, company_id, employee_code)
        if not result.allowed:
            result = await checker.execute(current.id, company_id, required_code)
    else:
        result = await checker.execute(current.id, company_id, required_code)
    if not result.allowed:
        raise AuthorizationError(
            "No tiene permiso para administrar el ciclo de vida de este registro.",
            code="lifecycle_forbidden",
        )


def _company_record_id(record_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(record_id)
    except ValueError as exc:
        raise NotFoundError("Empresa no encontrada.", code="lifecycle_record_not_found") from exc


async def _operation_company_context(
    resource: str,
    record_id: str,
    *,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> uuid.UUID:
    if resource == "companies":
        if not current.is_superuser:
            raise AuthorizationError(
                "Solo un superadministrador puede eliminar o restaurar empresas.",
                code="company_lifecycle_superuser_required",
            )
        return _company_record_id(record_id)
    if resource == "permissions":
        if not current.is_superuser:
            raise AuthorizationError(
                "Solo un superadministrador puede eliminar o restaurar permisos globales.",
                code="permission_lifecycle_superuser_required",
            )
        return uuid.UUID(int=0)
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    return company_id


@router.get(
    "/trash",
    response_model=DeletedRecordsPage,
)
async def list_trash(  # noqa: C901
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    resource: str | None = Query(None, max_length=64),
    search: str | None = Query(None, max_length=120),
) -> DeletedRecordsPage:
    include_all_companies = resource == "companies"
    document_module: str | None = None
    include_restricted = current.is_superuser
    if include_all_companies:
        if not current.is_superuser:
            raise AuthorizationError(
                "Solo un superadministrador puede consultar empresas eliminadas.",
                code="company_trash_superuser_required",
            )
        company_id = uuid.UUID(int=0)
    elif resource == "permissions":
        if not current.is_superuser:
            raise AuthorizationError(
                "Solo un superadministrador puede consultar permisos eliminados.",
                code="permission_trash_superuser_required",
            )
        company_id = uuid.UUID(int=0)
    elif resource == "documents":
        company_id = request_company_id(request)
        await require_company_wide_scope(session, current, company_id)
        if not current.is_superuser:
            lifecycle_allowed = (
                await checker.execute(current.id, company_id, "lifecycle:read")
            ).allowed
            general_allowed = (
                await checker.execute(current.id, company_id, "documents:restore")
            ).allowed
            employee_allowed = (
                await checker.execute(current.id, company_id, "employee_documents:restore")
            ).allowed
            if not lifecycle_allowed and not general_allowed and not employee_allowed:
                raise AuthorizationError(
                    "No tiene permiso para consultar los documentos en la papelera.",
                    code="lifecycle_forbidden",
                )
            if not general_allowed and not lifecycle_allowed:
                document_module = "employees"
            elif not employee_allowed and not lifecycle_allowed:
                document_module = "general"
            include_restricted = (
                await checker.execute(current.id, company_id, "employee_documents:restricted")
            ).allowed
    else:
        company_id = request_company_id(request)
        await require_company_wide_scope(session, current, company_id)
        if not current.is_superuser:
            result = await checker.execute(current.id, company_id, "lifecycle:read")
            if not result.allowed:
                raise AuthorizationError(
                    "No tiene permiso para consultar la papelera administrativa.",
                    code="lifecycle_forbidden",
                )
    items, total = await _service(session).list_deleted(
        company_id,
        page=page,
        size=size,
        resource=resource,
        search=search,
        include_global=current.is_superuser,
        include_all_companies=include_all_companies,
        document_module=document_module,
        include_restricted=include_restricted,
    )
    return DeletedRecordsPage(
        items=[DeletedRecordOut.model_validate(item, from_attributes=True) for item in items],
        meta=PageMeta(
            page=page,
            size=size,
            total=total,
            pages=(total + size - 1) // size if total else 1,
        ),
    )


@router.delete("/{resource}/{record_id}", response_model=DeletedRecordOut)
async def soft_delete_record(
    resource: str,
    record_id: str,
    body: SoftDeleteRequest,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> DeletedRecordOut:
    company_id = await _operation_company_context(
        resource,
        record_id,
        request=request,
        session=session,
        current=current,
    )
    document_module: str | None = None
    if resource == "documents":
        try:
            document_uuid = uuid.UUID(record_id)
        except ValueError:
            document_uuid = None
        if document_uuid is not None:
            document = await session.scalar(
                select(DocumentRecordModel)
                .where(DocumentRecordModel.id == document_uuid)
                .execution_options(include_deleted=True)
            )
            document_module = document.module if document is not None else None
    await _require_resource_permission(
        resource,
        0,
        current=current,
        company_id=company_id,
        checker=checker,
        document_module=document_module,
    )
    deleted = await _service(session).delete(
        resource,
        record_id,
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
            resource_type=resource,
            resource_id=record_id,
            before_state={
                "label": deleted.label,
                "deleted_at": None,
                "deleted_by": None,
                "deletion_reason": None,
            },
            after_state={
                "label": deleted.label,
                "deleted_at": deleted.deleted_at.isoformat() if deleted.deleted_at else None,
                "deleted_by": str(current.id),
                "deletion_reason": deleted.deletion_reason,
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            required=True,
        )
    return DeletedRecordOut.model_validate(deleted, from_attributes=True)


@router.post("/{resource}/{record_id}/restore", response_model=DeletedRecordOut)
async def restore_record(
    resource: str,
    record_id: str,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: AuditService = Depends(get_audit_service),
) -> DeletedRecordOut:
    company_id = await _operation_company_context(
        resource,
        record_id,
        request=request,
        session=session,
        current=current,
    )
    document_module: str | None = None
    if resource == "documents":
        try:
            document_uuid = uuid.UUID(record_id)
        except ValueError:
            document_uuid = None
        if document_uuid is not None:
            document = await session.scalar(
                select(DocumentRecordModel)
                .where(DocumentRecordModel.id == document_uuid)
                .execution_options(include_deleted=True)
            )
            document_module = document.module if document is not None else None
    await _require_resource_permission(
        resource,
        1,
        current=current,
        company_id=company_id,
        checker=checker,
        document_module=document_module,
    )
    restored = await _service(session).restore(
        resource,
        record_id,
        company_id=company_id,
        actor_id=current.id,
        allow_global=current.is_superuser,
    )
    if restored.operation_applied:
        await audit.record(
            action="RESTORE",
            user_id=current.id,
            company_id=restored.company_id,
            resource_type=resource,
            resource_id=record_id,
            before_state={
                "label": restored.label,
                "deleted_at": restored.deleted_at.isoformat() if restored.deleted_at else None,
                "deleted_by": str(restored.deleted_by) if restored.deleted_by else None,
                "deletion_reason": restored.deletion_reason,
            },
            after_state={
                "label": restored.label,
                "deleted_at": None,
                "deleted_by": None,
                "deletion_reason": None,
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            required=True,
        )
    return DeletedRecordOut.model_validate(restored, from_attributes=True)
