"""Cuentas por cobrar: documentos con su saldo, recibos de cobro y comprobantes de retención."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.domain.entities.sales_receivables import (
    ApplicationRequest,
    PaymentLine,
    ReceiptStatus,
    ReceivableDocument,
)


@dataclass(frozen=True)
class CustomerRef:
    id: uuid.UUID
    code: str
    name: str
    credit_days: int
    credit_limit: Decimal | None
    email: str | None = None
    credit_blocked: bool = False
    credit_block_reason: str | None = None
    credit_blocked_at: datetime | None = None


@dataclass(frozen=True)
class Certificate:
    certificate_number: str
    issued_on: date
    amount: Decimal


@dataclass(frozen=True)
class AccountDocument:
    """Documento por cobrar con su contexto para el estado de cuenta."""

    receivable: ReceivableDocument
    customer_id: uuid.UUID
    sale_id: uuid.UUID
    sale_code: str
    branch_id: uuid.UUID
    status: str
    withholding: Decimal
    certificate: Certificate | None = None


@dataclass(frozen=True)
class Application:
    document_id: uuid.UUID
    control_number: str
    amount: Decimal
    applied_on: date
    document_invalidated: bool


@dataclass(frozen=True)
class Receipt:
    id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    number: int
    received_on: date
    total: Decimal
    notes: str | None
    status: ReceiptStatus
    payments: list[PaymentLine]
    applications: list[Application] = field(default_factory=list)
    annul_reason: str | None = None
    annulled_at: datetime | None = None
    created_at: datetime | None = None

    @property
    def unapplied(self) -> Decimal:
        """Saldo a favor: lo cobrado que no está aplicado a un documento vigente."""

        if self.status is ReceiptStatus.ANNULLED:
            return Decimal("0")
        applied = sum(
            (item.amount for item in self.applications if not item.document_invalidated),
            Decimal("0"),
        )
        return self.total - applied


@dataclass(frozen=True)
class Issuer:
    name: str
    nit: str | None
    nrc: str | None


@dataclass(frozen=True)
class CollectionNote:
    id: uuid.UUID
    note: str
    next_action_on: date | None
    created_by: str
    created_at: datetime


class SalesReceivableRepository(Protocol):
    async def issuer(self, company_id: uuid.UUID) -> Issuer: ...

    async def notes(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> list[CollectionNote]: ...

    async def add_note(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        note: str,
        next_action_on: date | None,
        actor_id: uuid.UUID,
    ) -> None: ...

    async def set_block(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        reason: str | None,
        actor_id: uuid.UUID,
    ) -> None: ...

    async def customer(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, *, lock: bool = False
    ) -> CustomerRef | None: ...

    async def documents(
        self, company_id: uuid.UUID, customer_id: uuid.UUID | None = None
    ) -> list[AccountDocument]: ...

    async def document(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> AccountDocument | None: ...

    async def receipts(
        self, company_id: uuid.UUID, customer_id: uuid.UUID | None = None
    ) -> list[Receipt]: ...

    async def receipt(
        self, company_id: uuid.UUID, receipt_id: uuid.UUID, *, lock: bool = False
    ) -> Receipt | None: ...

    async def receipt_by_key(self, company_id: uuid.UUID, key: str) -> Receipt | None: ...

    async def customers(self, company_id: uuid.UUID, ids: set[uuid.UUID]) -> list[CustomerRef]: ...

    async def create_receipt(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        customer_id: uuid.UUID,
        received_on: date,
        total: Decimal,
        notes: str | None,
        payments: list[PaymentLine],
        applications: list[ApplicationRequest],
        idempotency_key: str,
        actor_id: uuid.UUID,
    ) -> uuid.UUID: ...

    async def add_applications(
        self,
        company_id: uuid.UUID,
        receipt_id: uuid.UUID,
        applications: list[ApplicationRequest],
        applied_on: date,
        actor_id: uuid.UUID,
    ) -> None: ...

    async def annul_receipt(
        self, company_id: uuid.UUID, receipt_id: uuid.UUID, reason: str, actor_id: uuid.UUID
    ) -> None: ...

    async def save_certificate(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        certificate: Certificate,
        actor_id: uuid.UUID,
    ) -> None: ...
