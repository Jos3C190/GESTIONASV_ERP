"""Branch scope shared by the fleet, drivers and tracking modules.

Rules (applied identically by every route of the three modules):

* The company is always the one authorised by ``require_permission`` for the
  request (``effective_company_id``); rows of other companies answer 404.
* Users with access to every branch (or superusers) see the whole company.
* A user assigned to the headquarters branch who also holds
  ``fleet:manage_all`` manages the fleet of every branch.
* Everyone else sees only the branches they are assigned to. A row in another
  branch answers 404 so its existence is not disclosed; asking explicitly for
  a branch filter outside the scope answers 403.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.company_access import get_branch_context
from app.api.v1.deps import CurrentUser
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import NotFoundError
from app.infrastructure.models.organization import Branch

MANAGE_ALL_PERMISSION = "fleet:manage_all"


@dataclass(frozen=True, slots=True)
class FleetScope:
    company_id: uuid.UUID
    all_branches: bool
    branch_ids: frozenset[uuid.UUID]

    def allows(self, branch_id: uuid.UUID | None) -> bool:
        return branch_id is not None and (self.all_branches or branch_id in self.branch_ids)

    def list_filter(self, branch_id: uuid.UUID | None) -> list[uuid.UUID] | None:
        """Branches a listing must be restricted to; ``None`` means the whole company."""
        if branch_id is not None:
            if not self.allows(branch_id):
                raise HTTPException(403, "No tiene acceso a esta sucursal.")
            return [branch_id]
        return None if self.all_branches else sorted(self.branch_ids)

    def require(self, branch_id: uuid.UUID | None, *, not_found: str) -> None:
        """Hide rows outside the scope behind a 404."""
        if not self.allows(branch_id):
            raise NotFoundError(not_found, code="not_found")

    def require_target(self, branch_id: uuid.UUID) -> None:
        """Reject moving or creating records in a branch outside the scope."""
        if not self.allows(branch_id):
            raise HTTPException(403, "No tiene acceso a la sucursal indicada.")


async def headquarters_branch_id(session: AsyncSession, company_id: uuid.UUID) -> uuid.UUID | None:
    headquarters: uuid.UUID | None = await session.scalar(
        select(Branch.id).where(
            Branch.company_id == company_id,
            Branch.is_headquarters.is_(True),
            Branch.is_active.is_(True),
            Branch.operational_status == "active",
            Branch.deleted_at.is_(None),
        )
    )
    return headquarters


async def get_fleet_scope(
    session: AsyncSession,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    company_id: uuid.UUID,
) -> FleetScope:
    context = await get_branch_context(session, current, company_id)
    branch_ids = frozenset(branch.id for branch in context.branches)
    if current.is_superuser or context.access_all_branches:
        return FleetScope(company_id, True, branch_ids)
    headquarters = await headquarters_branch_id(session, company_id)
    if headquarters is not None and headquarters in branch_ids:
        decision = await checker.execute(current.id, company_id, MANAGE_ALL_PERMISSION)
        if decision.allowed:
            return FleetScope(company_id, True, branch_ids)
    return FleetScope(company_id, False, branch_ids)
