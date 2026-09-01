"""Regression coverage for upgraded framework and cryptography dependencies."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import jwt
import pytest
from app.api.v1.routers.audit_logs import export_audit_logs
from app.core.exceptions import AuthenticationError
from app.domain.entities.audit import AuditLog
from app.domain.entities.user import User
from app.domain.ports.audit_repository import AuditRepository
from app.infrastructure.repositories.token_service import JwtTokenService
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.unit


def test_jwt_service_round_trip_and_rejects_invalid_tokens() -> None:
    service = JwtTokenService(
        secret="security-regression-secret-at-least-32-bytes",
        algorithm="HS256",
        access_ttl_minutes=15,
    )
    user_id = uuid.uuid4()

    token = service.issue_access_token(
        user_id=user_id,
        username="security-user",
        is_superuser=False,
    )
    payload = service.verify_access_token(token)

    assert payload.sub == user_id
    assert payload.username == "security-user"
    assert payload.is_superuser is False

    with pytest.raises(AuthenticationError, match="Token inválido"):
        service.verify_access_token(f"{token}tampered")


def test_jwt_service_rejects_expired_token() -> None:
    secret = "security-regression-secret-at-least-32-bytes"
    service = JwtTokenService(secret=secret, algorithm="HS256")
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "username": "expired-user",
            "is_superuser": False,
            "iat": int((now - timedelta(minutes=2)).timestamp()),
            "exp": int((now - timedelta(minutes=1)).timestamp()),
            "jti": "expired-jti",
            "type": "access",
        },
        secret,
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError, match="Sesión expirada"):
        service.verify_access_token(token)


@pytest.mark.asyncio
async def test_urlencoded_form_field_limit_is_enforced() -> None:
    """Starlette must reject URL-encoded forms that exceed max_fields."""
    app = FastAPI()

    @app.post("/form-limit")
    async def form_limit(request: Request) -> dict[str, int]:
        form = await request.form(max_fields=2)
        return {"fields": len(form)}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/form-limit",
            content="first=1&second=2&third=3",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_multipart_file_limit_is_enforced() -> None:
    app = FastAPI()

    @app.post("/multipart-limit")
    async def multipart_limit(request: Request) -> dict[str, int]:
        form = await request.form(max_files=1, max_fields=1)
        return {"parts": len(form)}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/multipart-limit",
            files=[
                ("first", ("first.csv", b"a,b\n1,2\n", "text/csv")),
                ("second", ("second.csv", b"a,b\n3,4\n", "text/csv")),
            ],
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_fastapi_lifespan_initializes_and_closes_observability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    calls: list[str] = []

    def initialize(service_name: str, *, app: FastAPI | None = None) -> bool:
        assert service_name == "erp-backend"
        assert app is not None
        calls.append("initialize")
        return True

    async def dispose() -> None:
        calls.append("dispose")

    monkeypatch.setattr(main_module, "configure_logging", lambda: None)
    monkeypatch.setattr(main_module, "initialize_observability", initialize)
    monkeypatch.setattr(main_module, "shutdown_observability", lambda: calls.append("shutdown"))
    monkeypatch.setattr(main_module, "dispose_engine", dispose)
    monkeypatch.setattr(main_module.settings, "RUN_MIGRATIONS_ON_STARTUP", False)

    app = FastAPI()
    async with main_module.lifespan(app):
        assert calls == ["initialize"]

    assert calls == ["initialize", "dispose", "shutdown"]


class _AuditExportRepository:
    async def list(self, **_filters: object) -> tuple[list[AuditLog], bool]:
        return (
            [
                AuditLog(
                    id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                    user_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                    action="document.download",
                    resource_type="document",
                    resource_id="safe-id",
                    before_state=None,
                    after_state={"status": "active"},
                    created_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
            ],
            False,
        )


@pytest.mark.asyncio
async def test_audit_export_remains_a_streaming_csv_response() -> None:
    current = User(
        id=uuid.uuid4(),
        username="admin",
        email="admin@example.test",
        password_hash="unused",
        is_superuser=True,
    )
    response = await export_audit_logs(
        session=cast(AsyncSession, object()),
        current=current,
        repo=cast(AuditRepository, _AuditExportRepository()),
        user_id=None,
        company_id=None,
        branch_id=None,
        action=None,
        resource_type=None,
        start_date=None,
        end_date=None,
    )
    chunks = [chunk async for chunk in response.body_iterator]
    body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in chunks)

    assert response.media_type == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == "attachment; filename=audit_logs.csv"
    assert "document.download" in body
    assert "safe-id" in body
