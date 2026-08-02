"""SQLAlchemy adapter for operational company/branch authorization."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.operational_context import AccessibleBranch, OperationalContext
from app.infrastructure.models.organization import Branch, UserBranch, UserCompany


class SqlAlchemyOperationalContextRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_context(
        self, *, user_id: uuid.UUID, company_id: uuid.UUID, is_superuser: bool
    ) -> OperationalContext | None:
        membership = await self._session.get(UserCompany, (user_id, company_id))
        if membership is None and not is_superuser:
            return None

        access_all = is_superuser or bool(
            membership and membership.access_all_branches
        )
        stmt = select(Branch).where(
            Branch.company_id == company_id, Branch.is_active.is_(True)
        )
        if not access_all:
            stmt = stmt.join(
                UserBranch,
                (UserBranch.branch_id == Branch.id)
                & (UserBranch.company_id == Branch.company_id),
            ).where(
                UserBranch.user_id == user_id,
                UserBranch.company_id == company_id,
                UserBranch.is_active.is_(True),
            )
        rows = (await self._session.execute(stmt.order_by(Branch.name))).scalars().all()
        branches = tuple(
            AccessibleBranch(
                id=row.id,
                company_id=row.company_id,
                name=row.name,
                code=row.code,
                is_active=row.is_active,
            )
            for row in rows
        )
        last_branch_id = membership.last_branch_id if membership else None
        if last_branch_id is not None and not any(
            branch.id == last_branch_id for branch in branches
        ):
            last_branch_id = None
        return OperationalContext(
            company_id=company_id,
            access_all_branches=access_all,
            last_branch_id=last_branch_id,
            branches=branches,
        )

    async def save_preference(
        self,
        *,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        is_superuser: bool,
    ) -> None:
        membership = await self._session.get(UserCompany, (user_id, company_id))
        if membership is None:
            if not is_superuser:
                raise LookupError("No existe la membresía de empresa.")
            membership = UserCompany(
                user_id=user_id,
                company_id=company_id,
                access_all_branches=True,
                is_default=False,
            )
            self._session.add(membership)
        membership.last_branch_id = branch_id
        await self._session.flush()

    async def replace_branch_access(
        self,
        *,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        branch_ids: set[uuid.UUID],
        access_all_branches: bool,
        default_branch_id: uuid.UUID | None,
        assigned_by: uuid.UUID,
    ) -> OperationalContext:
        membership = await self._session.get(UserCompany, (user_id, company_id))
        if membership is None:
            raise LookupError("El usuario no pertenece a la empresa.")

        branches_to_validate = set(branch_ids)
        if default_branch_id is not None:
            branches_to_validate.add(default_branch_id)
        if branches_to_validate:
            valid_ids = set(
                (
                    await self._session.execute(
                        select(Branch.id).where(
                            Branch.company_id == company_id,
                            Branch.id.in_(branches_to_validate),
                            Branch.is_active.is_(True),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if valid_ids != branches_to_validate:
                raise LookupError(
                    "Una o más sucursales no existen, están inactivas o pertenecen a otra empresa."
                )

        existing = {
            item.branch_id: item
            for item in (
                await self._session.execute(
                    select(UserBranch).where(
                        UserBranch.user_id == user_id,
                        UserBranch.company_id == company_id,
                    )
                )
            )
            .scalars()
            .all()
        }
        now = datetime.now(UTC)
        for assignment in existing.values():
            assignment.is_default = False
            assignment.is_active = False
            assignment.revoked_at = now
        await self._session.flush()

        for branch_id in branch_ids:
            assignment = existing.get(branch_id)
            if assignment is None:
                assignment = UserBranch(
                    user_id=user_id,
                    company_id=company_id,
                    branch_id=branch_id,
                )
                self._session.add(assignment)
            assignment.assigned_by = assigned_by
            assignment.assigned_at = now
            assignment.revoked_at = None
            assignment.is_active = True
            assignment.is_default = branch_id == default_branch_id

        membership.access_all_branches = access_all_branches
        membership.last_branch_id = default_branch_id
        await self._session.flush()
        context = await self.get_context(
            user_id=user_id, company_id=company_id, is_superuser=False
        )
        if context is None:  # pragma: no cover - guarded by membership above
            raise LookupError("No se pudo resolver el alcance actualizado.")
        return context
