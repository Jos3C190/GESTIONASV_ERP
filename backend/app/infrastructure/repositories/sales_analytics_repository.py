"""Consultas del análisis comercial y metas de venta (V9a)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.sales_analytics import LineFact, ReturnFact
from app.domain.ports.sales_analytics_repository import BranchGoal

# Documentos de venta vigentes: sellados, simulados o en contingencia; ni fallidos, ni rechazados,
# ni invalidados, ni reemplazados. Montos sin IVA: en factura el gravado trae el IVA incluido.
_LINES = text("""
    WITH docs AS (
        SELECT d.id, d.sale_id, d.branch_id,
               (COALESCE(d.issued_at, d.created_at) AT TIME ZONE 'America/El_Salvador') AS at_local
        FROM sales_fiscal_documents d
        WHERE d.company_id = :company_id AND d.document_type IN ('01', '03')
          AND d.status IN ('issued', 'simulated', 'contingency')
          AND d.superseded_by_id IS NULL AND d.sale_id IS NOT NULL
          AND (CAST(:branches AS uuid[]) IS NULL OR d.branch_id = ANY(:branches))
          AND (COALESCE(d.issued_at, d.created_at) AT TIME ZONE 'America/El_Salvador')::date
              BETWEEN :start AND :end
    )
    SELECT docs.id AS document_id, docs.at_local::date AS day,
           extract(hour FROM docs.at_local)::int AS hour,
           docs.branch_id, b.name AS branch_name, s.customer_id, c.name AS customer_name,
           COALESCE(cat.name, 'Sin categoría') AS category,
           l.product_id::text || ':' || COALESCE(l.variant_id::text, '') AS product_key,
           l.product_name, l.quantity, l.unit_name,
           l.not_subject + l.exempt + l.taxed - COALESCE(l.vat_item, 0) AS net,
           COALESCE(
             (SELECT sum(a.applied_total_cost)
              FROM sales_delivery_lines dl
              JOIN sales_deliveries dv ON dv.company_id = dl.company_id AND dv.id = dl.delivery_id
              JOIN sales_delivery_allocations a
                ON a.company_id = dl.company_id AND a.delivery_line_id = dl.id
              WHERE dl.company_id = l.company_id AND dl.sale_line_id = l.id
                AND dv.status = 'confirmed'),
             COALESCE(l.cost, 0) * l.quantity
           ) AS cost
    FROM docs
    JOIN sales s ON s.id = docs.sale_id
    JOIN sales_lines l ON l.company_id = s.company_id AND l.sale_id = s.id
    JOIN branches b ON b.id = docs.branch_id
    JOIN sales_customers c ON c.company_id = s.company_id AND c.id = s.customer_id
    LEFT JOIN products p ON p.id_product = l.product_id
    LEFT JOIN categories cat ON cat.id_category = p.id_category
    ORDER BY docs.at_local, l.line_number
""")

_RETURNS = text("""
    SELECT (COALESCE(n.issued_at, n.created_at) AT TIME ZONE 'America/El_Salvador')::date AS day,
           n.branch_id, COALESCE(sum(nl.amount), 0) AS net
    FROM sales_fiscal_documents n
    JOIN sales_fiscal_note_lines nl ON nl.company_id = n.company_id AND nl.note_id = n.id
    WHERE n.company_id = :company_id AND n.document_type = '05'
      AND n.status IN ('issued', 'simulated', 'contingency') AND n.superseded_by_id IS NULL
      AND (CAST(:branches AS uuid[]) IS NULL OR n.branch_id = ANY(:branches))
      AND (COALESCE(n.issued_at, n.created_at) AT TIME ZONE 'America/El_Salvador')::date
          BETWEEN :start AND :end
    GROUP BY 1, 2
    UNION ALL
    SELECT (COALESCE(r.issued_at, r.created_at) AT TIME ZONE 'America/El_Salvador')::date AS day,
           d.branch_id, COALESCE(sum(rl.amount - rl.vat), 0) AS net
    FROM sales_fiscal_returns r
    JOIN sales_fiscal_documents d ON d.company_id = r.company_id AND d.id = r.document_id
    JOIN sales_fiscal_return_lines rl ON rl.company_id = r.company_id AND rl.return_id = r.id
    WHERE r.company_id = :company_id AND r.status IN ('issued', 'simulated', 'contingency')
      AND COALESCE(r.annul_status, '') <> 'accepted'
      AND (CAST(:branches AS uuid[]) IS NULL OR d.branch_id = ANY(:branches))
      AND (COALESCE(r.issued_at, r.created_at) AT TIME ZONE 'America/El_Salvador')::date
          BETWEEN :start AND :end
    GROUP BY 1, 2
