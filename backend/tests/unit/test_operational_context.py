"""Unit tests for company/branch operational-context rules."""

from __future__ import annotations

import uuid

import pytest
from app.application.organization import (
    GetOperationalContext,
    ReplaceUserBranchAccess,
    SelectOperationalBranch,
)
from app.core.exceptions import AuthorizationError
from app.domain.entities.operational_context import (
    AccessibleBranch,
    OperationalContext,
)


class FakeOperationalContextRepository:
    def __init__(self, context: OperationalContext | None) -> None:
        self.context = context
        self.saved_branch_id: uuid.UUID | None = None

    async def get_context(self, **_: object) -> OperationalContext | None:
        return self.context

    async def save_preference(self, *, branch_id: uuid.UUID | None, **_: object) -> None:
        self.saved_branch_id = branch_id

    async def replace_branch_access(
        self,
        *,
        company_id: uuid.UUID,
        branch_ids: set[uuid.UUID],
        access_all_branches: bool,
        default_branch_id: uuid.UUID | None,
        **_: object,
    ) -> OperationalContext:
        assert self.context is not None
        branches = tuple(
            branch for branch in self.context.branches if branch.id in branch_ids
        )
        self.context = OperationalContext(
            company_id=company_id,
            access_all_branches=access_all_branches,
            last_branch_id=default_branch_id,
            branches=branches,
        )
        return self.context


def make_context(*, access_all: bool = False) -> OperationalContext:
    company_id = uuid.uuid4()
    return OperationalContext(
        company_id=company_id,
        access_all_branches=access_all,
        last_branch_id=None,
        branches=(
            AccessibleBranch(
                id=uuid.uuid4(),
                company_id=company_id,
                name="Sucursal Centro",
                code="CENTRO",
                is_active=True,
            ),
        ),
    )


async def test_company_membership_is_required() -> None:
    repository = FakeOperationalContextRepository(None)
    with pytest.raises(AuthorizationError) as exc:
        await GetOperationalContext(repository).execute(
            user_id=uuid.uuid4(), company_id=uuid.uuid4(), is_superuser=False
        )
    assert exc.value.code == "company_access_denied"


async def test_restricted_user_must_select_an_authorized_branch() -> None:
    context = make_context()
    repository = FakeOperationalContextRepository(context)
    with pytest.raises(AuthorizationError) as exc:
        await SelectOperationalBranch(repository).execute(
            user_id=uuid.uuid4(),
            company_id=context.company_id,
            branch_id=None,
            is_superuser=False,
        )
    assert exc.value.code == "branch_selection_required"


async def test_rejects_branch_id_manipulation() -> None:
    context = make_context()
    repository = FakeOperationalContextRepository(context)
    with pytest.raises(AuthorizationError) as exc:
        await SelectOperationalBranch(repository).execute(
            user_id=uuid.uuid4(),
            company_id=context.company_id,
            branch_id=uuid.uuid4(),
            is_superuser=False,
        )
    assert exc.value.code == "branch_access_denied"


async def test_all_branch_scope_allows_corporate_view() -> None:
    context = make_context(access_all=True)
    repository = FakeOperationalContextRepository(context)
    await SelectOperationalBranch(repository).execute(
        user_id=uuid.uuid4(),
        company_id=context.company_id,
        branch_id=None,
        is_superuser=False,
    )
    assert repository.saved_branch_id is None


async def test_default_branch_must_be_explicitly_assigned() -> None:
    context = make_context()
    repository = FakeOperationalContextRepository(context)
    with pytest.raises(AuthorizationError) as exc:
        await ReplaceUserBranchAccess(repository).execute(
            user_id=uuid.uuid4(),
            company_id=context.company_id,
            branch_ids={context.branches[0].id},
            access_all_branches=False,
            default_branch_id=uuid.uuid4(),
            assigned_by=uuid.uuid4(),
        )
    assert exc.value.code == "invalid_default_branch"
