"""Recibos de cobro y comprobantes de retención recibidos (revisión 0140, bloque V5a)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class SalesReceiptModel(Base):
    __tablename__ = "sales_receipts"

    id: Mapped[uuid.UUID] = _id()
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    received_on: Mapped[date] = mapped_column(Date, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="issued")
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    annul_reason: Mapped[str | None] = mapped_column(String(300))
    annulled_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    annulled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_receipts_company_id"),
        UniqueConstraint("company_id", "number", name="uq_sales_receipts_number"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_sales_receipts_idempotency"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_sales_receipts_branch",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "customer_id"],
            ["sales_customers.company_id", "sales_customers.id"],
            name="fk_sales_receipts_customer",
            ondelete="RESTRICT",
        ),
    )


class SalesReceiptPaymentModel(Base):
    __tablename__ = "sales_receipt_payments"

    id: Mapped[uuid.UUID] = _id()
    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    receipt_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    line_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        UniqueConstraint(
            "company_id", "receipt_id", "line_number", name="uq_sales_receipt_payments_line"
        ),
        ForeignKeyConstraint(
            ["company_id", "receipt_id"],
            ["sales_receipts.company_id", "sales_receipts.id"],
            name="fk_sales_receipt_payments_receipt",
            ondelete="RESTRICT",
        ),
    )


class SalesReceiptApplicationModel(Base):
    __tablename__ = "sales_receipt_applications"

    id: Mapped[uuid.UUID] = _id()
    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    receipt_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    applied_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "receipt_id"],
            ["sales_receipts.company_id", "sales_receipts.id"],
            name="fk_sales_receipt_applications_receipt",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "document_id"],
            ["sales_fiscal_documents.company_id", "sales_fiscal_documents.id"],
            name="fk_sales_receipt_applications_document",
            ondelete="RESTRICT",
        ),
    )


class SalesWithholdingCertificateModel(Base):
    __tablename__ = "sales_withholding_certificates"

    id: Mapped[uuid.UUID] = _id()
    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    certificate_number: Mapped[str] = mapped_column(String(100), nullable=False)
    issued_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "document_id", name="uq_sales_withholding_certificates_document"
        ),
        ForeignKeyConstraint(
            ["company_id", "document_id"],
            ["sales_fiscal_documents.company_id", "sales_fiscal_documents.id"],
            name="fk_sales_withholding_certificates_document",
            ondelete="RESTRICT",
        ),
    )


class SalesCollectionNoteModel(Base):
    """Nota de seguimiento de cobro de un cliente (revisión 0141)."""

    __tablename__ = "sales_collection_notes"

    id: Mapped[uuid.UUID] = _id()
    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    note: Mapped[str] = mapped_column(String(1000), nullable=False)
    next_action_on: Mapped[date | None] = mapped_column(Date)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "customer_id"],
            ["sales_customers.company_id", "sales_customers.id"],
            name="fk_sales_collection_notes_customer",
            ondelete="RESTRICT",
        ),
    )


class SalesReturnFiscalAdjustmentModel(Base):
    """Ajuste fiscal de una aceptación de devolución: nota, retorno o motivo (revisión 0142)."""

    __tablename__ = "sales_return_fiscal_adjustments"

    id: Mapped[uuid.UUID] = _id()
    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    return_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    fiscal_note_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    fiscal_return_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    message: Mapped[str | None] = mapped_column(String(500))
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default="[]")
    resolution_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "return_id"],
            ["sales_returns.company_id", "sales_returns.id"],
            name="fk_sales_return_fiscal_adjustments_return",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "document_id"],
            ["sales_fiscal_documents.company_id", "sales_fiscal_documents.id"],
            name="fk_sales_return_fiscal_adjustments_document",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "fiscal_note_id"],
            ["sales_fiscal_documents.company_id", "sales_fiscal_documents.id"],
            name="fk_sales_return_fiscal_adjustments_note",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "fiscal_return_id"],
            ["sales_fiscal_returns.company_id", "sales_fiscal_returns.id"],
            name="fk_sales_return_fiscal_adjustments_event",
            ondelete="RESTRICT",
        ),
    )


class SalesRefundModel(Base):
    """Reintegro de dinero desde el saldo a favor de un recibo (revisión 0142)."""

    __tablename__ = "sales_refunds"

    id: Mapped[uuid.UUID] = _id()
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    receipt_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    refunded_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="issued")
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    annul_reason: Mapped[str | None] = mapped_column(String(300))
    annulled_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    annulled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("company_id", "number", name="uq_sales_refunds_number"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_sales_refunds_idempotency"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_sales_refunds_branch",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "customer_id"],
            ["sales_customers.company_id", "sales_customers.id"],
            name="fk_sales_refunds_customer",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "receipt_id"],
            ["sales_receipts.company_id", "sales_receipts.id"],
            name="fk_sales_refunds_receipt",
            ondelete="RESTRICT",
        ),
    )
