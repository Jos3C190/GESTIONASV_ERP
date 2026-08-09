"""Reusable company-boundary authorization for multi-company resources."""

import uuid

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser
from app.application.organization import GetOperationalContext
from app.domain.entities.operational_context import OperationalContext
from app.infrastructure.models.organization import Company, UserCompany
from app.infrastructure.repositories import SqlAlchemyOperationalContextRepository


def request_company_id(request: Request) -> uuid.UUID:
    """Return the explicit company context sent by the authenticated client."""
    raw = request.headers.get("X-Company-ID")
    if not raw:
        raise HTTPException(400, "Seleccione una empresa para continuar.")
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(400, "El contexto de empresa no es válido.") from exc


async def request_company_id_or_default(
    request: Request, session: AsyncSession, current: CurrentUser
) -> uuid.UUID:
    """Resolve an explicit context or the user's default membership during bootstrap."""
    raw = request.headers.get("X-Company-ID")
    if raw:
        return request_company_id(request)
    membership = await session.scalar(
        select(UserCompany)
        .where(UserCompany.user_id == current.id)
        .order_by(UserCompany.is_default.desc(), UserCompany.company_id)
        .limit(1)
    )
    if membership is None:
        raise HTTPException(403, "El usuario no tiene una empresa asignada.")
    return membership.company_id


async def require_company_access(
    session: AsyncSession,
    current: CurrentUser,
    company_id: uuid.UUID,
    *,
    require_active: bool = False,
) -> Company:
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "Empresa no encontrada.")
    if (
        not current.is_superuser
        and await session.get(UserCompany, (current.id, company_id)) is None
    ):
        raise HTTPException(403, "No tiene acceso a esta empresa.")
    if require_active and not company.is_active:
        raise HTTPException(409, "La empresa está inactiva.")
    return company


async def resolve_branch_scope(
    session: AsyncSession,
    current: CurrentUser,
    company_id: uuid.UUID,
    branch_id: uuid.UUID | None,
) -> OperationalContext:
    """Validate both the company boundary and the requested operational scope."""
    await require_company_access(session, current, company_id)
    context = await GetOperationalContext(
        SqlAlchemyOperationalContextRepository(session)
    ).execute(
        user_id=current.id,
        company_id=company_id,
        is_superuser=current.is_superuser,
    )
    if branch_id is None:
        if not context.access_all_branches:
            raise HTTPException(403, "Debe seleccionar una sucursal autorizada.")
        return context
    if not context.can_access(branch_id):
        raise HTTPException(403, "No tiene acceso a esta sucursal.")
    return context


async def get_branch_context(
    session: AsyncSession, current: CurrentUser, company_id: uuid.UUID
) -> OperationalContext:
    """Return accessible branches without requiring an active selection."""
    await require_company_access(session, current, company_id)
    return await GetOperationalContext(
        SqlAlchemyOperationalContextRepository(session)
    ).execute(
        user_id=current.id,
        company_id=company_id,
        is_superuser=current.is_superuser,
    )


async def require_company_wide_scope(
    session: AsyncSession, current: CurrentUser, company_id: uuid.UUID
) -> OperationalContext:
    context = await resolve_branch_scope(session, current, company_id, None)
    if not context.access_all_branches:
        raise HTTPException(403, "Esta operación requiere alcance de todas las sucursales.")
    return context
