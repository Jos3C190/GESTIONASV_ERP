"""Gestión de cobro: situación de crédito, notas de seguimiento y bloqueo (bloque V5b)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.domain.entities.sales_credit import CreditSnapshot, require_block_reason
from app.domain.ports.sales_credit_repository import SalesCreditRepository
from app.domain.ports.sales_receivable_repository import (
    CollectionNote,
    CustomerRef,
    SalesReceivableRepository,
)

MIN_NOTE = 5
MAX_NOTE = 1000


@dataclass(frozen=True)
class CreditStatus:
    customer: CustomerRef
    snapshot: CreditSnapshot
    notes: list[CollectionNote]


class SalesCollectionUseCases:
    def __init__(
        self, receivables: SalesReceivableRepository, credit: SalesCreditRepository
    ) -> None:
        self._receivables = receivables
        self._credit = credit

    async def _customer(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, *, lock: bool = False
    ) -> CustomerRef:
        customer = await self._receivables.customer(company_id, customer_id, lock=lock)
        if customer is None:
            raise NotFoundError("Cliente no encontrado.", code="sales_customer_not_found")
        return customer

    async def status(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, today: date
    ) -> CreditStatus:
        customer = await self._customer(company_id, customer_id)
        return CreditStatus(
            customer=customer,
            snapshot=await self._credit.snapshot(
                company_id, customer_id, exclude_sale_id=None, today=today
            ),
            notes=await self._receivables.notes(company_id, customer_id),
        )

    async def add_note(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        note: str,
        next_action_on: date | None,
        actor_id: uuid.UUID,
        today: date,
    ) -> str:
        await self._customer(company_id, customer_id)
        text = " ".join(note.split())
        if not MIN_NOTE <= len(text) <= MAX_NOTE:
            raise BusinessRuleError(
                "La nota de cobro va de 5 a 1000 caracteres.", code="sales_collection_note_invalid"
            )
        if next_action_on is not None and next_action_on < today:
            raise BusinessRuleError(
                "La próxima acción no puede quedar en el pasado.",
                code="sales_collection_next_action_invalid",
            )
        await self._receivables.add_note(company_id, customer_id, text, next_action_on, actor_id)
        return text

    async def block(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, reason: str, actor_id: uuid.UUID
    ) -> tuple[CustomerRef, CustomerRef]:
        before = await self._customer(company_id, customer_id, lock=True)
        if before.credit_blocked:
            raise BusinessRuleError(
                "El crédito del cliente ya está bloqueado.", code="sales_credit_already_blocked"
            )
        await self._receivables.set_block(
            company_id, customer_id, require_block_reason(reason), actor_id
        )
        return before, await self._customer(company_id, customer_id)

    async def unblock(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, actor_id: uuid.UUID
    ) -> tuple[CustomerRef, CustomerRef]:
        before = await self._customer(company_id, customer_id, lock=True)
        if not before.credit_blocked:
            raise BusinessRuleError(
                "El crédito del cliente no está bloqueado.", code="sales_credit_not_blocked"
            )
        await self._receivables.set_block(company_id, customer_id, None, actor_id)
        return before, await self._customer(company_id, customer_id)
