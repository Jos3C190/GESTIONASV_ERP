"""Auth router — login, refresh, logout, /me.

Login and refresh are rate-limited per IP (OWASP A07). Refresh tokens are
issued as httpOnly Secure SameSite=Strict cookies AND echoed in the body
once for clients that can't store cookies. Logout is idempotent.
"""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.v1.deps import (
    CurrentUser,
    get_audit_service,
    get_authenticate_user_use_case,
    get_logout_use_case,
    get_password_policy,
    get_refresh_token_repository,
    get_refresh_token_use_case,
    get_user_repository,
)
from app.api.v1.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from app.api.v1.schemas.common import MessageOut
from app.application.audit.audit_service import AuditService
from app.application.auth.authenticate_user import AuthenticateUserUseCase, LoginInput
from app.application.auth.change_password import ChangePasswordInput, ChangePasswordUseCase
from app.application.auth.logout import LogoutInput, LogoutUseCase
from app.application.auth.refresh_token import (
    RefreshInput,
    RefreshTokenUseCase,
)
from app.application.password_policy import PasswordPolicy
from app.core.config import settings
from app.domain.ports.refresh_token_repository import RefreshTokenRepository
from app.domain.ports.user_repository import UserRepository
from app.middlewares.rate_limit import rate_limit_login, rate_limit_refresh

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "erp_refresh_token"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_token,
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="strict",
        path="/api/v1/auth",
        max_age=int(
            # align with refresh ttl (7d)
            7 * 24 * 60 * 60
        ),
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión",
    dependencies=[Depends(rate_limit_login)],
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    use_case: AuthenticateUserUseCase = Depends(get_authenticate_user_use_case),
    audit: AuditService = Depends(get_audit_service),
) -> TokenResponse:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        result = await use_case.execute(
            LoginInput(
                login=payload.login,
                password=payload.password,
                user_agent=ua,
                ip_address=ip,
            )
        )
        await audit.record(
            action="LOGIN_SUCCESS",
            user_id=result.user_id,
            resource_type="auth",
            ip_address=ip,
            user_agent=ua,
        )
        _set_refresh_cookie(response, result.refresh_token)
        return TokenResponse(
            access_token=result.access_token,
            expires_in=result.expires_in_seconds,
            refresh_token=result.refresh_token,
        )
    except Exception as exc:
        await audit.record(
            action="LOGIN_FAILED",
            resource_type="auth",
            ip_address=ip,
            user_agent=ua,
            status="failure",
            metadata={"login": payload.login[:64], "reason": getattr(exc, "code", "error")},
        )
        raise


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotar access token",
    dependencies=[Depends(rate_limit_refresh)],
)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    use_case: RefreshTokenUseCase = Depends(get_refresh_token_use_case),
) -> TokenResponse:
    raw = (body.refresh_token if body and body.refresh_token else None) or refresh_cookie
    if not raw:
        return JSONResponse(
            status_code=401,
            content={"code": "token_invalid", "message": "Refresh token requerido."},
        )
    result = await use_case.execute(
        RefreshInput(
            raw_refresh_token=raw,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    )
    _set_refresh_cookie(response, result.refresh_token)
    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in_seconds,
        refresh_token=result.refresh_token,
    )


@router.post(
    "/logout",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Cerrar sesión",
)
async def logout(
    response: Response,
    body: RefreshRequest | None = None,
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    use_case: LogoutUseCase = Depends(get_logout_use_case),
) -> MessageOut:
    raw = (body.refresh_token if body and body.refresh_token else None) or refresh_cookie
    if raw:
        await use_case.execute(LogoutInput(raw_refresh_token=raw))
    _clear_refresh_cookie(response)
    return MessageOut(message="Sesión cerrada.", code="logout_ok")


@router.get(
    "/me",
    response_model=MeResponse,
    status_code=status.HTTP_200_OK,
    summary="Usuario actual",
)
async def me(current: CurrentUser) -> MeResponse:
    return MeResponse.model_validate(current, from_attributes=True)


@router.get(
    "/me/users",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    summary="Perfil del usuario actual (alias)",
    include_in_schema=False,
)
async def me_user(current: CurrentUser) -> UserOut:
    return UserOut.model_validate(current, from_attributes=True)


@router.post(
    "/change-password",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Cambiar la contraseña del usuario actual",
)
async def change_password(
    payload: ChangePasswordRequest,
    current: CurrentUser,
    users: UserRepository = Depends(get_user_repository),
    sessions: RefreshTokenRepository = Depends(get_refresh_token_repository),
    policy: PasswordPolicy = Depends(get_password_policy),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    use_case = ChangePasswordUseCase(users, sessions, policy)
    await use_case.execute(
        ChangePasswordInput(
            user_id=current.id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    )
    await audit.record(
        action="PASSWORD_CHANGE",
        user_id=current.id,
        resource_type="users",
        resource_id=str(current.id),
        metadata={"password_fields_omitted": True},
    )
    return MessageOut(
        message="Contraseña actualizada. Las sesiones anteriores fueron revocadas.",
        code="password_changed",
    )
