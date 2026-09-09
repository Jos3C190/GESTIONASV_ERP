"""Application-level exception hierarchy.

These are domain/app errors. The API layer (api/v1/exception_handlers.py) maps
them to HTTP responses with generic client messages and detailed internal logs.
Never leak DB details or stack traces to the client.
"""

from __future__ import annotations


class AppError(Exception):
    """Base. Subclasses set `status_code` and a stable `code` string."""

    status_code: int = 500
    code: str = "app_error"
    message: str = "Unexpected error"

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message
        if code:
            self.code = code


# --- 4xx ---
class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Conflict with current state"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Validation failed"


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_failed"
    message = "Credenciales inválidas"


class AuthorizationError(AppError):
    status_code = 403
    code = "forbidden"
    message = "Acción no permitida"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"
    message = "Demasiados intentos. Intente más tarde."


class BusinessRuleError(AppError):
    status_code = 422
    code = "business_rule"
    message = "Operación no permitida por una regla de negocio"


# --- 5xx ---
class InfrastructureError(AppError):
    status_code = 503
    code = "infrastructure_error"
    message = "Servicio no disponible temporalmente"


class ConcurrencyError(AppError):
    status_code = 409
    code = "concurrency_conflict"
    message = "El recurso fue modificado por otra transacción. Recargue e intente de nuevo."
