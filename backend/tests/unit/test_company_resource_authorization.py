"""Company-boundary checks for resources addressed by a global identifier."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.api.v1.company_access import (
    authorize_request_company,
    effective_company_id,
    require_resource_company,
    require_resource_company_access,
    set_effective_company_id,
)
from app.api.v1.deps import require_permission
from app.application.rbac.check_permission import PermissionCheckResult
from app.core.exceptions import AuthorizationError
from app.domain.entities.user import User
from fastapi import HTTPException
from starlette.requests import Request

pytestmark = pytest.mark.unit


def _request(company_id: uuid.UUID | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if company_id is not None:
        headers.append((b"x-company-id", str(company_id).encode("ascii")))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def _user(*, is_superuser: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        username="company-scope-test",
        email="scope@example.com",
        password_hash="not-used",
        is_superuser=is_superuser,
    )


def test_effective_company_must_be_authorized_before_resource_lookup() -> None:
    with pytest.raises(HTTPException) as error:
        effective_company_id(_request(uuid.uuid4()))

    assert error.value.status_code == 403
    assert "autorizado" in error.value.detail


def test_effective_company_is_idempotent_but_cannot_be_replaced() -> None:
    company_id = uuid.uuid4()
    request = _request(company_id)

    assert set_effective_company_id(request, company_id) == company_id
    assert set_effective_company_id(request, company_id) == company_id

    with pytest.raises(HTTPException) as error:
        set_effective_company_id(request, uuid.uuid4())

    assert error.value.status_code == 403
    assert effective_company_id(request) == company_id


def test_resource_must_belong_to_effective_company() -> None:
    company_id = uuid.uuid4()
    request = _request(company_id)
    set_effective_company_id(request, company_id)

    assert require_resource_company(request, company_id) == company_id


def test_cross_company_resource_is_hidden_even_from_superuser_context() -> None:
    selected_company_id = uuid.uuid4()
    resource_company_id = uuid.uuid4()
    request = _request(selected_company_id)
    set_effective_company_id(request, selected_company_id)

    with pytest.raises(HTTPException) as error:
        require_resource_company(
            request,
            resource_company_id,
            not_found_detail="Ubicación no encontrada.",
        )

    assert error.value.status_code == 404
    assert error.value.detail == "Ubicación no encontrada."


def test_resource_without_resolvable_company_fails_closed() -> None:
    request = _request(uuid.uuid4())
    set_effective_company_id(request, uuid.UUID(request.headers["x-company-id"]))

    with pytest.raises(HTTPException) as error:
        require_resource_company(request, None)

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_permission_dependency_persists_the_authorized_company() -> None:
    company_id = uuid.uuid4()
    request = _request(company_id)
    user = _user()
    company = SimpleNamespace(id=company_id, is_active=True)
    membership = SimpleNamespace(user_id=user.id, company_id=company_id)
    session = AsyncMock()
    session.get.side_effect = [company, membership]
    checker = SimpleNamespace(
        execute=AsyncMock(return_value=PermissionCheckResult(True, "granted"))
    )
    dependency = require_permission("locations.view")

    result = await dependency(request, session, user, checker)

    assert result.username == "company-scope-test"
    assert checker.execute.await_args.args[1:] == (company_id, "locations.view")
    assert effective_company_id(request) == company_id


@pytest.mark.asyncio
async def test_permission_without_current_company_membership_fails_closed() -> None:
    company_id = uuid.uuid4()
    request = _request(company_id)
    session = AsyncMock()
    session.get.side_effect = [SimpleNamespace(id=company_id, is_active=True), None]
    checker = SimpleNamespace(
        execute=AsyncMock(return_value=PermissionCheckResult(True, "granted"))
    )

    with pytest.raises(HTTPException) as error:
        await require_permission("locations.view")(request, session, _user(), checker)

    assert error.value.status_code == 403
    with pytest.raises(HTTPException):
        effective_company_id(request)


@pytest.mark.asyncio
async def test_superuser_cannot_authorize_a_nonexistent_company_context() -> None:
    company_id = uuid.uuid4()
    request = _request(company_id)
    session = AsyncMock()
    session.get.return_value = None
    checker = SimpleNamespace(
        execute=AsyncMock(return_value=PermissionCheckResult(True, "superuser"))
    )

    with pytest.raises(HTTPException) as error:
        await require_permission("locations.view")(
            request,
            session,
            _user(is_superuser=True),
            checker,
        )

    assert error.value.status_code == 404
    with pytest.raises(HTTPException):
        effective_company_id(request)


@pytest.mark.asyncio
async def test_denied_permission_does_not_persist_company_context() -> None:
    request = _request(uuid.uuid4())
    checker = SimpleNamespace(
        execute=AsyncMock(return_value=PermissionCheckResult(False, "not_granted"))
    )
    dependency = require_permission("locations.update")

    with pytest.raises(AuthorizationError):
        await dependency(request, AsyncMock(), _user(), checker)

    with pytest.raises(HTTPException) as error:
        effective_company_id(request)
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_authorize_request_company_sets_context_only_after_membership_check() -> None:
    company_id = uuid.uuid4()
    company = SimpleNamespace(id=company_id, is_active=True)
    membership = SimpleNamespace(user_id=uuid.uuid4(), company_id=company_id)
    session = AsyncMock()
    session.get.side_effect = [company, membership]
    request = _request(company_id)

    result = await authorize_request_company(
        request,
        session,
        _user(),
        company_id,
        require_active=True,
    )

    assert result is company
    assert effective_company_id(request) == company_id


@pytest.mark.asyncio
async def test_resource_access_uses_persisted_company_not_header_alone() -> None:
    selected_company_id = uuid.uuid4()
    request = _request(selected_company_id)
    set_effective_company_id(request, selected_company_id)
    session = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await require_resource_company_access(
            request,
            session,
            _user(is_superuser=True),
            uuid.uuid4(),
            not_found_detail="Ubicación no encontrada.",
        )

    assert error.value.status_code == 404
    session.get.assert_not_awaited()
