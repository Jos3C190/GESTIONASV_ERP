"""ORM models for purchase quotations, RFQ coverage and additional expenses."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class ExpenseTypeModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "expense_types"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("id", "company_id", name="uq_expense_types_id_company_id"),
        Index(
            "uq_expense_types_company_name",
            "company_id",
            func.lower(name),
            unique=True,
        ),
        Index("ix_expense_types_company_active", "company_id", "is_active"),
    )


class PurchaseQuotationModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_quotations"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    supplier_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quotation_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    discount: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    tax: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    request_links: Mapped[list[PurchaseQuotationRequestModel]] = relationship(
        "PurchaseQuotationRequestModel",
        back_populates="purchase_quotation",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PurchaseQuotationRequestModel.created_at",
    )
    details: Mapped[list[PurchaseQuotationDetailModel]] = relationship(
        "PurchaseQuotationDetailModel",
        back_populates="purchase_quotation",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PurchaseQuotationDetailModel.created_at",
    )
    expenses: Mapped[list[PurchaseQuotationExpenseModel]] = relationship(
        "PurchaseQuotationExpenseModel",
        back_populates="purchase_quotation",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PurchaseQuotationExpenseModel.created_at",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "supplier_id"],
            ["suppliers.company_id", "suppliers.id_supplier"],
            name="fk_purchase_quotations_supplier_company",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "company_id", name="uq_purchase_quotations_id_company_id"),
        UniqueConstraint("company_id", "code", name="uq_purchase_quotations_company_code"),
        CheckConstraint(
            "status IN "
            "('draft','requested','received','under_evaluation','selected','rejected',"
            "'expired','cancelled')",
            name="ck_purchase_quotations_status",
        ),
        CheckConstraint(
            "char_length(currency) = 3 AND currency = upper(currency)",
            name="ck_purchase_quotations_currency",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until >= quotation_date",
            name="ck_purchase_quotations_validity",
        ),
        CheckConstraint(
            "delivery_days IS NULL OR delivery_days >= 0",
            name="ck_purchase_quotations_delivery_days",
        ),
        CheckConstraint(
            "subtotal >= 0 AND discount >= 0 AND tax >= 0 AND total >= 0",
            name="ck_purchase_quotations_amounts_nonnegative",
        ),
        CheckConstraint(
            "discount <= subtotal",
            name="ck_purchase_quotations_discount_within_subtotal",
        ),
        Index(
            "ix_purchase_quotations_company_status_date",
            "company_id",
            "status",
            "quotation_date",
        ),
        Index(
            "ix_purchase_quotations_company_supplier_date",
            "company_id",
            "supplier_id",
            "quotation_date",
        ),
    )


class PurchaseQuotationRequestModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_quotation_requests"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_quotation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_request_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    purchase_quotation: Mapped[PurchaseQuotationModel] = relationship(
        "PurchaseQuotationModel",
        back_populates="request_links",
    )
    details: Mapped[list[PurchaseQuotationRequestDetailModel]] = relationship(
        "PurchaseQuotationRequestDetailModel",
        back_populates="purchase_quotation_request",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PurchaseQuotationRequestDetailModel.created_at",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_quotation_id", "company_id"],
            ["purchase_quotations.id", "purchase_quotations.company_id"],
            name="fk_purchase_quotation_requests_quotation_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["purchase_request_id", "company_id"],
            ["purchase_requests.id", "purchase_requests.company_id"],
            name="fk_purchase_quotation_requests_request_company",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "company_id",
            name="uq_purchase_quotation_requests_id_company_id",
        ),
        UniqueConstraint(
            "purchase_quotation_id",
            "purchase_request_id",
            name="uq_purchase_quotation_requests_pair",
        ),
        Index(
            "ix_purchase_quotation_requests_request",
            "purchase_request_id",
            "created_at",
        ),
    )


class PurchaseQuotationRequestDetailModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_quotation_request_details"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_quotation_request_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    purchase_quotation_detail_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    purchase_request_detail_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    purchase_quotation_request: Mapped[PurchaseQuotationRequestModel] = relationship(
        "PurchaseQuotationRequestModel",
        back_populates="details",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_quotation_request_id", "company_id"],
            ["purchase_quotation_requests.id", "purchase_quotation_requests.company_id"],
            name="fk_purchase_quotation_request_details_link_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["purchase_quotation_detail_id", "company_id"],
            ["purchase_quotation_details.id", "purchase_quotation_details.company_id"],
            name="fk_purchase_quotation_request_details_quotation_detail_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["purchase_request_detail_id", "company_id"],
            ["purchase_request_details.id", "purchase_request_details.company_id"],
            name="fk_purchase_quotation_request_details_request_detail_company",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "purchase_quotation_request_id",
            "purchase_request_detail_id",
            name="uq_purchase_quotation_request_details_pair",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_purchase_quotation_request_details_quantity_positive",
        ),
        Index(
            "ix_purchase_quotation_request_details_request_detail",
            "purchase_request_detail_id",
        ),
        Index(
            "ix_purchase_quotation_request_details_quotation_detail",
            "purchase_quotation_detail_id",
        ),
    )


class PurchaseQuotationDetailModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_quotation_details"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_quotation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    discount: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(9, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    purchase_quotation: Mapped[PurchaseQuotationModel] = relationship(
        "PurchaseQuotationModel",
        back_populates="details",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_quotation_id", "company_id"],
            ["purchase_quotations.id", "purchase_quotations.company_id"],
            name="fk_purchase_quotation_details_quotation_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            name="fk_purchase_quotation_details_product_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            name="fk_purchase_quotation_details_unit_company",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "company_id",
            name="uq_purchase_quotation_details_id_company_id",
        ),
        CheckConstraint("quantity > 0", name="ck_purchase_quotation_details_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_purchase_quotation_details_unit_price"),
        CheckConstraint(
            "discount >= 0 AND subtotal >= 0 AND tax_amount >= 0 AND total >= 0",
            name="ck_purchase_quotation_details_amounts_nonnegative",
        ),
        CheckConstraint(
            "tax_rate >= 0 AND tax_rate <= 100",
            name="ck_purchase_quotation_details_tax_rate",
        ),
        CheckConstraint(
            "discount <= subtotal",
            name="ck_purchase_quotation_details_discount_within_subtotal",
        ),
        CheckConstraint(
            "delivery_days IS NULL OR delivery_days >= 0",
            name="ck_purchase_quotation_details_delivery_days",
        ),
        CheckConstraint(
            "available_quantity IS NULL OR "
            "(available_quantity >= 0 AND available_quantity <= quantity)",
            name="ck_purchase_quotation_details_available_quantity",
        ),
        Index(
            "ix_purchase_quotation_details_company_product",
            "company_id",
            "product_id",
        ),
    )


class PurchaseQuotationExpenseModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_quotation_expenses"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_quotation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    expense_type_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    purchase_quotation: Mapped[PurchaseQuotationModel] = relationship(
        "PurchaseQuotationModel",
        back_populates="expenses",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_quotation_id", "company_id"],
            ["purchase_quotations.id", "purchase_quotations.company_id"],
            name="fk_purchase_quotation_expenses_quotation_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["expense_type_id", "company_id"],
            ["expense_types.id", "expense_types.company_id"],
            name="fk_purchase_quotation_expenses_type_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint("amount > 0", name="ck_purchase_quotation_expenses_amount_positive"),
        Index(
            "ix_purchase_quotation_expenses_quotation",
            "purchase_quotation_id",
            "created_at",
        ),
    )
