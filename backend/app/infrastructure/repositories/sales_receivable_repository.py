"""Cuentas por cobrar sobre los documentos fiscales, y recibos de cobro."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.sales_receivables import (
    ApplicationRequest,
    PaymentLine,
    PaymentMethod,
    ReceiptStatus,
    ReceivableDocument,
    due_date,
)
from app.domain.ports.sales_receivable_repository import (
    AccountDocument,
    Application,
    Certificate,
    CustomerRef,
    Issuer,
    Receipt,
)

# El saldo de cada documento sale del DTE (totalPagar ya descuenta la retención), de sus notas de
# crédito y retornos vigentes y de lo aplicado por recibos vigentes.
_DOCUMENTS = """
    SELECT d.id, d.document_type, d.control_number, d.status, d.branch_id, d.sale_id,
           (d.dte_json->'identificacion'->>'fecEmi')::date AS issued_on,
           COALESCE((d.dte_json->'resumen'->>'totalPagar')::numeric, d.total) AS payable,
           COALESCE((d.dte_json->'resumen'->>'ivaRete1')::numeric,
                    (d.dte_json->'resumen'->>'ivaRete')::numeric, 0) AS withholding,
           s.customer_id, s.code AS sale_code, s.credit_days,
           COALESCE((
               SELECT sum(COALESCE((n.dte_json->'resumen'->>'totalPagar')::numeric, n.total))
               FROM sales_fiscal_documents n
               WHERE n.company_id = d.company_id AND n.related_document_id = d.id
                 AND n.document_type = '05'
                 AND n.status IN ('issued', 'simulated', 'contingency')
           ), 0) + COALESCE((
               SELECT sum(r.total) FROM sales_fiscal_returns r
               WHERE r.company_id = d.company_id AND r.document_id = d.id
                 AND r.status IN ('issued', 'simulated')
           ), 0) AS credited,
           COALESCE((
               SELECT sum(a.amount) FROM sales_receipt_applications a
               JOIN sales_receipts rc ON rc.company_id = a.company_id AND rc.id = a.receipt_id
               WHERE a.company_id = d.company_id AND a.document_id = d.id
                 AND rc.status = 'issued'
           ), 0) AS applied,
           c.certificate_number, c.issued_on AS certificate_on, c.amount AS certificate_amount
    FROM sales_fiscal_documents d
    JOIN sales s ON s.company_id = d.company_id AND s.id = d.sale_id
    LEFT JOIN sales_withholding_certificates c
      ON c.company_id = d.company_id AND c.document_id = d.id
    WHERE d.company_id = :company AND d.dte_json IS NOT NULL
      AND d.document_type IN ('01', '03', '06')
      AND d.status IN ('issued', 'simulated', 'contingency', 'invalidated')
      AND (CAST(:customer AS uuid) IS NULL OR s.customer_id = :customer)
      AND (CAST(:document AS uuid) IS NULL OR d.id = :document)
    ORDER BY issued_on, d.control_number
"""

_RECEIPTS = """
    SELECT id, company_id, branch_id, customer_id, number, received_on, total, notes, status,
           annul_reason, annulled_at, created_at
    FROM sales_receipts
    WHERE company_id = :company
      AND (CAST(:customer AS uuid) IS NULL OR customer_id = :customer)
      AND (CAST(:receipt AS uuid) IS NULL OR id = :receipt)
      AND (CAST(:key AS text) IS NULL OR idempotency_key = :key)
    ORDER BY received_on DESC, number DESC
