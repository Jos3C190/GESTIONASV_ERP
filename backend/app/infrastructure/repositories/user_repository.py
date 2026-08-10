"""SQLAlchemy UserRepository — concrete implementation of the domain port.

Converts between ORM models and domain entities. The application layer only
sees domain entities, never ORM objects.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User as DomainUser
from app.infrastructure.models.auth import PasswordResetToken, RefreshToken
from app.infrastructure.models.organization import UserBranch, UserCompany
from app.infrastructure.models.user import User as ORMUser


def _to_domain(orm: ORMUser) -> DomainUser:
    return DomainUser(
        id=orm.id,
        username=orm.username,
        email=orm.email,
        password_hash=orm.password_hash,
        is_active=orm.is_active,
        is_superuser=orm.is_superuser,
        mfa_enabled=orm.mfa_enabled,
        last_login_at=orm.last_login_at,
        failed_login_attempts=orm.failed_login_attempts,
        locked_until=orm.locked_until,
        password_changed_at=orm.password_changed_at,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        deleted_at=orm.deleted_at,
    )


class SqlAlchemyUserRepository:
    """Concrete UserRepository backed by SQLAlchemy async session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _revoke_auth_credentials(self, user_id: uuid.UUID, *, revoked_at: datetime) -> None:
        await self._session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        await self._session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=revoked_at)
        )

    async def get_by_id(self, user_id: uuid.UUID) -> DomainUser | None:
        stmt = select(ORMUser).where(ORMUser.id == user_id, ORMUser.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def get_by_email(self, email: str) -> DomainUser | None:
        stmt = select(ORMUser).where(
            func.lower(ORMUser.email) == email.lower(),
            ORMUser.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def get_by_username(self, username: str) -> DomainUser | None:
        stmt = select(ORMUser).where(
            func.lower(ORMUser.username) == username.lower(),
            ORMUser.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def get_by_email_or_username(self, login: str) -> DomainUser | None:
        stmt = select(ORMUser).where(
            or_(
                func.lower(ORMUser.email) == login.lower(),
                func.lower(ORMUser.username) == login.lower(),
            ),
            ORMUser.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def list_active(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
        status_filter: str | None = None,
        company_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> tuple[Sequence[DomainUser], int]:
        base = select(ORMUser).where(ORMUser.deleted_at.is_(None))
        count_base = select(func.count(ORMUser.id)).where(ORMUser.deleted_at.is_(None))
        if company_id is not None:
            base = base.join(UserCompany, UserCompany.user_id == ORMUser.id).where(
                UserCompany.company_id == company_id
            )
            count_base = count_base.join(UserCompany, UserCompany.user_id == ORMUser.id).where(
                UserCompany.company_id == company_id
            )
        if branch_id is not None:
            access_condition = or_(
                ORMUser.is_superuser.is_(True),
                UserCompany.access_all_branches.is_(True),
                UserBranch.branch_id.is_not(None),
            )
            join_condition = (
                (UserBranch.user_id == ORMUser.id)
                & (UserBranch.company_id == company_id)
                & (UserBranch.branch_id == branch_id)
                & UserBranch.is_active.is_(True)
            )
            base = base.outerjoin(UserBranch, join_condition).where(access_condition)
            count_base = count_base.outerjoin(UserBranch, join_condition).where(access_condition)
        if search:
            like = f"%{search}%"
            cond = or_(ORMUser.username.ilike(like), ORMUser.email.ilike(like))
            base = base.where(cond)
            count_base = count_base.where(cond)
        now = datetime.now(UTC)
        if status_filter == "active":
            cond = ORMUser.is_active.is_(True) & or_(
                ORMUser.locked_until.is_(None), ORMUser.locked_until <= now
            )
            base = base.where(cond)
            count_base = count_base.where(cond)
        elif status_filter == "inactive":
            base = base.where(ORMUser.is_active.is_(False))
            count_base = count_base.where(ORMUser.is_active.is_(False))
        elif status_filter == "superuser":
            base = base.where(ORMUser.is_superuser.is_(True))
            count_base = count_base.where(ORMUser.is_superuser.is_(True))
        base = base.order_by(ORMUser.created_at.desc()).offset(offset).limit(limit)
        items = (await self._session.execute(base)).scalars().all()
        total = int((await self._session.execute(count_base)).scalar_one())
        return [_to_domain(o) for o in items], total

    async def count_active_superadmins(self) -> int:
        stmt = select(func.count(ORMUser.id)).where(
            ORMUser.is_superuser.is_(True),
            ORMUser.is_active.is_(True),
            ORMUser.deleted_at.is_(None),
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def add(self, user: DomainUser) -> DomainUser:
        orm = ORMUser(
            username=user.username,
            email=user.email,
            password_hash=user.password_hash,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            mfa_enabled=user.mfa_enabled,
        )
        self._session.add(orm)
        await self._session.flush()
        return _to_domain(orm)

    async def update(self, user: DomainUser) -> DomainUser:
        stmt = (
            update(ORMUser)
            .where(ORMUser.id == user.id, ORMUser.deleted_at.is_(None))
            .values(
                password_hash=user.password_hash,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                last_login_at=user.last_login_at,
                failed_login_attempts=user.failed_login_attempts,
                locked_until=user.locked_until,
                password_changed_at=user.password_changed_at,
            )
            .returning(ORMUser)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            raise LookupError(f"User {user.id} not found")
        if not user.is_active:
            await self._revoke_auth_credentials(user.id, revoked_at=datetime.now(UTC))
        return _to_domain(orm)

    async def deactivate(self, user_id: uuid.UUID) -> bool:
        revoked_at = datetime.now(UTC)
        stmt = (
            update(ORMUser)
            .where(
                ORMUser.id == user_id,
                ORMUser.deleted_at.is_(None),
                ORMUser.is_active.is_(True),
            )
            .values(is_active=False)
        )
        result = await self._session.execute(stmt)
        changed = (result.rowcount or 0) > 0
        if changed:
            await self._revoke_auth_credentials(user_id, revoked_at=revoked_at)
        return changed
