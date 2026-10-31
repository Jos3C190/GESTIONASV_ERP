"""Persistence models for demand consolidation, source links and edit history."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin
from app.infrastructure.models.organization import Warehouse
from app.infrastructure.models.purchase_request import PurchaseRequestModel


class PurchaseConsolidationModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_consolidations"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    central_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines: Mapped[list[PurchaseConsolidationLineModel]] = relationship(
        back_populates="consolidation", cascade="all, delete-orphan", lazy="selectin"
    )
    events: Mapped[list[PurchaseConsolidationEventModel]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PurchaseConsolidationEventModel.created_at",
    )
    central_warehouse: Mapped[Warehouse | None] = relationship(lazy="selectin")

    __table_args__ = (
        UniqueConstraint("id", "company_id", name="uq_purchase_consolidations_id_company"),
        UniqueConstraint("company_id", "code", name="uq_purchase_consolidations_company_code"),
        CheckConstraint("period_end >= period_start", name="ck_purchase_consolidations_period"),
        CheckConstraint(
            "status IN ('draft','frozen','closed','cancelled')",
            name="ck_purchase_consolidations_status",
        ),
        Index(
            "ix_purchase_consolidations_company_status_period",
            "company_id",
            "status",
            "period_start",
        ),
    )


class PurchaseConsolidationLineModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_consolidation_lines"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    consolidation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    central_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, server_default="0"
    )
    central_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    consolidation: Mapped[PurchaseConsolidationModel] = relationship(back_populates="lines")
    sources: Mapped[list[PurchaseConsolidationSourceModel]] = relationship(
        back_populates="line", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("id", "company_id", name="uq_purchase_consolidation_lines_id_company"),
        UniqueConstraint(
            "consolidation_id",
            "product_id",
            "unit_id",
            name="uq_purchase_consolidation_product_unit",
        ),
        ForeignKeyConstraint(
            ["consolidation_id", "company_id"],
            ["purchase_consolidations.id", "purchase_consolidations.company_id"],
            ondelete="CASCADE",
            name="fk_purchase_consolidation_lines_header_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            ondelete="RESTRICT",
            name="fk_purchase_consolidation_lines_product_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_purchase_consolidation_lines_unit_company",
        ),
        CheckConstraint(
            "central_quantity >= 0", name="ck_purchase_consolidation_central_nonnegative"
        ),
        CheckConstraint(
            "central_quantity = 0 OR length(trim(coalesce(central_reason, ''))) > 0",
            name="ck_purchase_consolidation_central_reason",
        ),
        Index("ix_purchase_consolidation_lines_header", "company_id", "consolidation_id"),
    )


class PurchaseConsolidationSourceModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_consolidation_sources"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    consolidation_line_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_request_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_request_detail_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    included_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    demand_level: Mapped[str | None] = mapped_column(String(16), nullable=True)

    line: Mapped[PurchaseConsolidationLineModel] = relationship(back_populates="sources")
    purchase_request: Mapped[PurchaseRequestModel] = relationship(lazy="selectin", viewonly=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["consolidation_line_id", "company_id"],
            ["purchase_consolidation_lines.id", "purchase_consolidation_lines.company_id"],
            ondelete="CASCADE",
            name="fk_purchase_consolidation_sources_line_company",
        ),
        ForeignKeyConstraint(
            ["purchase_request_id", "company_id"],
            ["purchase_requests.id", "purchase_requests.company_id"],
            ondelete="RESTRICT",
            name="fk_purchase_consolidation_sources_request_company",
        ),
        ForeignKeyConstraint(
            ["purchase_request_detail_id", "company_id"],
            ["purchase_request_details.id", "purchase_request_details.company_id"],
            ondelete="RESTRICT",
            name="fk_purchase_consolidation_sources_request_detail_company",
        ),
        UniqueConstraint("id", "company_id", name="uq_purchase_consolidation_sources_id_company"),
        CheckConstraint(
            "requested_quantity > 0", name="ck_purchase_consolidation_source_requested_positive"
        ),
        CheckConstraint(
            "included_quantity >= 0 AND included_quantity <= requested_quantity",
            name="ck_purchase_consolidation_source_included_range",
        ),
        CheckConstraint(
            "included_quantity = requested_quantity OR length(trim(coalesce(reason, ''))) > 0",
            name="ck_purchase_consolidation_source_reason",
        ),
        CheckConstraint(
            "demand_level IS NULL OR demand_level IN ('low','medium','high')",
            name="ck_purchase_consolidation_source_demand_level",
        ),
        Index("ix_purchase_consolidation_sources_request", "company_id", "purchase_request_id"),
    )


class PurchaseConsolidationEventModel(UUIDPKMixin, Base):
    __tablename__ = "purchase_consolidation_events"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    consolidation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    changes: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["consolidation_id", "company_id"],
            ["purchase_consolidations.id", "purchase_consolidations.company_id"],
            ondelete="CASCADE",
            name="fk_purchase_consolidation_events_header_company",
        ),
        Index(
            "ix_purchase_consolidation_events_history",
            "company_id",
            "consolidation_id",
            "created_at",
        ),
    )


class PurchaseConsolidationAwardModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_consolidation_awards"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    consolidation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    consolidation_line_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_quotation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_quotation_detail_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    supplier_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["consolidation_id", "company_id"],
            ["purchase_consolidations.id", "purchase_consolidations.company_id"],
            name="fk_purchase_consolidation_awards_header_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["consolidation_line_id", "company_id"],
            ["purchase_consolidation_lines.id", "purchase_consolidation_lines.company_id"],
            name="fk_purchase_consolidation_awards_line_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["purchase_quotation_id", "company_id"],
            ["purchase_quotations.id", "purchase_quotations.company_id"],
            name="fk_purchase_consolidation_awards_quotation_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["purchase_quotation_detail_id", "company_id"],
            ["purchase_quotation_details.id", "purchase_quotation_details.company_id"],
            name="fk_purchase_consolidation_awards_quotation_detail_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "supplier_id"],
            ["suppliers.company_id", "suppliers.id_supplier"],
            name="fk_purchase_consolidation_awards_supplier_company",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "company_id", name="uq_purchase_consolidation_awards_id_company"),
        CheckConstraint("quantity > 0", name="ck_purchase_consolidation_awards_quantity_positive"),
        CheckConstraint(
            "length(trim(reason)) > 0", name="ck_purchase_consolidation_awards_reason_required"
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_id IS NULL AND revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by_id IS NOT NULL "
            "AND length(trim(coalesce(revocation_reason, ''))) > 0)",
            name="ck_purchase_consolidation_awards_revocation_complete",
        ),
        Index(
            "ix_purchase_consolidation_awards_line_active",
            "company_id",
            "consolidation_id",
            "consolidation_line_id",
            "revoked_at",
        ),
        Index(
            "ix_purchase_consolidation_awards_quote_detail",
            "company_id",
            "purchase_quotation_detail_id",
            "revoked_at",
        ),
    )
