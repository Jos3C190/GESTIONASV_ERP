"""SQLAlchemy AuditRepository — append-only (add + list only, no update/delete).

The architectural enforcement of append-only is twofold:
1. This class deliberately does NOT implement update() or delete() methods.
2. The API layer does not expose any UPDATE/DELETE endpoint for audit logs.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.audit import AuditLog as DomainLog
from app.infrastructure.models.audit import AuditLog as ORMLog


def _to_domain(orm: ORMLog) -> DomainLog:
    return DomainLog(
        id=orm.id,
        user_id=orm.user_id,
        action=orm.action,
        resource_type=orm.resource_type,
        resource_id=orm.resource_id,
        before_state=orm.before_state,
        after_state=orm.after_state,
        ip_address=orm.ip_address,
        user_agent=orm.user_agent,
        status=orm.status,
        metadata=orm.metadata_,
        created_at=orm.created_at,
    )


class SqlAlchemyAuditRepository:
    """Append-only: only add() and list() exist. No update/delete."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, log: DomainLog) -> DomainLog:
        orm = ORMLog(
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            before_state=log.before_state,
            after_state=log.after_state,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            status=log.status,
            metadata_=log.metadata,
        )
        self._session.add(orm)
        await self._session.flush()
        return _to_domain(orm)

    async def get_by_id(self, log_id: uuid.UUID) -> DomainLog | None:
        result = await self._session.execute(select(ORMLog).where(ORMLog.id == log_id))
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm is not None else None

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[Sequence[DomainLog], bool]:
        """Paginated by offset/limit over (created_at DESC, id DESC)."""
        conditions: list[Any] = []
        if user_id is not None:
            conditions.append(ORMLog.user_id == user_id)
        if action is not None:
            conditions.append(ORMLog.action == action)
        if resource_type is not None:
            conditions.append(ORMLog.resource_type == resource_type)
        if resource_id is not None:
            conditions.append(ORMLog.resource_id == resource_id)
        if status is not None:
            conditions.append(ORMLog.status == status)
        if start_date is not None:
            conditions.append(ORMLog.created_at >= start_date)
        if end_date is not None:
            conditions.append(ORMLog.created_at <= end_date)

        stmt = select(ORMLog)
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = stmt.order_by(ORMLog.created_at.desc(), ORMLog.id.desc()).offset(offset).limit(limit)

        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [_to_domain(o) for o in rows], False

    async def count(
        self,
        *,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        conditions: list[Any] = []
        if user_id is not None:
            conditions.append(ORMLog.user_id == user_id)
        if action is not None:
            conditions.append(ORMLog.action == action)
        if resource_type is not None:
            conditions.append(ORMLog.resource_type == resource_type)
        if resource_id is not None:
            conditions.append(ORMLog.resource_id == resource_id)
        if status is not None:
            conditions.append(ORMLog.status == status)
        if start_date is not None:
            conditions.append(ORMLog.created_at >= start_date)
        if end_date is not None:
            conditions.append(ORMLog.created_at <= end_date)

        stmt = select(func.count(ORMLog.id))
        if conditions:
            stmt = stmt.where(*conditions)
        return int((await self._session.execute(stmt)).scalar_one())


def or_clause(*conditions: Any) -> Any:
    """Build an OR clause from conditions (SQLAlchemy 2.0 style)."""
    from sqlalchemy import or_

    return or_(*conditions)
