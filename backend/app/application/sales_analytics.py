"""Análisis comercial y metas de venta por sucursal (V9a)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.core.exceptions import BusinessRuleError
from app.domain.entities.fiscal_books import Period
from app.domain.entities.sales_analytics import (
    Analysis,
    build_analysis,
    month_start,
    require_goal,
    require_range,
)
from app.domain.ports.sales_analytics_repository import BranchGoal, SalesAnalyticsRepository


def parse_period(value: str) -> Period:
    try:
        return Period.parse(value)
    except ValueError as error:
        raise BusinessRuleError(
            "El mes debe tener la forma AAAA-MM.", code="sales_goal_period_invalid"
        ) from error


class SalesAnalyticsUseCases:
    def __init__(self, repository: SalesAnalyticsRepository) -> None:
        self._repository = repository

    async def analysis(
        self,
        company_id: uuid.UUID,
        branch_ids: tuple[uuid.UUID, ...] | None,
        start: date,
        end: date,
        *,
        costs_visible: bool,
    ) -> Analysis:
        require_range(start, end)
        facts = await self._repository.lines(company_id, branch_ids, start, end)
        returns = await self._repository.returns(company_id, branch_ids, start, end)
        goals = await self._repository.goals(company_id, branch_ids, month_start(start), end)
        result = build_analysis(start, end, facts, returns, goals, costs_visible=costs_visible)
        if goals:
            names = {
                str(item.branch_id): item.branch_name
                for item in await self._repository.month_goals(
                    company_id, branch_ids, month_start(start)
                )
            }
            for bucket in result.by_branch:
                bucket.label = bucket.label or names.get(bucket.key, "Sucursal")
        return result

    async def month_goals(
        self, company_id: uuid.UUID, branch_ids: tuple[uuid.UUID, ...] | None, period_key: str
    ) -> list[BranchGoal]:
        period = parse_period(period_key)
        return await self._repository.month_goals(company_id, branch_ids, period.first)

    async def save_goals(
        self,
        company_id: uuid.UUID,
        branch_ids: tuple[uuid.UUID, ...] | None,
        period_key: str,
        items: list[tuple[uuid.UUID, Decimal | None]],
        actor_id: uuid.UUID,
    ) -> tuple[list[BranchGoal], list[BranchGoal]]:
        """Guarda las metas del mes; devuelve (antes, después) para la bitácora."""

        period = parse_period(period_key)
        before = await self._repository.month_goals(company_id, branch_ids, period.first)
        allowed = {item.branch_id for item in before}
        seen: set[uuid.UUID] = set()
        for branch_id, amount in items:
            if branch_id not in allowed or branch_id in seen:
                raise BusinessRuleError(
                    "Una de las sucursales no existe, está inactiva o está repetida.",
                    code="sales_goal_branch_invalid",
                )
            seen.add(branch_id)
            await self._repository.save_goal(
                company_id,
                branch_id,
                period.first,
                require_goal(amount) if amount is not None else None,
                actor_id,
            )
        after = await self._repository.month_goals(company_id, branch_ids, period.first)
        return before, after