""")

_GOALS = text("""
    SELECT branch_id, sum(amount) AS amount FROM sales_branch_goals
    WHERE company_id = :company_id AND period BETWEEN :first AND :last
      AND (CAST(:branches AS uuid[]) IS NULL OR branch_id = ANY(:branches))
    GROUP BY branch_id
""")

_MONTH_GOALS = text("""
    SELECT b.id, b.name, g.amount
    FROM branches b
    LEFT JOIN sales_branch_goals g
      ON g.company_id = b.company_id AND g.branch_id = b.id AND g.period = :period
    WHERE b.company_id = :company_id AND b.is_active
      AND (CAST(:branches AS uuid[]) IS NULL OR b.id = ANY(:branches))
    ORDER BY b.name
""")

_UPSERT = text("""
    INSERT INTO sales_branch_goals (company_id, branch_id, period, amount, updated_by_id)
    VALUES (:company_id, :branch_id, :period, :amount, :actor_id)
    ON CONFLICT (company_id, branch_id, period)
    DO UPDATE SET amount = EXCLUDED.amount, updated_by_id = EXCLUDED.updated_by_id,
                  updated_at = now()
""")

_DELETE = text("""
    DELETE FROM sales_branch_goals
    WHERE company_id = :company_id AND branch_id = :branch_id AND period = :period
""")


def _ids(branch_ids: tuple[uuid.UUID, ...] | None) -> list[uuid.UUID] | None:
    return list(branch_ids) if branch_ids is not None else None


class SqlAlchemySalesAnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lines(
        self,
        company_id: uuid.UUID,
        branch_ids: tuple[uuid.UUID, ...] | None,
        start: date,
        end: date,
    ) -> list[LineFact]:
        rows = await self._session.execute(
            _LINES,
            {"company_id": company_id, "branches": _ids(branch_ids), "start": start, "end": end},
        )
        return [
            LineFact(
                document_id=row.document_id,
                day=row.day,
                hour=int(row.hour),
                branch_id=row.branch_id,
                branch_name=row.branch_name,
                customer_id=row.customer_id,
                customer_name=row.customer_name,
                category=row.category,
                product_key=row.product_key,
                product_name=row.product_name,
                quantity=Decimal(row.quantity),
                unit_name=row.unit_name,
                net=Decimal(row.net),
                cost=Decimal(row.cost),
            )
            for row in rows
        ]

    async def returns(
        self,
        company_id: uuid.UUID,
        branch_ids: tuple[uuid.UUID, ...] | None,
        start: date,
        end: date,
    ) -> list[ReturnFact]:
        rows = await self._session.execute(
            _RETURNS,
            {"company_id": company_id, "branches": _ids(branch_ids), "start": start, "end": end},
        )
        return [ReturnFact(row.day, row.branch_id, Decimal(row.net)) for row in rows]

    async def goals(
        self,
        company_id: uuid.UUID,
        branch_ids: tuple[uuid.UUID, ...] | None,
        first: date,
        last: date,
    ) -> dict[uuid.UUID, Decimal]:
        rows = await self._session.execute(
            _GOALS,
            {"company_id": company_id, "branches": _ids(branch_ids), "first": first, "last": last},
        )
        return {row.branch_id: Decimal(row.amount) for row in rows}

    async def month_goals(
        self, company_id: uuid.UUID, branch_ids: tuple[uuid.UUID, ...] | None, period: date
    ) -> list[BranchGoal]:
        rows = await self._session.execute(
            _MONTH_GOALS,
            {"company_id": company_id, "branches": _ids(branch_ids), "period": period},
        )
        return [
            BranchGoal(row.id, row.name, Decimal(row.amount) if row.amount is not None else None)
            for row in rows
        ]

    async def save_goal(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period: date,
        amount: Decimal | None,
        actor_id: uuid.UUID,
    ) -> None:
        params = {"company_id": company_id, "branch_id": branch_id, "period": period}
        if amount is None:
            await self._session.execute(_DELETE, params)
        else:
            await self._session.execute(_UPSERT, {**params, "amount": amount, "actor_id": actor_id})