"""


def _document(row: Any) -> AccountDocument:
    certificate = (
        Certificate(row.certificate_number, row.certificate_on, row.certificate_amount)
        if row.certificate_number
        else None
    )
    return AccountDocument(
        receivable=ReceivableDocument(
            id=row.id,
            document_type=row.document_type,
            control_number=row.control_number or "",
            issued_on=row.issued_on,
            due_on=due_date(row.issued_on, row.credit_days or 0),
            payable=Decimal(row.payable),
            credited=Decimal(row.credited),
            applied=Decimal(row.applied),
            invalidated=row.status == "invalidated",
        ),
        customer_id=row.customer_id,
        sale_id=row.sale_id,
        sale_code=row.sale_code,
        branch_id=row.branch_id,
        status=row.status,
        withholding=Decimal(row.withholding),
        certificate=certificate,
    )


class SqlAlchemySalesReceivableRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def issuer(self, company_id: uuid.UUID) -> Issuer:
        row = (
            await self._session.execute(
                text("SELECT name, nit, nrc FROM companies WHERE id = :company"),
                {"company": company_id},
            )
        ).one()
        return Issuer(row.name, row.nit, row.nrc)

    async def customer(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, *, lock: bool = False
    ) -> CustomerRef | None:
        sql = (
            "SELECT id, code, name, credit_days, credit_limit FROM sales_customers "
            "WHERE company_id = :company AND id = :customer"
        )
        row = (
            await self._session.execute(
                text(sql + (" FOR UPDATE" if lock else "")),
                {"company": company_id, "customer": customer_id},
            )
        ).one_or_none()
        return CustomerRef(*row) if row else None

    async def customers(self, company_id: uuid.UUID, ids: set[uuid.UUID]) -> list[CustomerRef]:
        if not ids:
            return []
        rows = await self._session.execute(
            text(
                "SELECT id, code, name, credit_days, credit_limit FROM sales_customers "
                "WHERE company_id = :company AND id = ANY(:ids) ORDER BY name"
            ),
            {"company": company_id, "ids": list(ids)},
        )
        return [CustomerRef(*row) for row in rows]

    async def documents(
        self, company_id: uuid.UUID, customer_id: uuid.UUID | None = None
    ) -> list[AccountDocument]:
        rows = await self._session.execute(
            text(_DOCUMENTS), {"company": company_id, "customer": customer_id, "document": None}
        )
        return [_document(row) for row in rows]

    async def document(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> AccountDocument | None:
        row = (
            await self._session.execute(
                text(_DOCUMENTS),
                {"company": company_id, "customer": None, "document": document_id},
            )
        ).one_or_none()
        return _document(row) if row else None

    async def _receipts(
        self,
        company_id: uuid.UUID,
        *,
        customer: uuid.UUID | None = None,
        receipt: uuid.UUID | None = None,
        key: str | None = None,
    ) -> list[Receipt]:
        rows = (
            await self._session.execute(
                text(_RECEIPTS),
                {"company": company_id, "customer": customer, "receipt": receipt, "key": key},
            )
        ).all()
        if not rows:
            return []
        ids = [row.id for row in rows]
        payments: dict[uuid.UUID, list[PaymentLine]] = defaultdict(list)
        for row in await self._session.execute(
            text(
                "SELECT receipt_id, method, amount, reference FROM sales_receipt_payments "
                "WHERE company_id = :company AND receipt_id = ANY(:ids) "
                "ORDER BY receipt_id, line_number"
            ),
            {"company": company_id, "ids": ids},
        ):
            payments[row.receipt_id].append(
                PaymentLine(PaymentMethod(row.method), Decimal(row.amount), row.reference)
            )
        applications: dict[uuid.UUID, list[Application]] = defaultdict(list)
        for row in await self._session.execute(
            text(
                "SELECT a.receipt_id, a.document_id, d.control_number, a.amount, a.applied_on, "
                "d.status = 'invalidated' AS invalidated "
                "FROM sales_receipt_applications a "
                "JOIN sales_fiscal_documents d "
                "  ON d.company_id = a.company_id AND d.id = a.document_id "
                "WHERE a.company_id = :company AND a.receipt_id = ANY(:ids) "
                "ORDER BY a.created_at"
            ),
            {"company": company_id, "ids": ids},
        ):
            applications[row.receipt_id].append(
                Application(
                    row.document_id,
                    row.control_number or "",
                    Decimal(row.amount),
                    row.applied_on,
                    row.invalidated,
                )
            )
        return [
            Receipt(
                id=row.id,
                company_id=row.company_id,
                branch_id=row.branch_id,
                customer_id=row.customer_id,
                number=row.number,
                received_on=row.received_on,
                total=Decimal(row.total),
                notes=row.notes,
                status=ReceiptStatus(row.status),
                payments=payments[row.id],
                applications=applications[row.id],
                annul_reason=row.annul_reason,
                annulled_at=row.annulled_at,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def receipts(
        self, company_id: uuid.UUID, customer_id: uuid.UUID | None = None
    ) -> list[Receipt]:
        return await self._receipts(company_id, customer=customer_id)

    async def receipt(
        self, company_id: uuid.UUID, receipt_id: uuid.UUID, *, lock: bool = False
    ) -> Receipt | None:
        if lock:
            await self._session.execute(
                text(
                    "SELECT id FROM sales_receipts WHERE company_id = :company AND id = :receipt "
                    "FOR UPDATE"
                ),
                {"company": company_id, "receipt": receipt_id},
            )
        found = await self._receipts(company_id, receipt=receipt_id)
        return found[0] if found else None

    async def receipt_by_key(self, company_id: uuid.UUID, key: str) -> Receipt | None:
        found = await self._receipts(company_id, key=key)
        return found[0] if found else None

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
    ) -> uuid.UUID:
        # Numeración correlativa por empresa, sin huecos por concurrencia.
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"sales_receipts:{company_id}"},
        )
        number = await self._session.scalar(
            text("SELECT COALESCE(max(number), 0) + 1 FROM sales_receipts WHERE company_id = :c"),
            {"c": company_id},
        )
        receipt_id = uuid.uuid4()
        await self._session.execute(
            text(
                "INSERT INTO sales_receipts (id, company_id, branch_id, customer_id, number, "
                "received_on, total, notes, idempotency_key, created_by_id) VALUES (:id, :company, "
                ":branch, :customer, :number, :received_on, :total, :notes, :key, :actor)"
            ),
            {
                "id": receipt_id,
                "company": company_id,
                "branch": branch_id,
                "customer": customer_id,
                "number": number,
                "received_on": received_on,
                "total": total,
                "notes": notes,
                "key": idempotency_key,
                "actor": actor_id,
            },
        )
        for index, payment in enumerate(payments, start=1):
            await self._session.execute(
                text(
                    "INSERT INTO sales_receipt_payments (company_id, receipt_id, line_number, "
                    "method, amount, reference) VALUES (:company, :receipt, :line, :method, "
                    ":amount, :reference)"
                ),
                {
                    "company": company_id,
                    "receipt": receipt_id,
                    "line": index,
                    "method": payment.method.value,
                    "amount": payment.amount,
                    "reference": payment.reference,
                },
            )
        await self.add_applications(company_id, receipt_id, applications, received_on, actor_id)
        return receipt_id

    async def add_applications(
        self,
        company_id: uuid.UUID,
        receipt_id: uuid.UUID,
        applications: list[ApplicationRequest],
        applied_on: date,
        actor_id: uuid.UUID,
    ) -> None:
        for item in applications:
            await self._session.execute(
                text(
                    "INSERT INTO sales_receipt_applications (company_id, receipt_id, document_id, "
                    "amount, applied_on, created_by_id) VALUES (:company, :receipt, :document, "
                    ":amount, :applied_on, :actor)"
                ),
                {
                    "company": company_id,
                    "receipt": receipt_id,
                    "document": item.document_id,
                    "amount": item.amount,
                    "applied_on": applied_on,
                    "actor": actor_id,
                },
            )

    async def annul_receipt(
        self, company_id: uuid.UUID, receipt_id: uuid.UUID, reason: str, actor_id: uuid.UUID
    ) -> None:
        await self._session.execute(
            text(
                "UPDATE sales_receipts SET status = 'annulled', annul_reason = :reason, "
                "annulled_by_id = :actor, annulled_at = :now "
                "WHERE company_id = :company AND id = :receipt AND status = 'issued'"
            ),
            {
                "company": company_id,
                "receipt": receipt_id,
                "reason": reason,
                "actor": actor_id,
                "now": datetime.now(UTC),
            },
        )

    async def save_certificate(
        self,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        certificate: Certificate,
        actor_id: uuid.UUID,
    ) -> None:
        await self._session.execute(
            text(
                "INSERT INTO sales_withholding_certificates (company_id, document_id, "
                "certificate_number, issued_on, amount, created_by_id) VALUES (:company, "
                ":document, :number, :issued_on, :amount, :actor) "
                "ON CONFLICT (company_id, document_id) DO UPDATE SET "
                "certificate_number = EXCLUDED.certificate_number, "
                "issued_on = EXCLUDED.issued_on, amount = EXCLUDED.amount, "
                "created_by_id = EXCLUDED.created_by_id, created_at = now()"
            ),
            {
                "company": company_id,
                "document": document_id,
                "number": certificate.certificate_number,
                "issued_on": certificate.issued_on,
                "amount": certificate.amount,
                "actor": actor_id,
            },
        )
