"""Map application exceptions to HTTP responses.

Client messages are generic; details go to logs only (OWASP A05).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.core.logging import get_logger

log = get_logger(__name__)


def _payload(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": code, "message": message})


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    route = getattr(request.scope.get("route"), "path", "unmatched")
    log.warning(
        "app_error",
        code=exc.code,
        message=exc.message,
        route=route,
        method=request.method,
    )
    return _payload(exc.code, exc.message, exc.status_code)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    route = getattr(request.scope.get("route"), "path", "unmatched")
    log.exception("unhandled_exception", route=route, method=request.method)
    return _payload("internal_error", "Error interno del servidor.", 500)


def register_exception_handlers(app: FastAPI) -> None:
    # FastAPI accepts subclass-specific handlers at runtime; Starlette's type
    # alias is intentionally wider and loses that generic relationship.
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
