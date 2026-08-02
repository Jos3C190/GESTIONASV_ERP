"""Audit log router — read-only with page-based pagination.

Only GET endpoints. No POST/PUT/PATCH/DELETE — the audit log is append-only
and entries are created internally by AuditService during business operations.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from app.api.v1.company_access import resolve_branch_scope
from app.api.v1.deps import CurrentUser, SessionDep, require_permission
from app.api.v1.schemas.audit import AuditLogOut, AuditLogPage
from app.api.v1.schemas.common import PageMeta
from app.core.exceptions import NotFoundError
from app.domain.entities.audit import AuditLog
from app.domain.ports.audit_repository import AuditRepository

router = APIRouter(prefix="/audit-logs", tags=["audit"])


def _get_audit_repo(session: SessionDep) -> AuditRepository:
    from app.infrastructure.repositories import SqlAlchemyAuditRepository

    return SqlAlchemyAuditRepository(session)


def _to_output(log: AuditLog) -> AuditLogOut:
    return AuditLogOut(
        id=log.id,
        user_id=log.user_id,
        company_id=log.company_id,
        branch_id=log.branch_id,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        before_state=log.before_state,
        after_state=log.after_state,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        status=log.status,
        metadata=log.metadata,
        created_at=log.created_at or datetime.now(UTC),
    )


@router.get(
    "",
    response_model=AuditLogPage,
    status_code=status.HTTP_200_OK,
    summary="Listar bitácora (paginado)",
    dependencies=[Depends(require_permission("logs.view"))],
)
async def list_audit_logs(
    session: SessionDep,
    current: CurrentUser,
    repo: AuditRepository = Depends(_get_audit_repo),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    user_id: uuid.UUID | None = Query(None),
    company_id: uuid.UUID | None = Query(None),
    branch_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    resource_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
) -> AuditLogPage:
    if company_id is None and not current.is_superuser:
        raise NotFoundError(
            "Debe indicar la empresa de la bitácora.", code="company_context_required"
        )
    if company_id is not None:
        await resolve_branch_scope(session, current, company_id, branch_id)
    offset = (page - 1) * size

    logs, _has_more = await repo.list(
        limit=size,
        offset=offset,
        user_id=user_id,
        company_id=company_id,
        branch_id=branch_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status_filter,
        start_date=start_date,
        end_date=end_date,
    )

    total = await repo.count(
        user_id=user_id,
        company_id=company_id,
        branch_id=branch_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status_filter,
        start_date=start_date,
        end_date=end_date,
    )

    pages = (total + size - 1) // size if total else 1

    items = [_to_output(log) for log in logs]

    return AuditLogPage(
        items=items,
        meta=PageMeta(page=page, size=size, total=total, pages=pages),
    )


@router.get(
    "/export",
    dependencies=[Depends(require_permission("logs.export"))],
    response_class=StreamingResponse,
)
async def export_audit_logs(
    session: SessionDep,
    current: CurrentUser,
    repo: AuditRepository = Depends(_get_audit_repo),
    user_id: uuid.UUID | None = Query(None),
    company_id: uuid.UUID | None = Query(None),
    branch_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
) -> StreamingResponse:
    if company_id is None and not current.is_superuser:
        raise NotFoundError(
            "Debe indicar la empresa de la bitácora.", code="company_context_required"
        )
    if company_id is not None:
        await resolve_branch_scope(session, current, company_id, branch_id)
    logs, _ = await repo.list(
        limit=10_000,
        user_id=user_id,
        company_id=company_id,
        branch_id=branch_id,
        action=action,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id_log",
            "id_record",
            "controller",
            "action",
            "original_data",
            "modified_data",
            "id_user",
            "created_at",
        ]
    )
    for log in logs:
        writer.writerow(
            [
                log.id,
                log.resource_id,
                log.resource_type,
                log.action,
                json.dumps(log.before_state, ensure_ascii=False),
                json.dumps(log.after_state, ensure_ascii=False),
                log.user_id,
                log.created_at.isoformat() if log.created_at else "",
            ]
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )


@router.get(
    "/{log_id}",
    response_model=AuditLogOut,
    dependencies=[Depends(require_permission("logs.detail"))],
)
async def get_audit_log(
    log_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    repo: AuditRepository = Depends(_get_audit_repo),
) -> AuditLogOut:
    log = await repo.get_by_id(log_id)
    if log is None:
        raise NotFoundError("Evento de auditoría no encontrado.", code="audit_log_not_found")
    if log.company_id is None:
        if not current.is_superuser:
            raise NotFoundError(
                "Evento de auditoría no encontrado.", code="audit_log_not_found"
            )
    else:
        await resolve_branch_scope(session, current, log.company_id, log.branch_id)
    return _to_output(log)
