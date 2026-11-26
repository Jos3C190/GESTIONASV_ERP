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
    PaymentMethod,
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
class Refund:
    """Reintegro de dinero desde el saldo a favor de un recibo (V8a)."""

    id: uuid.UUID
    receipt_id: uuid.UUID
    number: int
    refunded_on: date
    amount: Decimal
    method: PaymentMethod
    reference: str | None
    reason: str
    status: ReceiptStatus
    annul_reason: str | None = None
    annulled_at: datetime | None = None


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
    released: Decimal = Decimal("0")
    """Lo aplicado que volvió porque una nota o un retorno dejaron el documento pagado de más."""
    refunds: list[Refund] = field(default_factory=list)

    @property
    def refunded(self) -> Decimal:
        return sum(
            (item.amount for item in self.refunds if item.status is ReceiptStatus.ISSUED),
            Decimal("0"),
        )

    @property
    def unapplied(self) -> Decimal:
        """Saldo a favor: lo cobrado que no está aplicado a un documento vigente ni reintegrado."""

        if self.status is ReceiptStatus.ANNULLED:
            return Decimal("0")
        applied = sum(
            (item.amount for item in self.applications if not item.document_invalidated),
            Decimal("0"),
        )
        return self.total - applied + self.released - self.refunded


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

    async def refund(
        self, company_id: uuid.UUID, refund_id: uuid.UUID, *, lock: bool = False
    ) -> Refund | None: ...

    async def refund_by_key(self, company_id: uuid.UUID, key: str) -> Refund | None: ...

    async def create_refund(
        self,
        *,
        company_id: uuid.UUID,
        receipt: Receipt,
        refunded_on: date,
        amount: Decimal,
        method: PaymentMethod,
        reference: str | None,
        reason: str,
        idempotency_key: str,
        actor_id: uuid.UUID,
    ) -> uuid.UUID: ...

    async def annul_refund(
        self, company_id: uuid.UUID, refund_id: uuid.UUID, reason: str, actor_id: uuid.UUID
    ) -> None: ...

    async def save_certificate(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        certificate: Certificate,
        actor_id: uuid.UUID,
    ) -> None: ...
