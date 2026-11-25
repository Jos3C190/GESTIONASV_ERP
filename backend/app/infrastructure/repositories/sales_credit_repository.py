"""Situación de crédito del cliente: saldo abierto, mora y pedidos a crédito sin facturar."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.sales_credit import ZERO, CreditSnapshot
from app.infrastructure.repositories.sales_receivable_repository import (
    SqlAlchemySalesReceivableRepository,
)

# Pedidos a crédito confirmados que todavía no tienen un documento fiscal vigente.
_PENDING_ORDERS = """
    SELECT COALESCE(sum(s.total), 0)
    FROM sales s
    WHERE s.company_id = :company AND s.customer_id = :customer
      AND s.status = 'confirmed' AND s.payment_terms = 'credit'
      AND (CAST(:exclude AS uuid) IS NULL OR s.id <> :exclude)
      AND NOT EXISTS (
          SELECT 1 FROM sales_fiscal_documents d
          WHERE d.company_id = s.company_id AND d.sale_id = s.id
            AND d.document_type IN ('01', '03')
            AND d.status IN ('pending', 'contingency', 'issued', 'simulated')
      )
"""


class SqlAlchemySalesCreditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._receivables = SqlAlchemySalesReceivableRepository(session)

    async def snapshot(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        exclude_sale_id: uuid.UUID | None,
        today: date,
    ) -> CreditSnapshot:
        customer = (
            await self._session.execute(
                text(
                    "SELECT credit_limit, credit_blocked FROM sales_customers "
                    "WHERE company_id = :company AND id = :customer"
                ),
                {"company": company_id, "customer": customer_id},
            )
        ).one()
        grace = await self._session.scalar(
            text(
                "SELECT credit_overdue_grace_days FROM sales_settings WHERE company_id = :company"
            ),
            {"company": company_id},
        )
        limit_day = today - timedelta(days=int(grace or 0))
        open_balance = ZERO
        overdue = ZERO
        for item in await self._receivables.documents(company_id, customer_id):
            balance = item.receivable.balance
            open_balance += balance
            if balance > ZERO and item.receivable.due_on < limit_day:
                overdue += balance
        pending = await self._session.scalar(
            text(_PENDING_ORDERS),
            {"company": company_id, "customer": customer_id, "exclude": exclude_sale_id},
        )
        return CreditSnapshot(
            credit_limit=customer.credit_limit,
            blocked=bool(customer.credit_blocked),
            open_balance=open_balance,
            pending_orders=Decimal(pending or 0),
            overdue_beyond_grace=overdue,
        )
