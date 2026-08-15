"""Reusable company-boundary authorization for multi-company resources.

The ``X-Company-ID`` header selects an operational context; it never proves
that a resource belongs to that company.  Routers that first load a resource
by its global identifier must compare the resource's persisted company with
the context already authorised for the request.
"""

import uuid

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser
from app.application.organization import GetOperationalContext
from app.domain.entities.operational_context import OperationalContext
from app.infrastructure.models.organization import Company, UserCompany
from app.infrastructure.repositories import SqlAlchemyOperationalContextRepository

EFFECTIVE_COMPANY_STATE_KEY = "effective_company_id"


def set_effective_company_id(request: Request, company_id: uuid.UUID) -> uuid.UUID:
    """Store the authorised company context for downstream resource checks.

    A conflicting value indicates two dependencies attempted to authorise the
    same request under different tenants.  Fail closed instead of silently
    replacing the first context.
    """
    existing = getattr(request.state, EFFECTIVE_COMPANY_STATE_KEY, None)
    if existing is not None and existing != company_id:
        raise HTTPException(403, "El contexto de empresa de la solicitud es inconsistente.")
    setattr(request.state, EFFECTIVE_COMPANY_STATE_KEY, company_id)
    return company_id


def effective_company_id(request: Request) -> uuid.UUID:
    """Return the company context previously authorised for this request."""
    company_id = getattr(request.state, EFFECTIVE_COMPANY_STATE_KEY, None)
    if not isinstance(company_id, uuid.UUID):
        raise HTTPException(403, "El contexto de empresa no ha sido autorizado.")
    return company_id


def require_resource_company(
    request: Request,
    resource_company_id: uuid.UUID | None,
    *,
    not_found_detail: str = "Recurso no encontrado.",
) -> uuid.UUID:
    """Bind a loaded resource to the request's authorised company.

    Return ``404`` for a cross-company mismatch so callers cannot use global
    resource identifiers as a tenant-enumeration oracle.  This check applies
    to superusers too: superuser access bypasses membership, not the explicit
    tenant selected for an individual request.
    """
    company_id = effective_company_id(request)
    if resource_company_id is None or resource_company_id != company_id:
        raise HTTPException(404, not_found_detail)
    return company_id


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


async def authorize_request_company(
    request: Request,
    session: AsyncSession,
    current: CurrentUser,
    company_id: uuid.UUID,
    *,
    require_active: bool = False,
) -> Company:
    """Authorise membership and persist the effective request company."""
    company = await require_company_access(
        session,
        current,
        company_id,
        require_active=require_active,
    )
    set_effective_company_id(request, company_id)
    return company


async def require_resource_company_access(
    request: Request,
    session: AsyncSession,
    current: CurrentUser,
    resource_company_id: uuid.UUID | None,
    *,
    require_active: bool = False,
    not_found_detail: str = "Recurso no encontrado.",
) -> Company:
    """Authorise a loaded resource against the explicit request tenant.

    Use this helper only after obtaining ``resource_company_id`` from trusted
    persisted relationships (for example location -> warehouse -> branch ->
    company), never from the request body itself.
    """
    company_id = require_resource_company(
        request,
        resource_company_id,
        not_found_detail=not_found_detail,
    )
    return await require_company_access(
        session,
        current,
        company_id,
        require_active=require_active,
    )


async def resolve_branch_scope(
    session: AsyncSession,
    current: CurrentUser,
    company_id: uuid.UUID,
    branch_id: uuid.UUID | None,
) -> OperationalContext:
    """Validate both the company boundary and the requested operational scope."""
    await require_company_access(session, current, company_id)
    context = await GetOperationalContext(SqlAlchemyOperationalContextRepository(session)).execute(
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
    return await GetOperationalContext(SqlAlchemyOperationalContextRepository(session)).execute(
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
