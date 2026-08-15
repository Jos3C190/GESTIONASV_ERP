"""Dependency providers for the API layer.

Centralising providers here keeps routers thin and makes testing trivial: tests
override a single dependency to swap a real repo for an in-memory fake.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.audit.audit_service import AuditService
from app.application.auth.authenticate_user import AuthenticateUserUseCase
from app.application.auth.get_current_user import GetCurrentUserUseCase
from app.application.auth.logout import LogoutUseCase
from app.application.auth.refresh_token import RefreshTokenUseCase
from app.application.auth.register_user import RegisterUserUseCase
from app.application.password_policy import PasswordPolicy
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.domain.entities.user import User
from app.domain.ports.audit_repository import AuditRepository
from app.domain.ports.permission_repository import PermissionRepository
from app.domain.ports.refresh_token_repository import RefreshTokenRepository
from app.domain.ports.role_repository import RoleRepository
from app.domain.ports.token_service import TokenService
from app.domain.ports.user_repository import UserRepository
from app.infrastructure.db.session import get_async_session
from app.infrastructure.repositories import (
    JwtTokenService,
    SqlAlchemyPermissionRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyRoleRepository,
    SqlAlchemyUserRepository,
)

# Type aliases used widely in routers.
SessionDep = Annotated[AsyncSession, Depends(get_async_session)]

_bearer = HTTPBearer(auto_error=False)


# -------- repository / service factories --------
def get_user_repository(session: SessionDep) -> UserRepository:
    return SqlAlchemyUserRepository(session)


def get_refresh_token_repository(session: SessionDep) -> RefreshTokenRepository:
    return SqlAlchemyRefreshTokenRepository(session)


def get_role_repository(session: SessionDep) -> RoleRepository:
    return SqlAlchemyRoleRepository(session)


def get_permission_repository(session: SessionDep) -> PermissionRepository:
    return SqlAlchemyPermissionRepository(session)


def get_audit_repository(session: SessionDep) -> AuditRepository:
    from app.infrastructure.repositories import SqlAlchemyAuditRepository

    return SqlAlchemyAuditRepository(session)


def get_audit_service(
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repository)],
) -> AuditService:
    return AuditService(audit_repo)


def get_token_service() -> TokenService:
    return JwtTokenService()


def get_password_policy() -> PasswordPolicy:
    return PasswordPolicy()


# -------- use case providers --------
def get_authenticate_user_use_case(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    sessions: Annotated[RefreshTokenRepository, Depends(get_refresh_token_repository)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> AuthenticateUserUseCase:
    return AuthenticateUserUseCase(users, sessions, tokens)


def get_refresh_token_use_case(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    sessions: Annotated[RefreshTokenRepository, Depends(get_refresh_token_repository)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(users, sessions, tokens)


def get_logout_use_case(
    sessions: Annotated[RefreshTokenRepository, Depends(get_refresh_token_repository)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> LogoutUseCase:
    return LogoutUseCase(sessions, tokens)


def get_register_user_use_case(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    policy: Annotated[PasswordPolicy, Depends(get_password_policy)],
) -> RegisterUserUseCase:
    return RegisterUserUseCase(users, policy)


def get_current_user_use_case(
    users: Annotated[UserRepository, Depends(get_user_repository)],
) -> GetCurrentUserUseCase:
    return GetCurrentUserUseCase(users)


def get_check_permission_use_case(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    roles: Annotated[RoleRepository, Depends(get_role_repository)],
) -> CheckPermissionUseCase:
    return CheckPermissionUseCase(users, roles)


# -------- authenticated user dependency --------
async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    """Resolve the Bearer token to a User. Raises 401 if missing/invalid."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("No autenticado.", code="not_authenticated")
    payload = tokens.verify_access_token(credentials.credentials)
    use_case = GetCurrentUserUseCase(users)
    result = await use_case.execute(payload.sub)
    # Stash the resolved user on the request state for downstream deps.
    request.state.user = result.user
    return result.user


CurrentUser = Annotated[User, Depends(get_current_user)]


# -------- require_permission dependency --------
def require_permission(required_code: str):
    """FastAPI dependency factory. Usage:

        @router.post("/users", dependencies=[Depends(require_permission("users:create"))])

    Superusers always pass. Non-superusers get their effective permissions
    computed from the DB. Raises 403 (AuthorizationError) if not granted.
    """

    async def _checker(
        request: Request,
        session: SessionDep,
        current: CurrentUser,
        checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    ) -> User:
        raw_company = request.headers.get("X-Company-ID")
        try:
            if raw_company:
                company_id = uuid.UUID(raw_company)
            else:
                from app.infrastructure.models.organization import UserCompany

                membership = await session.scalar(
                    select(UserCompany)
                    .where(UserCompany.user_id == current.id)
                    .order_by(UserCompany.is_default.desc(), UserCompany.company_id)
                    .limit(1)
                )
                if membership is None:
                    raise AuthorizationError(
                        "Seleccione una empresa para continuar.", code="company_context_required"
                    )
                company_id = membership.company_id
        except ValueError as exc:
            raise AuthorizationError(
                "El contexto de empresa no es válido.", code="invalid_company_context"
            ) from exc
        result = await checker.execute(current.id, company_id, required_code)
        if not result.allowed:
            from app.core.logging import get_logger

            get_logger(__name__).warning(
                "access_denied",
                user_id=str(current.id),
                required_permission=required_code,
                reason=result.reason,
            )
            raise AuthorizationError(f"Permiso requerido: {required_code}", code="forbidden")
        # Permission assignment alone is not proof of a current company
        # membership (stale/corrupt role rows must fail closed).  Validate the
        # company and membership before persisting the effective tenant so
        # resource routers can bind globally addressed rows to the same tenant.
        from app.api.v1.company_access import authorize_request_company

        await authorize_request_company(request, session, current, company_id)
        return current

    return _checker


__all__ = [
    "CurrentUser",
    "SessionDep",
    "get_authenticate_user_use_case",
    "get_check_permission_use_case",
    "get_current_user",
    "get_current_user_use_case",
    "get_logout_use_case",
    "get_password_policy",
    "get_permission_repository",
    "get_refresh_token_repository",
    "get_refresh_token_use_case",
    "get_register_user_use_case",
    "get_role_repository",
    "get_token_service",
    "get_user_repository",
    "require_permission",
]
