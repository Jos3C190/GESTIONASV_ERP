"""Cartera, estados de cuenta y recibos de cobro (bloque V5a)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domain.entities.sales_receivables import (
    ZERO,
    AgingBucket,
    ApplicationRequest,
    PaymentLine,
    PaymentMethod,
    ReceiptStatus,
    aging,
    require_annul_reason,
    validate_applications,
    validate_payments,
)
from app.domain.entities.sales_return_fiscal import validate_refund
from app.domain.ports.sales_receivable_repository import (
    AccountDocument,
    Certificate,
    CustomerRef,
    Issuer,
    Receipt,
    Refund,
    SalesReceivableRepository,
)

MIN_KEY = 8


@dataclass(frozen=True)
class CustomerSummary:
    customer: CustomerRef
    balance: Decimal
    overdue: Decimal
    credit: Decimal
    aging: dict[AgingBucket, Decimal]
    oldest_due: date | None


@dataclass(frozen=True)
class Account:
    customer: CustomerRef
    documents: list[AccountDocument]
    receipts: list[Receipt]
    balance: Decimal
    overdue: Decimal
    credit: Decimal
    aging: dict[AgingBucket, Decimal]


def _not_found() -> NotFoundError:
    return NotFoundError("Cliente no encontrado.", code="sales_customer_not_found")


def _visible(document: AccountDocument) -> bool:
    """En la cuenta aparecen los documentos con saldo o con algo cobrado."""

    receivable = document.receivable
    return receivable.balance > ZERO or receivable.applied > ZERO


class SalesReceivableUseCases:
    def __init__(self, repository: SalesReceivableRepository) -> None:
        self._repository = repository

    async def portfolio(self, company_id: uuid.UUID, today: date) -> list[CustomerSummary]:
        documents = await self._repository.documents(company_id)
        receipts = await self._repository.receipts(company_id)
        by_customer: dict[uuid.UUID, list[AccountDocument]] = {}
        for document in documents:
            by_customer.setdefault(document.customer_id, []).append(document)
        credit_by_customer: dict[uuid.UUID, Decimal] = {}
        for receipt in receipts:
            if receipt.unapplied > ZERO:
                credit_by_customer[receipt.customer_id] = credit_by_customer.get(
                    receipt.customer_id, ZERO
                ) + (receipt.unapplied)
        ids = {cid for cid, docs in by_customer.items() if any(_visible(d) for d in docs)}
        ids |= set(credit_by_customer)
        summaries = []
        for customer in await self._repository.customers(company_id, ids):
            docs = [item.receivable for item in by_customer.get(customer.id, [])]
            open_docs = [doc for doc in docs if doc.balance > ZERO]
            summaries.append(
                CustomerSummary(
                    customer=customer,
                    balance=sum((doc.balance for doc in open_docs), ZERO),
                    overdue=sum((doc.balance for doc in open_docs if doc.overdue(today)), ZERO),
                    credit=credit_by_customer.get(customer.id, ZERO),
                    aging=aging(open_docs, today),
                    oldest_due=min((doc.due_on for doc in open_docs), default=None),
                )
            )
        return sorted(summaries, key=lambda item: (-item.overdue, -item.balance))

    async def account(self, company_id: uuid.UUID, customer_id: uuid.UUID, today: date) -> Account:
        customer = await self._repository.customer(company_id, customer_id)
        if customer is None:
            raise _not_found()
        documents = [
            item
            for item in await self._repository.documents(company_id, customer_id)
            if _visible(item)
        ]
        receipts = await self._repository.receipts(company_id, customer_id)
        open_docs = [item.receivable for item in documents if item.receivable.balance > ZERO]
        return Account(
            customer=customer,
            documents=documents,
            receipts=receipts,
            balance=sum((doc.balance for doc in open_docs), ZERO),
            overdue=sum((doc.balance for doc in open_docs if doc.overdue(today)), ZERO),
            credit=sum((receipt.unapplied for receipt in receipts), ZERO),
            aging=aging(open_docs, today),
        )

    async def document(self, company_id: uuid.UUID, document_id: uuid.UUID) -> AccountDocument:
        found = await self._repository.document(company_id, document_id)
        if found is None:
            raise NotFoundError(
                "El documento no es una cuenta por cobrar.", code="sales_receivable_not_found"
            )
        return found

    async def receipt(self, company_id: uuid.UUID, receipt_id: uuid.UUID) -> Receipt:
        found = await self._repository.receipt(company_id, receipt_id)
        if found is None:
            raise NotFoundError("Recibo no encontrado.", code="sales_receipt_not_found")
        return found

    async def issuer(self, company_id: uuid.UUID) -> Issuer:
        return await self._repository.issuer(company_id)

    async def printable(
        self, company_id: uuid.UUID, receipt_id: uuid.UUID
    ) -> tuple[Receipt, CustomerRef, Issuer]:
        receipt = await self.receipt(company_id, receipt_id)
        customer = await self._repository.customer(company_id, receipt.customer_id)
        if customer is None:
            raise _not_found()
        return receipt, customer, await self._repository.issuer(company_id)

    async def _balances(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> dict[object, Decimal]:
        return {
            item.receivable.id: item.receivable.balance
            for item in await self._repository.documents(company_id, customer_id)
            if item.receivable.balance > ZERO
        }

    async def register(
        self,
        company_id: uuid.UUID,
        *,
        branch_id: uuid.UUID,
        customer_id: uuid.UUID,
        received_on: date,
        payments: list[PaymentLine],
        applications: list[ApplicationRequest],
        notes: str | None,
        idempotency_key: str,
        actor_id: uuid.UUID,
        today: date,
    ) -> tuple[Receipt, bool]:
        """Registra el recibo; si la llave ya se usó devuelve el mismo recibo (reintento)."""

        if len(idempotency_key) < MIN_KEY:
            raise BusinessRuleError(
                "La llave de idempotencia es demasiado corta.", code="sales_receipt_key_invalid"
            )
        previous = await self._repository.receipt_by_key(company_id, idempotency_key)
        if previous is not None:
            if previous.customer_id != customer_id:
                raise ConflictError(
                    "La llave ya se usó para otro recibo.", code="sales_receipt_key_conflict"
                )
            return previous, False
        if received_on > today:
            raise BusinessRuleError(
                "La fecha del cobro no puede ser futura.", code="sales_receipt_date_invalid"
            )
        if await self._repository.customer(company_id, customer_id, lock=True) is None:
            raise _not_found()
        clean_payments, total = validate_payments(payments)
        clean = validate_applications(
            applications, await self._balances(company_id, customer_id), total
        )
        receipt_id = await self._repository.create_receipt(
            company_id=company_id,
            branch_id=branch_id,
            customer_id=customer_id,
            received_on=received_on,
            total=total,
            notes=(notes or "").strip()[:300] or None,
            payments=clean_payments,
            applications=clean,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
        )
        return await self.receipt(company_id, receipt_id), True

    async def apply_credit(
        self,
        company_id: uuid.UUID,
        receipt_id: uuid.UUID,
        applications: list[ApplicationRequest],
        actor_id: uuid.UUID,
        today: date,
    ) -> Receipt:
        """Aplica a otros documentos el saldo a favor que dejó un recibo."""

        receipt = await self._repository.receipt(company_id, receipt_id, lock=True)
        if receipt is None:
            raise NotFoundError("Recibo no encontrado.", code="sales_receipt_not_found")
        if receipt.status is not ReceiptStatus.ISSUED:
            raise BusinessRuleError(
                "Un recibo anulado no tiene saldo a favor.", code="sales_receipt_annulled"
            )
        await self._repository.customer(company_id, receipt.customer_id, lock=True)
        if not applications:
            raise BusinessRuleError(
                "Indica a qué documentos aplicar el saldo a favor.",
                code="sales_receipt_applications_required",
            )
        clean = validate_applications(
            applications, await self._balances(company_id, receipt.customer_id), receipt.unapplied
        )
        await self._repository.add_applications(company_id, receipt_id, clean, today, actor_id)
        return await self.receipt(company_id, receipt_id)

    async def annul(
        self, company_id: uuid.UUID, receipt_id: uuid.UUID, reason: str, actor_id: uuid.UUID
    ) -> tuple[Receipt, Receipt]:
        """Anula el recibo y devuelve (antes, después): los saldos aplicados se restituyen."""

        before = await self._repository.receipt(company_id, receipt_id, lock=True)
        if before is None:
            raise NotFoundError("Recibo no encontrado.", code="sales_receipt_not_found")
        if before.status is not ReceiptStatus.ISSUED:
            raise BusinessRuleError("El recibo ya está anulado.", code="sales_receipt_annulled")
        await self._repository.annul_receipt(
            company_id, receipt_id, require_annul_reason(reason), actor_id
        )
        return before, await self.receipt(company_id, receipt_id)

    async def register_refund(
        self,
        company_id: uuid.UUID,
        receipt_id: uuid.UUID,
        *,
        refunded_on: date,
        amount: Decimal,
        method: PaymentMethod,
        reference: str | None,
        reason: str,
        idempotency_key: str,
        actor_id: uuid.UUID,
        today: date,
    ) -> tuple[Receipt, Refund, bool]:
        """Devuelve dinero al cliente desde el saldo a favor del recibo (V8a)."""

        if len(idempotency_key) < MIN_KEY:
            raise BusinessRuleError(
                "La llave de idempotencia es demasiado corta.", code="sales_refund_key_invalid"
            )
        previous = await self._repository.refund_by_key(company_id, idempotency_key)
        if previous is not None:
            if previous.receipt_id != receipt_id:
                raise ConflictError(
                    "La llave ya se usó para otro reintegro.", code="sales_refund_key_conflict"
                )
            return await self.receipt(company_id, receipt_id), previous, False
        receipt = await self._repository.receipt(company_id, receipt_id, lock=True)
        if receipt is None:
            raise NotFoundError("Recibo no encontrado.", code="sales_receipt_not_found")
        if receipt.status is not ReceiptStatus.ISSUED:
            raise BusinessRuleError(
                "Un recibo anulado no tiene saldo a favor.", code="sales_receipt_annulled"
            )
        clean_reference, clean_reason = validate_refund(
            amount=amount,
            available=receipt.unapplied,
            method=method,
            reference=reference,
            reason=reason,
            refunded_on=refunded_on,
            today=today,
        )
        refund_id = await self._repository.create_refund(
            company_id=company_id,
            receipt=receipt,
            refunded_on=refunded_on,
            amount=amount,
            method=method,
            reference=clean_reference,
            reason=clean_reason,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
        )
        refund = await self._repository.refund(company_id, refund_id)
        assert refund is not None
        return await self.receipt(company_id, receipt_id), refund, True

    async def annul_refund(
        self, company_id: uuid.UUID, refund_id: uuid.UUID, reason: str, actor_id: uuid.UUID
    ) -> tuple[Refund, Receipt]:
        refund = await self._repository.refund(company_id, refund_id, lock=True)
        if refund is None:
            raise NotFoundError("Reintegro no encontrado.", code="sales_refund_not_found")
        if refund.status is not ReceiptStatus.ISSUED:
            raise BusinessRuleError("El reintegro ya está anulado.", code="sales_refund_annulled")
        await self._repository.annul_refund(
            company_id, refund_id, require_annul_reason(reason), actor_id
        )
        return refund, await self.receipt(company_id, refund.receipt_id)

    async def record_certificate(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        certificate: Certificate,
        actor_id: uuid.UUID,
        today: date,
    ) -> AccountDocument:
        document = await self.document(company_id, document_id)
        if document.withholding <= ZERO:
            raise BusinessRuleError(
                "Este documento no tiene retención de IVA.", code="sales_withholding_not_applicable"
            )
        number = certificate.certificate_number.strip()
        if not number or certificate.amount <= ZERO or certificate.amount > document.withholding:
            raise BusinessRuleError(
                "Indica el número del comprobante y un monto que no pase de la retención del "
                "documento.",
                code="sales_withholding_certificate_invalid",
            )
        if certificate.issued_on > today or certificate.issued_on < document.receivable.issued_on:
            raise BusinessRuleError(
                "La fecha del comprobante va desde la del documento hasta hoy.",
                code="sales_withholding_certificate_date_invalid",
            )
        await self._repository.save_certificate(
            company_id,
            document_id,
            Certificate(number, certificate.issued_on, certificate.amount),
            actor_id,
        )
        return await self.document(company_id, document_id)
