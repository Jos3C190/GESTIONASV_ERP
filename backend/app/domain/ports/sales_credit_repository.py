"""Situación de crédito de un cliente para evaluar un pedido (V5b)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Protocol

from app.domain.entities.sales_credit import CreditSnapshot


class SalesCreditRepository(Protocol):
    async def snapshot(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        exclude_sale_id: uuid.UUID | None,
        today: date,
    ) -> CreditSnapshot: ...
