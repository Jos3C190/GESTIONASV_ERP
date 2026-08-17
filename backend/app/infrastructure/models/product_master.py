"""ORM models for product master data and supplier sourcing."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.models.catalog import ProductModel
    from app.infrastructure.models.supplier import SupplierModel


class ProductBrandModel(TimestampMixin, Base):
    __tablename__ = "product_brands"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        UniqueConstraint("company_id", "normalized_name", name="uq_product_brands_company_name"),
        UniqueConstraint("company_id", "code", name="uq_product_brands_company_code"),
    )


class ProductManufacturerModel(TimestampMixin, Base):
    __tablename__ = "product_manufacturers"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    commercial_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    country_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("countries.id_country", ondelete="RESTRICT"), nullable=True)
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (Index("ix_product_manufacturers_company_name", "company_id", func.lower(legal_name)),)


class ProductIdentifierModel(TimestampMixin, Base):
    __tablename__ = "product_identifiers"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    identifier_type: Mapped[str] = mapped_column(String(24), nullable=False)
    value: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(160), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        ForeignKeyConstraint(["company_id", "product_id"], ["products.company_id", "products.id_product"], ondelete="CASCADE", name="fk_product_identifiers_product_company"),
        UniqueConstraint("company_id", "identifier_type", "normalized_value", name="uq_product_identifiers_company_value"),
        Index("uq_product_identifiers_primary", "product_id", "identifier_type", unique=True, postgresql_where=text("is_primary = true")),
        CheckConstraint("identifier_type IN ('ean','upc','gtin','isbn','manufacturer','internal','other')", name="ck_product_identifiers_type"),
    )
    product: Mapped[ProductModel] = relationship("ProductModel", back_populates="identifiers")


class ProductSupplierModel(TimestampMixin, Base):
    __tablename__ = "product_suppliers"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    supplier_product_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    minimum_order_qty: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    order_multiple: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(["company_id", "product_id"], ["products.company_id", "products.id_product"], ondelete="CASCADE", name="fk_product_suppliers_product_company"),
        ForeignKeyConstraint(["company_id", "supplier_id"], ["suppliers.company_id", "suppliers.id_supplier"], ondelete="RESTRICT", name="fk_product_suppliers_supplier_company"),
        UniqueConstraint("company_id", "product_id", "supplier_id", name="uq_product_suppliers_pair"),
        Index("uq_product_suppliers_preferred", "product_id", unique=True, postgresql_where=text("is_preferred = true AND status = 'active'")),
        CheckConstraint("status IN ('active','inactive')", name="ck_product_suppliers_status"),
        CheckConstraint("unit_cost IS NULL OR unit_cost >= 0", name="ck_product_suppliers_cost_nonnegative"),
        CheckConstraint("minimum_order_qty IS NULL OR minimum_order_qty > 0", name="ck_product_suppliers_moq_positive"),
        CheckConstraint("order_multiple IS NULL OR order_multiple > 0", name="ck_product_suppliers_multiple_positive"),
        CheckConstraint("lead_time_days IS NULL OR lead_time_days >= 0", name="ck_product_suppliers_lead_time_nonnegative"),
        CheckConstraint("valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from", name="ck_product_suppliers_date_range"),
    )
    product: Mapped[ProductModel] = relationship("ProductModel", back_populates="supplier_links", overlaps="supplier,product_links")
    supplier: Mapped[SupplierModel] = relationship("SupplierModel", back_populates="product_links", overlaps="product,supplier_links")
