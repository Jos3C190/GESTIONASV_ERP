"""Operational context resolution and user branch-access administration."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.v1.company_access import require_company_wide_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    require_permission,
)
from app.api.v1.schemas.operational_context import (
    AccessibleBranchOut,
    ContextPreferenceIn,
    OperationalContextOut,
    UserBranchAccessIn,
)
from app.application.audit.audit_service import AuditService
from app.application.organization import (
    GetOperationalContext,
    ReplaceUserBranchAccess,
    SelectOperationalBranch,
)
from app.domain.entities.operational_context import OperationalContext
from app.infrastructure.models.user import User as ORMUser
from app.infrastructure.repositories import SqlAlchemyOperationalContextRepository

router = APIRouter(tags=["operational-context"])


def _out(context: OperationalContext) -> OperationalContextOut:
    return OperationalContextOut(
        company_id=context.company_id,
        access_all_branches=context.access_all_branches,
        last_branch_id=context.last_branch_id,
        branches=[
            AccessibleBranchOut(
                id=branch.id,
                company_id=branch.company_id,
                name=branch.name,
                code=branch.code,
                is_active=branch.is_active,
            )
            for branch in context.branches
        ],
    )


@router.get(
    "/operational-contexts/{company_id}", response_model=OperationalContextOut
)
async def get_operational_context(
    company_id: uuid.UUID, session: SessionDep, current: CurrentUser
) -> OperationalContextOut:
    context = await GetOperationalContext(
        SqlAlchemyOperationalContextRepository(session)
    ).execute(
        user_id=current.id,
        company_id=company_id,
        is_superuser=current.is_superuser,
    )
    return _out(context)


@router.patch(
    "/operational-contexts/{company_id}/preference",
    response_model=OperationalContextOut,
)
async def select_operational_branch(
    company_id: uuid.UUID,
    body: ContextPreferenceIn,
    session: SessionDep,
    current: CurrentUser,
) -> OperationalContextOut:
    context = await SelectOperationalBranch(
        SqlAlchemyOperationalContextRepository(session)
    ).execute(
        user_id=current.id,
        company_id=company_id,
        branch_id=body.branch_id,
        is_superuser=current.is_superuser,
    )
    return _out(
        OperationalContext(
            company_id=context.company_id,
            access_all_branches=context.access_all_branches,
            last_branch_id=body.branch_id,
            branches=context.branches,
        )
    )


@router.get(
    "/users/{user_id}/companies/{company_id}/branch-access",
    response_model=OperationalContextOut,
    dependencies=[Depends(require_permission("users.view"))],
)
async def get_user_branch_access(
    user_id: uuid.UUID,
    company_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
) -> OperationalContextOut:
    await require_company_wide_scope(session, current, company_id)
    target = await session.get(ORMUser, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    context = await GetOperationalContext(
        SqlAlchemyOperationalContextRepository(session)
    ).execute(
        user_id=user_id,
        company_id=company_id,
        is_superuser=target.is_superuser,
    )
    return _out(context)


@router.put(
    "/users/{user_id}/companies/{company_id}/branch-access",
    response_model=OperationalContextOut,
    dependencies=[Depends(require_permission("users:update"))],
)
async def replace_user_branch_access(
    user_id: uuid.UUID,
    company_id: uuid.UUID,
    body: UserBranchAccessIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> OperationalContextOut:
    await require_company_wide_scope(session, current, company_id)
    target = await session.get(ORMUser, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if target.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Los superadministradores siempre tienen acceso a todas las sucursales.",
        )

    previous = await GetOperationalContext(
        SqlAlchemyOperationalContextRepository(session)
    ).execute(user_id=user_id, company_id=company_id, is_superuser=False)
    context = await ReplaceUserBranchAccess(
        SqlAlchemyOperationalContextRepository(session)
    ).execute(
        user_id=user_id,
        company_id=company_id,
        branch_ids=set(body.branch_ids),
        access_all_branches=body.access_all_branches,
        default_branch_id=body.default_branch_id,
        assigned_by=current.id,
    )
    await audit.record(
        action="UPDATE_BRANCH_ACCESS",
        user_id=current.id,
        company_id=company_id,
        resource_type="users",
        resource_id=str(user_id),
        before_state={
            "access_all_branches": previous.access_all_branches,
            "branch_ids": [str(branch.id) for branch in previous.branches],
            "default_branch_id": str(previous.last_branch_id)
            if previous.last_branch_id
            else None,
        },
        after_state={
            "access_all_branches": context.access_all_branches,
            "branch_ids": [str(branch.id) for branch in context.branches],
            "default_branch_id": str(context.last_branch_id)
            if context.last_branch_id
            else None,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return _out(context)
