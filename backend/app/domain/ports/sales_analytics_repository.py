"""Puerto del análisis comercial y las metas de venta (V9a)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.domain.entities.sales_analytics import LineFact, ReturnFact


@dataclass(frozen=True, slots=True)
class BranchGoal:
    branch_id: uuid.UUID
    branch_name: str
    amount: Decimal | None


class SalesAnalyticsRepository(Protocol):
    async def lines(
        self,
        company_id: uuid.UUID,
        branch_ids: tuple[uuid.UUID, ...] | None,
        start: date,
        end: date,
    ) -> list[LineFact]: ...

    async def returns(
        self,
        company_id: uuid.UUID,
        branch_ids: tuple[uuid.UUID, ...] | None,
        start: date,
        end: date,
    ) -> list[ReturnFact]: ...

    async def goals(
        self,
        company_id: uuid.UUID,
        branch_ids: tuple[uuid.UUID, ...] | None,
        first: date,
        last: date,
    ) -> dict[uuid.UUID, Decimal]:
        """Suma de las metas de los meses que empiezan entre ``first`` y ``last``."""
        ...

    async def month_goals(
        self, company_id: uuid.UUID, branch_ids: tuple[uuid.UUID, ...] | None, period: date
    ) -> list[BranchGoal]:
        """Sucursales activas del alcance con su meta del mes (o ``None``)."""
        ...

    async def save_goal(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period: date,
        amount: Decimal | None,
        actor_id: uuid.UUID,
    ) -> None:
        """Guarda la meta; ``None`` la quita."""
        ...
