"""SQLAlchemy RefreshTokenRepository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.auth import RefreshToken as DomainToken
from app.infrastructure.models.auth import RefreshToken as ORMToken


def _to_domain(orm: ORMToken) -> DomainToken:
    return DomainToken(
        id=orm.id,
        user_id=orm.user_id,
        token_hash=orm.token_hash,
        user_agent=orm.user_agent,
        ip_address=orm.ip_address,
        expires_at=orm.expires_at,
        revoked_at=orm.revoked_at,
        rotated_from=orm.rotated_from,
        created_at=orm.created_at,
    )


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: DomainToken) -> DomainToken:
        orm = ORMToken(
            user_id=token.user_id,
            token_hash=token.token_hash,
            user_agent=token.user_agent,
            ip_address=token.ip_address,
            expires_at=token.expires_at,
            rotated_from=token.rotated_from,
        )
        self._session.add(orm)
        await self._session.flush()
        return _to_domain(orm)

    async def get_by_hash(self, token_hash: str) -> DomainToken | None:
        stmt = select(ORMToken).where(ORMToken.token_hash == token_hash)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def revoke(self, token_id: uuid.UUID) -> bool:
        stmt = (
            update(ORMToken)
            .where(ORMToken.id == token_id, ORMToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        result = await self._session.execute(stmt)
        return (cast(CursorResult[Any], result).rowcount or 0) > 0

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        stmt = (
            update(ORMToken)
            .where(ORMToken.user_id == user_id, ORMToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        result = await self._session.execute(stmt)
        return int(cast(CursorResult[Any], result).rowcount or 0)

    async def list_active_for_user(self, user_id: uuid.UUID) -> Sequence[DomainToken]:
        stmt = (
            select(ORMToken)
            .where(ORMToken.user_id == user_id, ORMToken.revoked_at.is_(None))
            .order_by(ORMToken.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_to_domain(o) for o in result.scalars().all()]
