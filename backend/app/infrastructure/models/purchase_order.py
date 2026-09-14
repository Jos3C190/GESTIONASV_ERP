"""ORM models for purchase orders, order details and additional expenses."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

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
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class PurchaseOrderModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_orders"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    supplier_id: Mapped[int] = mapped_column(Integer, nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_quotation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    order_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expected_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    discount: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    tax: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    additional_expenses: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    details: Mapped[list[PurchaseOrderDetailModel]] = relationship(
        "PurchaseOrderDetailModel",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PurchaseOrderDetailModel.created_at",
    )
    expenses: Mapped[list[PurchaseOrderExpenseModel]] = relationship(
        "PurchaseOrderExpenseModel",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PurchaseOrderExpenseModel.created_at",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "supplier_id"],
            ["suppliers.company_id", "suppliers.id_supplier"],
            name="fk_purchase_orders_supplier_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_purchase_orders_branch_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["warehouse_id", "branch_id"],
            ["warehouses.id", "warehouses.branch_id"],
            name="fk_purchase_orders_warehouse_branch",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["purchase_quotation_id", "company_id"],
            ["purchase_quotations.id", "purchase_quotations.company_id"],
            name="fk_purchase_orders_quotation_company",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "company_id", name="uq_purchase_orders_id_company_id"),
        UniqueConstraint("company_id", "code", name="uq_purchase_orders_company_code"),
        CheckConstraint(
            "status IN "
            "('draft','pending_approval','approved','sent','partially_received',"
            "'received','cancelled','closed')",
            name="ck_purchase_orders_status",
        ),
        CheckConstraint(
            "char_length(currency) = 3 AND currency = upper(currency)",
            name="ck_purchase_orders_currency",
        ),
        CheckConstraint(
            "expected_date IS NULL OR expected_date >= order_date",
            name="ck_purchase_orders_expected_date",
        ),
        CheckConstraint(
            "subtotal >= 0 AND discount >= 0 AND tax >= 0 "
            "AND additional_expenses >= 0 AND total >= 0",
            name="ck_purchase_orders_amounts_nonnegative",
        ),
        CheckConstraint(
            "discount <= subtotal",
            name="ck_purchase_orders_discount_within_subtotal",
        ),
        Index(
            "ix_purchase_orders_company_status_date",
            "company_id",
            "status",
            "order_date",
        ),
        Index(
            "ix_purchase_orders_company_supplier_date",
            "company_id",
            "supplier_id",
            "order_date",
        ),
        Index(
            "ix_purchase_orders_quotation",
            "purchase_quotation_id",
            "created_at",
        ),
        Index(
            "ix_purchase_orders_branch_warehouse_status",
            "branch_id",
            "warehouse_id",
            "status",
        ),
    )


class PurchaseOrderDetailModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_order_details"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_quotation_detail_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
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
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    purchase_order: Mapped[PurchaseOrderModel] = relationship(
        "PurchaseOrderModel",
        back_populates="details",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_order_id", "company_id"],
            ["purchase_orders.id", "purchase_orders.company_id"],
            name="fk_purchase_order_details_order_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["purchase_quotation_detail_id", "company_id"],
            ["purchase_quotation_details.id", "purchase_quotation_details.company_id"],
            name="fk_purchase_order_details_quotation_detail_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            name="fk_purchase_order_details_product_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            name="fk_purchase_order_details_unit_company",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "company_id",
            name="uq_purchase_order_details_id_company_id",
        ),
        CheckConstraint("quantity > 0", name="ck_purchase_order_details_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_purchase_order_details_unit_price"),
        CheckConstraint(
            "discount >= 0 AND subtotal >= 0 AND tax_amount >= 0 AND total >= 0",
            name="ck_purchase_order_details_amounts_nonnegative",
        ),
        CheckConstraint(
            "tax_rate >= 0 AND tax_rate <= 100",
            name="ck_purchase_order_details_tax_rate",
        ),
        CheckConstraint(
            "discount <= subtotal",
            name="ck_purchase_order_details_discount_within_subtotal",
        ),
        Index(
            "ix_purchase_order_details_order",
            "purchase_order_id",
            "created_at",
        ),
        Index(
            "ix_purchase_order_details_company_product",
            "company_id",
            "product_id",
        ),
        Index(
            "ix_purchase_order_details_company_quotation_detail",
            "company_id",
            "purchase_quotation_detail_id",
        ),
    )


class PurchaseOrderExpenseModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_order_expenses"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    expense_type_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    purchase_order: Mapped[PurchaseOrderModel] = relationship(
        "PurchaseOrderModel",
        back_populates="expenses",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_order_id", "company_id"],
            ["purchase_orders.id", "purchase_orders.company_id"],
            name="fk_purchase_order_expenses_order_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["expense_type_id", "company_id"],
            ["expense_types.id", "expense_types.company_id"],
            name="fk_purchase_order_expenses_type_company",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "company_id",
            name="uq_purchase_order_expenses_id_company_id",
        ),
        CheckConstraint("amount > 0", name="ck_purchase_order_expenses_amount_positive"),
        Index(
            "ix_purchase_order_expenses_order",
            "purchase_order_id",
            "created_at",
        ),
    )


class PurchaseOrderExpenseDocumentModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_order_expense_documents"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    purchase_order_expense_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(160), nullable=False)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_order_expense_id", "company_id"],
            ["purchase_order_expenses.id", "purchase_order_expenses.company_id"],
            name="fk_purchase_order_expense_documents_expense_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_id", "company_id"],
            ["document_assets.id", "document_assets.company_id"],
            name="fk_purchase_order_expense_documents_document_company",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "document_id",
            name="uq_purchase_order_expense_documents_document",
        ),
        Index(
            "ix_purchase_order_expense_documents_expense",
            "purchase_order_expense_id",
            "created_at",
        ),
        Index(
            "ix_purchase_order_expense_documents_company",
            "company_id",
            "created_at",
        ),
    )
