"""ORM models for retaceo landed-cost allocations."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class RetaceoModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "retaceos"
    calculation_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="manual", default="manual"
    )
    dai_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    vat_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    manual_entry: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )

    origin_country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    import_invoice_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    import_invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    import_policy_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    import_policy_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    purchase_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("currencies.code", ondelete="RESTRICT"),
        nullable=False,
    )
    total_fob: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    total_freight: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    total_expenses: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    total_dai: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    import_vat: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))

    details: Mapped[list[RetaceoDetailModel]] = relationship(
        "RetaceoDetailModel",
        back_populates="retaceo",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="RetaceoDetailModel.created_at",
    )
    costs: Mapped[list[RetaceoCostModel]] = relationship(
        "RetaceoCostModel",
        back_populates="retaceo",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="RetaceoCostModel.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            "calculation_mode IN ('automatic', 'manual')", name="ck_retaceos_calculation_mode"
        ),
        CheckConstraint(
            "(calculation_mode = 'manual' AND dai_rate IS NULL AND vat_rate IS NULL) OR (calculation_mode = 'automatic' AND dai_rate IS NOT NULL AND vat_rate IS NOT NULL AND dai_rate BETWEEN 0 AND 1000 AND vat_rate BETWEEN 0 AND 1000)",
            name="ck_retaceos_calculation_rates",
        ),
        CheckConstraint(
            "(applied_at IS NULL AND applied_by IS NULL) OR (applied_at IS NOT NULL AND applied_by IS NOT NULL AND status IN ('verified', 'closed'))",
            name="ck_retaceos_application",
        ),
        ForeignKeyConstraint(
            ["purchase_id", "company_id"],
            ["purchases.id", "purchases.company_id"],
            name="fk_retaceos_purchase_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_retaceos_branch_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('draft','calculated','verified','cancelled','closed')",
            name="ck_retaceos_status",
        ),
        CheckConstraint(
            "char_length(currency) = 3 AND currency = upper(currency)",
            name="ck_retaceos_currency",
        ),
        CheckConstraint("total_fob > 0", name="ck_retaceos_fob_positive"),
        CheckConstraint(
            "total_freight >= 0 AND total_expenses >= 0 AND total_dai >= 0 "
            "AND import_vat >= 0 AND total_cost >= 0",
            name="ck_retaceos_amounts_nonnegative",
        ),
        CheckConstraint(
            "total_cost = total_fob + total_freight + total_expenses + total_dai",
            name="ck_retaceos_total_cost",
        ),
        Index("uq_retaceos_id_company", "id", "company_id", unique=True),
        Index("uq_retaceos_company_code", "company_id", "code", unique=True),
        Index("ix_retaceos_company_status_created", "company_id", "status", "created_at"),
        Index("ix_retaceos_purchase_created", "purchase_id", "created_at"),
        Index("ix_retaceos_branch_created", "branch_id", "created_at"),
    )


class RetaceoDetailModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "retaceo_details"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    retaceo_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_detail_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cost_fob: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    freight: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    expenses: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    dai: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    retaceo: Mapped[RetaceoModel] = relationship("RetaceoModel", back_populates="details")

    __table_args__ = (
        ForeignKeyConstraint(
            ["retaceo_id", "company_id"],
            ["retaceos.id", "retaceos.company_id"],
            name="fk_retaceo_details_retaceo_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["purchase_detail_id", "company_id"],
            ["purchase_details.id", "purchase_details.company_id"],
            name="fk_retaceo_details_purchase_detail_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            name="fk_retaceo_details_product_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            name="fk_retaceo_details_unit_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantity > 0", name="ck_retaceo_details_quantity_positive"),
        CheckConstraint(
            "cost_fob >= 0 AND freight >= 0 AND expenses >= 0 AND dai >= 0 "
            "AND total_cost >= 0 AND unit_cost >= 0",
            name="ck_retaceo_details_amounts_nonnegative",
        ),
        CheckConstraint(
            "total_cost = cost_fob + freight + expenses + dai",
            name="ck_retaceo_details_total_cost",
        ),
        Index("uq_retaceo_details_id_company", "id", "company_id", unique=True),
        Index(
            "uq_retaceo_details_retaceo_purchase_detail",
            "retaceo_id",
            "purchase_detail_id",
            unique=True,
        ),
        Index("ix_retaceo_details_retaceo_created", "retaceo_id", "created_at"),
        Index(
            "ix_retaceo_details_company_purchase_detail",
            "company_id",
            "purchase_detail_id",
        ),
    )


class RetaceoCostModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "retaceo_costs"
    incurred_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    retaceo_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_purchase_order_expense_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    expense_type_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    retaceo: Mapped[RetaceoModel] = relationship("RetaceoModel", back_populates="costs")
    allocations: Mapped[list[RetaceoCostAllocationModel]] = relationship(
        "RetaceoCostAllocationModel",
        back_populates="cost",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="RetaceoCostAllocationModel.created_at",
    )
    documents: Mapped[list[RetaceoCostDocumentModel]] = relationship(
        "RetaceoCostDocumentModel",
        back_populates="cost",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="RetaceoCostDocumentModel.created_at",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["retaceo_id", "company_id"],
            ["retaceos.id", "retaceos.company_id"],
            name="fk_retaceo_costs_retaceo_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_purchase_order_expense_id", "company_id"],
            ["purchase_order_expenses.id", "purchase_order_expenses.company_id"],
            name="fk_retaceo_costs_source_expense_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["expense_type_id", "company_id"],
            ["expense_types.id", "expense_types.company_id"],
            name="fk_retaceo_costs_expense_type_company",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "company_id", name="uq_retaceo_costs_id_company"),
        CheckConstraint(
            "classification IN ('freight','expense','dai','import_vat')",
            name="ck_retaceo_costs_classification",
        ),
        CheckConstraint("amount > 0", name="ck_retaceo_costs_amount_positive"),
        CheckConstraint("length(trim(title)) > 0", name="ck_retaceo_costs_title_nonempty"),
        Index("ix_retaceo_costs_retaceo_created", "retaceo_id", "created_at"),
        Index(
            "uq_retaceo_costs_source_expense",
            "retaceo_id",
            "source_purchase_order_expense_id",
            unique=True,
            postgresql_where=sa_text("source_purchase_order_expense_id IS NOT NULL"),
        ),
    )


class RetaceoCostAllocationModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "retaceo_cost_allocations"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    retaceo_cost_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_detail_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    cost: Mapped[RetaceoCostModel] = relationship("RetaceoCostModel", back_populates="allocations")

    __table_args__ = (
        ForeignKeyConstraint(
            ["retaceo_cost_id", "company_id"],
            ["retaceo_costs.id", "retaceo_costs.company_id"],
            name="fk_retaceo_cost_allocations_cost_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["purchase_detail_id", "company_id"],
            ["purchase_details.id", "purchase_details.company_id"],
            name="fk_retaceo_cost_allocations_purchase_detail_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint("amount >= 0", name="ck_retaceo_cost_allocations_amount_nonnegative"),
        UniqueConstraint(
            "retaceo_cost_id",
            "purchase_detail_id",
            name="uq_retaceo_cost_allocations_cost_detail",
        ),
        Index("ix_retaceo_cost_allocations_detail", "company_id", "purchase_detail_id"),
    )


class RetaceoCostDocumentModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "retaceo_cost_documents"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    retaceo_cost_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(160), nullable=False)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cost: Mapped[RetaceoCostModel] = relationship("RetaceoCostModel", back_populates="documents")

    __table_args__ = (
        ForeignKeyConstraint(
            ["retaceo_cost_id", "company_id"],
            ["retaceo_costs.id", "retaceo_costs.company_id"],
            name="fk_retaceo_cost_documents_cost_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_id", "company_id"],
            ["document_assets.id", "document_assets.company_id"],
            name="fk_retaceo_cost_documents_asset_company",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("retaceo_cost_id", "document_id", name="uq_retaceo_cost_documents_asset"),
        Index("ix_retaceo_cost_documents_cost", "company_id", "retaceo_cost_id", "created_at"),
    )
