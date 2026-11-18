"""Documento fiscal del pedido (revisión 0126, bloque V3b)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
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
    contingency_type: Mapped[int | None] = mapped_column(SmallInteger)
    contingency_reason: Mapped[str | None] = mapped_column(Text)
    contingency_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaces_document_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
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
            "status IN ('pending','contingency','issued','simulated','rejected','failed',"
            "'invalidated')",
            name="ck_sales_fiscal_documents_status",
        ),
        CheckConstraint(
            "status NOT IN ('contingency','issued','simulated','invalidated') "
            "OR (generation_code IS NOT NULL "
            "AND control_number IS NOT NULL AND issued_at IS NOT NULL)",
            name="ck_sales_fiscal_documents_identity",
        ),
        CheckConstraint(
            "status <> 'issued' OR seal IS NOT NULL", name="ck_sales_fiscal_documents_seal"
        ),
        CheckConstraint("total >= 0 AND attempts >= 0", name="ck_sales_fiscal_documents_total"),
        CheckConstraint(
            "(contingency_type IS NULL OR contingency_type BETWEEN 1 AND 5) "
            "AND (status <> 'contingency' OR (contingency_at IS NOT NULL "
            "AND contingency_type IS NOT NULL))",
            name="ck_sales_fiscal_documents_contingency",
        ),
        CheckConstraint(
            "replaces_document_id IS DISTINCT FROM id AND superseded_by_id IS DISTINCT FROM id",
            name="ck_sales_fiscal_documents_replacement",
        ),
        ForeignKeyConstraint(
            ["company_id", "replaces_document_id"],
            ["sales_fiscal_documents.company_id", "sales_fiscal_documents.id"],
            ondelete="RESTRICT",
            name="fk_sales_fiscal_documents_replaces",
        ),
        ForeignKeyConstraint(
            ["company_id", "superseded_by_id"],
            ["sales_fiscal_documents.company_id", "sales_fiscal_documents.id"],
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
            name="fk_sales_fiscal_documents_superseded",
        ),
        Index(
            "uq_sales_fiscal_documents_active_sale",
            "company_id",
            "sale_id",
            unique=True,
            postgresql_where=text(
                "status IN ('pending','contingency','issued','simulated') AND superseded_by_id IS NULL"
            ),
        ),
        Index(
            "uq_sales_fiscal_documents_replaces",
            "company_id",
            "replaces_document_id",
            unique=True,
            postgresql_where=text(
                "replaces_document_id IS NOT NULL AND status NOT IN ('failed','rejected')"
            ),
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
    invalidation_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
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
            postgresql_where=text("origin = 'auto' AND invalidation_id IS NULL"),
        ),
        Index(
            "uq_sales_fiscal_document_emails_invalidation",
            "company_id",
            "invalidation_id",
            unique=True,
            postgresql_where=text("origin = 'auto' AND invalidation_id IS NOT NULL"),
        ),
        ForeignKeyConstraint(
            ["company_id", "invalidation_id"],
            ["sales_fiscal_invalidations.company_id", "sales_fiscal_invalidations.id"],
            ondelete="RESTRICT",
            name="fk_sales_fiscal_document_emails_invalidation",
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


class SalesFiscalInvalidationModel(Base):
    """Solicitud de invalidación de un documento fiscal (revisión 0131, bloque V4b)."""

    __tablename__ = "sales_fiscal_invalidations"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    kind: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200))
    requester_name: Mapped[str] = mapped_column(String(100), nullable=False)
    requester_document_type: Mapped[str] = mapped_column(String(2), nullable=False)
    requester_document_number: Mapped[str] = mapped_column(String(25), nullable=False)
    responsible_name: Mapped[str | None] = mapped_column(String(100))
    responsible_document_type: Mapped[str | None] = mapped_column(String(2))
    responsible_document_number: Mapped[str | None] = mapped_column(String(25))
    replacement_document_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    cancel_order: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    event_generation_code: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    event_seal: Mapped[str | None] = mapped_column(String(100))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    requested_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_fiscal_invalidations_company_id"),
        UniqueConstraint(
            "company_id", "idempotency_key", name="uq_sales_fiscal_invalidations_idempotency"
        ),
        ForeignKeyConstraint(
            ["company_id", "document_id"],
            ["sales_fiscal_documents.company_id", "sales_fiscal_documents.id"],
            ondelete="RESTRICT",
            name="fk_sales_fiscal_invalidations_document",
        ),
        ForeignKeyConstraint(
            ["company_id", "replacement_document_id"],
            ["sales_fiscal_documents.company_id", "sales_fiscal_documents.id"],
            ondelete="RESTRICT",
            name="fk_sales_fiscal_invalidations_replacement",
        ),
        ForeignKeyConstraint(
            ["requested_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_fiscal_invalidations_requester",
        ),
        CheckConstraint(
            "(kind = 1 AND replacement_document_id IS NOT NULL AND NOT cancel_order) "
            "OR (kind = 2 AND replacement_document_id IS NULL)",
            name="ck_sales_fiscal_invalidations_kind",
        ),
        CheckConstraint(
            "status IN ('pending','accepted','rejected','failed')",
            name="ck_sales_fiscal_invalidations_status",
        ),
        CheckConstraint(
            "requester_document_type IN ('36','13','37','03','02') "
            "AND char_length(btrim(requester_name)) BETWEEN 3 AND 100 "
            "AND char_length(btrim(requester_document_number)) BETWEEN 1 AND 25",
            name="ck_sales_fiscal_invalidations_people",
        ),
        CheckConstraint(
            "(status = 'pending') = (resolved_at IS NULL) "
            "AND (status <> 'accepted' OR event_generation_code IS NOT NULL) "
            "AND (status NOT IN ('rejected','failed') OR error_message IS NOT NULL) "
            "AND attempts >= 0",
            name="ck_sales_fiscal_invalidations_result",
        ),
        Index(
            "uq_sales_fiscal_invalidations_pending",
            "company_id",
            "document_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_sales_fiscal_invalidations_status", "status", "updated_at"),
    )
