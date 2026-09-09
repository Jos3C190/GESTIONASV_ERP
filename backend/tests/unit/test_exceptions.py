"""Unit tests for the application exception hierarchy mapping."""

from __future__ import annotations

from app.core.exceptions import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    BusinessRuleError,
    ConcurrencyError,
    ConflictError,
    InfrastructureError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


def test_status_codes_are_4xx_or_5xx() -> None:
    assert NotFoundError().status_code == 404
    assert ConflictError().status_code == 409
    assert ValidationError().status_code == 422
    assert AuthenticationError().status_code == 401
    assert AuthorizationError().status_code == 403
    assert RateLimitError().status_code == 429
    assert BusinessRuleError().status_code == 422
    assert InfrastructureError().status_code == 503
    assert ConcurrencyError().status_code == 409


def test_app_error_is_base_of_all() -> None:
    for cls in (
        NotFoundError,
        ConflictError,
        ValidationError,
        AuthenticationError,
        AuthorizationError,
        RateLimitError,
        BusinessRuleError,
        InfrastructureError,
        ConcurrencyError,
    ):
        assert issubclass(cls, AppError)


def test_custom_message_and_code() -> None:
    e = NotFoundError("User not found", code="user_not_found")
    assert e.message == "User not found"
    assert e.code == "user_not_found"
