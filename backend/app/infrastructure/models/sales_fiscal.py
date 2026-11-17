"""Documento fiscal del pedido (revisión 0126, bloque V3b)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class SalesFiscalDocumentModel(Base):
    """Copia del ERP de cada factura o crédito fiscal emitido por el servicio DTE."""

    __tablename__ = "sales_fiscal_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sale_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    establishment_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    point_of_sale_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_type: Mapped[str] = mapped_column(String(2), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    generation_code: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    control_number: Mapped[str | None] = mapped_column(String(31))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    issuer_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    dte_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    seal: Mapped[str | None] = mapped_column(String(100))
    service_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    json_object_key: Mapped[str | None] = mapped_column(Text)
    pdf_object_key: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_fiscal_documents_company_id"),
        UniqueConstraint(
            "company_id", "idempotency_key", name="uq_sales_fiscal_documents_idempotency"
        ),
        UniqueConstraint(
            "company_id", "generation_code", name="uq_sales_fiscal_documents_generation"
        ),
        ForeignKeyConstraint(
            ["company_id", "sale_id"],
            ["sales.company_id", "sales.id"],
            ondelete="RESTRICT",
            name="fk_sales_fiscal_documents_sale",
        ),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_fiscal_documents_branch",
        ),
        ForeignKeyConstraint(
            ["company_id", "establishment_id"],
            ["fiscal_establishments.company_id", "fiscal_establishments.id"],
            ondelete="RESTRICT",
            name="fk_sales_fiscal_documents_establishment",
        ),
        ForeignKeyConstraint(
            ["company_id", "point_of_sale_id"],
            ["fiscal_points_of_sale.company_id", "fiscal_points_of_sale.id"],
            ondelete="RESTRICT",
            name="fk_sales_fiscal_documents_point_of_sale",
        ),
        ForeignKeyConstraint(
            ["created_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_fiscal_documents_creator",
        ),
        CheckConstraint("document_type IN ('01','03')", name="ck_sales_fiscal_documents_document"),
        CheckConstraint(
            "mode IN ('simulated','hacienda-test','production')",
            name="ck_sales_fiscal_documents_mode",
        ),
        CheckConstraint(
            "status IN ('pending','issued','simulated','rejected','failed')",
            name="ck_sales_fiscal_documents_status",
        ),
        CheckConstraint(
            "status NOT IN ('issued','simulated') OR (generation_code IS NOT NULL "
            "AND control_number IS NOT NULL AND issued_at IS NOT NULL)",
            name="ck_sales_fiscal_documents_identity",
        ),
        CheckConstraint(
            "status <> 'issued' OR seal IS NOT NULL", name="ck_sales_fiscal_documents_seal"
        ),
        CheckConstraint("total >= 0 AND attempts >= 0", name="ck_sales_fiscal_documents_total"),
        Index(
            "uq_sales_fiscal_documents_active_sale",
            "company_id",
            "sale_id",
            unique=True,
            postgresql_where=text("status <> 'failed'"),
        ),
        Index(
            "ix_sales_fiscal_documents_company_status",
            "company_id",
            "branch_id",
            "status",
            "created_at",
        ),
    )


class SalesFiscalDocumentEmailModel(Base):
    """Envío por correo de un documento fiscal (revisión 0127, bloque V3c)."""

    __tablename__ = "sales_fiscal_document_emails"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    recipients: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    origin: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    message_id: Mapped[str | None] = mapped_column(String(255))
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_fiscal_document_emails_company_id"),
        ForeignKeyConstraint(
            ["company_id", "document_id"],
            ["sales_fiscal_documents.company_id", "sales_fiscal_documents.id"],
            ondelete="RESTRICT",
            name="fk_sales_fiscal_document_emails_document",
        ),
        ForeignKeyConstraint(
            ["requested_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_fiscal_document_emails_requester",
        ),
        CheckConstraint(
            "origin IN ('auto','manual') AND (origin = 'manual') = (requested_by_id IS NOT NULL)",
            name="ck_sales_fiscal_document_emails_origin",
        ),
        CheckConstraint(
            "status IN ('pending','sent','failed')", name="ck_sales_fiscal_document_emails_status"
        ),
        CheckConstraint(
            "cardinality(recipients) BETWEEN 1 AND 5",
            name="ck_sales_fiscal_document_emails_recipients",
        ),
        CheckConstraint(
            "(status = 'sent') = (sent_at IS NOT NULL AND message_id IS NOT NULL)",
            name="ck_sales_fiscal_document_emails_sent",
        ),
        CheckConstraint("attempts >= 0", name="ck_sales_fiscal_document_emails_attempts"),
        Index(
            "uq_sales_fiscal_document_emails_auto",
            "company_id",
            "document_id",
            unique=True,
            postgresql_where=text("origin = 'auto'"),
        ),
        Index(
            "ix_sales_fiscal_document_emails_document", "company_id", "document_id", "created_at"
        ),
        Index(
            "ix_sales_fiscal_document_emails_pending",
            "updated_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )
