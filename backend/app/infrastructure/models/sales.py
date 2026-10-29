"""Commercial sales documents. Physical delivery belongs to a later block."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class SalesCustomerModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_customers"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(320))
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    created_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    updated_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_customers_company_id"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["created_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_customers_created_by_company",
        ),
        ForeignKeyConstraint(
            ["updated_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_customers_updated_by_company",
        ),
        Index("uq_sales_customers_company_code", "company_id", func.lower(code), unique=True),
        Index("ix_sales_customers_company_active_name", "company_id", "is_active", "name"),
    )


class SalesQuotationModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_quotations"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    quotation_date: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="USD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_quotations_company_id"),
        UniqueConstraint("company_id", "code", name="uq_sales_quotations_company_code"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotations_branch_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "customer_id"],
            ["sales_customers.company_id", "sales_customers.id"],
            ondelete="RESTRICT",
            name="fk_sales_quotations_customer_company",
        ),
        ForeignKeyConstraint(
            ["created_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotations_creator_company",
        ),
        ForeignKeyConstraint(
            ["confirmed_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotations_confirmer_company",
        ),
        ForeignKeyConstraint(
            ["cancelled_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotations_canceller_company",
        ),
        CheckConstraint("currency = 'USD'", name="ck_sales_quotations_currency_usd"),
        CheckConstraint(
            "status IN ('draft','confirmed','cancelled')", name="ck_sales_quotations_status"
        ),
        CheckConstraint(
            "version >= 1 AND valid_until >= quotation_date",
            name="ck_sales_quotations_dates_version",
        ),
        CheckConstraint("subtotal >= 0 AND total = subtotal", name="ck_sales_quotations_totals"),
        CheckConstraint(
            "(confirmed_at IS NULL) = (confirmed_by_id IS NULL) "
            "AND (status <> 'confirmed' OR (confirmed_at IS NOT NULL AND confirmed_by_id IS NOT NULL)) "
            "AND (status <> 'draft' OR (confirmed_at IS NULL AND confirmed_by_id IS NULL))",
            name="ck_sales_quotations_confirmation",
        ),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL AND cancelled_by_id IS NOT NULL AND cancellation_reason IS NOT NULL)",
            name="ck_sales_quotations_cancellation",
        ),
        Index(
            "ix_sales_quotations_company_branch_status_date",
            "company_id",
            "branch_id",
            "status",
            "quotation_date",
        ),
        Index(
            "ix_sales_quotations_company_customer", "company_id", "customer_id", "quotation_date"
        ),
    )


class SalesQuotationLineModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_quotation_lines"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    quotation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    packaging_definition_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    packaging_version: Mapped[int | None] = mapped_column(Integer)
    unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    base_unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_unit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_quotation_lines_company_id"),
        UniqueConstraint(
            "company_id", "quotation_id", "line_number", name="uq_sales_quotation_lines_number"
        ),
        ForeignKeyConstraint(
            ["company_id", "quotation_id"],
            ["sales_quotations.company_id", "sales_quotations.id"],
            ondelete="CASCADE",
            name="fk_sales_quotation_lines_header_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            ondelete="RESTRICT",
            name="fk_sales_quotation_lines_product_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id", "variant_id"],
            ["product_variants.company_id", "product_variants.product_id", "product_variants.id"],
            ondelete="RESTRICT",
            name="fk_sales_quotation_lines_variant_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_sales_quotation_lines_item_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "packaging_definition_id"],
            [
                "inventory_packaging_definitions.company_id",
                "inventory_packaging_definitions.inventory_item_id",
                "inventory_packaging_definitions.id",
            ],
            ondelete="RESTRICT",
            name="fk_sales_quotation_lines_packaging",
        ),
        ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotation_lines_unit_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "base_unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_sales_quotation_lines_base_unit_company",
        ),
        CheckConstraint(
            "line_number > 0 AND quantity > 0 AND quantity_base > 0 AND unit_factor > 0",
            name="ck_sales_quotation_lines_quantities",
        ),
        CheckConstraint(
            "unit_price >= 0 AND line_total >= 0", name="ck_sales_quotation_lines_amounts"
        ),
        CheckConstraint(
            "(packaging_definition_id IS NULL) = (packaging_version IS NULL)",
            name="ck_sales_quotation_lines_packaging_snapshot",
        ),
    )


class SaleModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    quotation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="USD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_company_id"),
        UniqueConstraint("company_id", "code", name="uq_sales_company_code"),
        UniqueConstraint("company_id", "quotation_id", name="uq_sales_source_quotation"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_branch_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "customer_id"],
            ["sales_customers.company_id", "sales_customers.id"],
            ondelete="RESTRICT",
            name="fk_sales_customer_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "quotation_id"],
            ["sales_quotations.company_id", "sales_quotations.id"],
            ondelete="RESTRICT",
            name="fk_sales_source_quotation_company",
        ),
        ForeignKeyConstraint(
            ["created_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_creator_company",
        ),
        ForeignKeyConstraint(
            ["confirmed_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_confirmer_company",
        ),
        ForeignKeyConstraint(
            ["cancelled_by_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_canceller_company",
        ),
        CheckConstraint("currency = 'USD'", name="ck_sales_currency_usd"),
        CheckConstraint("status IN ('draft','confirmed','cancelled')", name="ck_sales_status"),
        CheckConstraint(
            "version >= 1 AND subtotal >= 0 AND total = subtotal", name="ck_sales_totals_version"
        ),
        CheckConstraint(
            "(confirmed_at IS NULL) = (confirmed_by_id IS NULL) "
            "AND (status <> 'confirmed' OR (confirmed_at IS NOT NULL AND confirmed_by_id IS NOT NULL)) "
            "AND (status <> 'draft' OR (confirmed_at IS NULL AND confirmed_by_id IS NULL))",
            name="ck_sales_confirmation",
        ),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL AND cancelled_by_id IS NOT NULL AND cancellation_reason IS NOT NULL)",
            name="ck_sales_cancellation",
        ),
        Index(
            "ix_sales_company_branch_status_created",
            "company_id",
            "branch_id",
            "status",
            "created_at",
        ),
    )


class SaleLineModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_lines"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sale_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_quotation_line_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    packaging_definition_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    packaging_version: Mapped[int | None] = mapped_column(Integer)
    unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    base_unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quantity_base: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_unit_name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_lines_company_id"),
        UniqueConstraint("company_id", "sale_id", "id", name="uq_sales_lines_company_sale_id"),
        UniqueConstraint("company_id", "sale_id", "line_number", name="uq_sales_lines_number"),
        UniqueConstraint(
            "company_id", "source_quotation_line_id", name="uq_sales_lines_source_quote_line"
        ),
        ForeignKeyConstraint(
            ["company_id", "sale_id"],
            ["sales.company_id", "sales.id"],
            ondelete="CASCADE",
            name="fk_sales_lines_header_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "source_quotation_line_id"],
            ["sales_quotation_lines.company_id", "sales_quotation_lines.id"],
            ondelete="RESTRICT",
            name="fk_sales_lines_source_quote_line",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            ondelete="RESTRICT",
            name="fk_sales_lines_product_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id", "variant_id"],
            ["product_variants.company_id", "product_variants.product_id", "product_variants.id"],
            ondelete="RESTRICT",
            name="fk_sales_lines_variant_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            ondelete="RESTRICT",
            name="fk_sales_lines_item_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_item_id", "packaging_definition_id"],
            [
                "inventory_packaging_definitions.company_id",
                "inventory_packaging_definitions.inventory_item_id",
                "inventory_packaging_definitions.id",
            ],
            ondelete="RESTRICT",
            name="fk_sales_lines_packaging",
        ),
        ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_sales_lines_unit_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "base_unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_sales_lines_base_unit_company",
        ),
        CheckConstraint(
            "line_number > 0 AND quantity > 0 AND quantity_base > 0 AND unit_factor > 0",
            name="ck_sales_lines_quantities",
        ),
        CheckConstraint("unit_price >= 0 AND line_total >= 0", name="ck_sales_lines_amounts"),
        CheckConstraint(
            "(packaging_definition_id IS NULL) = (packaging_version IS NULL)",
            name="ck_sales_lines_packaging_snapshot",
        ),
    )


class SalesIdempotencyModel(UUIDPKMixin, Base):
    __tablename__ = "sales_idempotency_commands"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(24), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "action", "idempotency_key", name="uq_sales_idempotency_action_key"
        ),
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["actor_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_idempotency_actor_company",
        ),
        CheckConstraint(
            "resource_type IN ('quotation','sale')", name="ck_sales_idempotency_resource_type"
        ),
    )
