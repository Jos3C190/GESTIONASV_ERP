"""Use cases for resolving and administering operational branch scope."""

from __future__ import annotations

import uuid

from app.core.exceptions import AuthorizationError, NotFoundError
from app.domain.entities.operational_context import OperationalContext
from app.domain.ports.operational_context_repository import OperationalContextRepository


class GetOperationalContext:
    def __init__(self, repository: OperationalContextRepository) -> None:
        self._repository = repository

    async def execute(
        self, *, user_id: uuid.UUID, company_id: uuid.UUID, is_superuser: bool
    ) -> OperationalContext:
        context = await self._repository.get_context(
            user_id=user_id, company_id=company_id, is_superuser=is_superuser
        )
        if context is None:
            raise AuthorizationError(
                "No tiene acceso a esta empresa.", code="company_access_denied"
            )
        return context


class SelectOperationalBranch:
    def __init__(self, repository: OperationalContextRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        is_superuser: bool,
    ) -> OperationalContext:
        context = await GetOperationalContext(self._repository).execute(
            user_id=user_id, company_id=company_id, is_superuser=is_superuser
        )
        if branch_id is not None and not context.can_access(branch_id):
            raise AuthorizationError(
                "No tiene acceso a esta sucursal.", code="branch_access_denied"
            )
        if branch_id is None and not context.access_all_branches:
            raise AuthorizationError(
                "Debe seleccionar una sucursal autorizada.",
                code="branch_selection_required",
            )
        await self._repository.save_preference(
            user_id=user_id,
            company_id=company_id,
            branch_id=branch_id,
            is_superuser=is_superuser,
        )
        return context


class ReplaceUserBranchAccess:
    def __init__(self, repository: OperationalContextRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        branch_ids: set[uuid.UUID],
        access_all_branches: bool,
        default_branch_id: uuid.UUID | None,
        assigned_by: uuid.UUID,
    ) -> OperationalContext:
        if not access_all_branches and not branch_ids:
            raise AuthorizationError(
                "Debe asignar al menos una sucursal.", code="branch_access_required"
            )
        if (
            default_branch_id is not None
            and default_branch_id not in branch_ids
            and not access_all_branches
        ):
            raise AuthorizationError(
                "La sucursal predeterminada debe estar asignada.",
                code="invalid_default_branch",
            )
        try:
            return await self._repository.replace_branch_access(
                user_id=user_id,
                company_id=company_id,
                branch_ids=branch_ids,
                access_all_branches=access_all_branches,
                default_branch_id=default_branch_id,
                assigned_by=assigned_by,
            )
        except LookupError as exc:
            raise NotFoundError(str(exc), code="branch_scope_not_found") from exc
