"""Cierres de período fiscal en PostgreSQL (V8b2)."""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.fiscal_books import Period
from app.domain.entities.fiscal_period import PeriodClose

_HISTORY = text("""
    SELECT c.id, c.period, c.status, c.summary, c.closed_at, c.reopen_reason, c.reopened_at,
           (SELECT COALESCE(NULLIF(btrim(concat(e.first_name, ' ', e.last_name)), ''), u.username)
            FROM users u LEFT JOIN employees e ON e.user_id = u.id AND e.deleted_at IS NULL
            WHERE u.id = c.closed_by_id LIMIT 1) AS closed_by,
           (SELECT COALESCE(NULLIF(btrim(concat(e.first_name, ' ', e.last_name)), ''), u.username)
            FROM users u LEFT JOIN employees e ON e.user_id = u.id AND e.deleted_at IS NULL
            WHERE u.id = c.reopened_by_id LIMIT 1) AS reopened_by
    FROM fiscal_period_closes c
    WHERE c.company_id = :company_id AND c.period = :period
    ORDER BY c.closed_at DESC, c.id
""")
_CLOSED = text("""
    SELECT 1 FROM fiscal_period_closes
    WHERE company_id = :company_id AND period = :period AND status = 'closed'
""")
_UNSEALED = text("""
    SELECT
      (SELECT count(*) FROM sales_fiscal_documents d
       WHERE d.company_id = :company_id AND d.status IN ('pending', 'contingency')
         AND (d.created_at AT TIME ZONE 'America/El_Salvador')::date BETWEEN :start AND :end)
    + (SELECT count(*) FROM sales_fiscal_returns r
       WHERE r.company_id = :company_id AND r.status IN ('pending', 'contingency')
         AND (r.created_at AT TIME ZONE 'America/El_Salvador')::date BETWEEN :start AND :end)
""")
_INSERT = text("""
    INSERT INTO fiscal_period_closes (company_id, period, summary, closed_by_id)
    VALUES (:company_id, :period, CAST(:summary AS jsonb), :actor_id)
    RETURNING id
""")
_REOPEN = text("""
    UPDATE fiscal_period_closes
    SET status = 'reopened', reopen_reason = :reason, reopened_by_id = :actor_id, reopened_at = now()
    WHERE company_id = :company_id AND id = :close_id AND status = 'closed'
""")


class SqlAlchemyFiscalPeriodRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock(self, company_id: uuid.UUID, period: Period) -> None:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"fiscal_period:{company_id}:{period.key}"},
        )

    async def closed_period(self, company_id: uuid.UUID, day: date) -> Period | None:
        period = Period(day.year, day.month)
        found = await self._session.execute(
            _CLOSED, {"company_id": company_id, "period": period.first}
        )
        return period if found.first() is not None else None

    async def history(self, company_id: uuid.UUID, period: Period) -> list[PeriodClose]:
        rows = await self._session.execute(
            _HISTORY, {"company_id": company_id, "period": period.first}
        )
        return [
            PeriodClose(
                id=row.id,
                period=period,
                status=row.status,
                summary=dict(row.summary or {}),
                closed_by=row.closed_by,
                closed_at=row.closed_at,
                reopen_reason=row.reopen_reason,
                reopened_by=row.reopened_by,
                reopened_at=row.reopened_at,
            )
            for row in rows
        ]

    async def unsealed(self, company_id: uuid.UUID, period: Period) -> int:
        value = await self._session.scalar(
            _UNSEALED, {"company_id": company_id, "start": period.first, "end": period.last}
        )
        return int(value or 0)

    async def close(
        self,
        company_id: uuid.UUID,
        period: Period,
        summary: dict[str, Any],
        actor_id: uuid.UUID,
    ) -> uuid.UUID:
        row = await self._session.execute(
            _INSERT,
            {
                "company_id": company_id,
                "period": period.first,
                "summary": json.dumps(summary),
                "actor_id": actor_id,
            },
        )
        close_id: uuid.UUID = row.scalar_one()
        return close_id

    async def reopen(
        self, company_id: uuid.UUID, close_id: uuid.UUID, reason: str, actor_id: uuid.UUID
    ) -> None:
        await self._session.execute(
            _REOPEN,
            {
                "company_id": company_id,
                "close_id": close_id,
                "reason": reason,
                "actor_id": actor_id,
            },
        )
