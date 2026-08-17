"""ORM models: CountryModel, CategoryModel, SubCategoryModel, UnitModel, ProductModel."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.models.product_image import ProductImageModel
    from app.infrastructure.models.product_master import (
        ProductBrandModel,
        ProductIdentifierModel,
        ProductManufacturerModel,
        ProductSupplierModel,
    )
    from app.infrastructure.models.supplier import SupplierModel


class CountryModel(TimestampMixin, Base):
    __tablename__ = "countries"

    id_country: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    iso_code_2: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
    iso_code_3: Mapped[str] = mapped_column(String(3), nullable=False, unique=True)
    phone_code: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    suppliers: Mapped[list[SupplierModel]] = relationship("SupplierModel", back_populates="country")


class CategoryModel(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "categories"

    id_category: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        Index(
            "uq_categories_company_name_visible",
            "company_id",
            func.lower(name),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_categories_company_active_name", "company_id", "is_active", "name"),
        Index("ix_categories_company_deleted_at", "company_id", "deleted_at"),
    )

    sub_categories: Mapped[list[SubCategoryModel]] = relationship(
        "SubCategoryModel", back_populates="category", cascade="all, delete-orphan"
    )
    products: Mapped[list[ProductModel]] = relationship("ProductModel", back_populates="category")


class SubCategoryModel(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "sub_categories"

    id_sub_category: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_category: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("categories.id_category", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        Index(
            "uq_subcategories_company_category_name_visible",
            "company_id",
            "id_category",
            func.lower(name),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_subcategories_company_category_active", "company_id", "id_category", "is_active"),
        Index("ix_sub_categories_company_deleted_at", "company_id", "deleted_at"),
    )

    category: Mapped[CategoryModel] = relationship("CategoryModel", back_populates="sub_categories")
    products: Mapped[list[ProductModel]] = relationship(
        "ProductModel", back_populates="sub_category"
    )


class UnitModel(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "units"

    id_unit: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_company_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_standard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        Index("ix_units_standard_active", "is_standard", "is_active"),
        Index(
            "uq_units_global_code_visible",
            func.lower(code),
            unique=True,
            postgresql_where=text("owner_company_id IS NULL AND deleted_at IS NULL"),
            sqlite_where=text("owner_company_id IS NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_units_company_code_visible",
            "owner_company_id",
            func.lower(code),
            unique=True,
            postgresql_where=text("owner_company_id IS NOT NULL AND deleted_at IS NULL"),
            sqlite_where=text("owner_company_id IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_units_global_name_visible",
            func.lower(name),
            unique=True,
            postgresql_where=text("owner_company_id IS NULL AND deleted_at IS NULL"),
            sqlite_where=text("owner_company_id IS NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_units_company_name_visible",
            "owner_company_id",
            func.lower(name),
            unique=True,
            postgresql_where=text("owner_company_id IS NOT NULL AND deleted_at IS NULL"),
            sqlite_where=text("owner_company_id IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index("ix_units_owner_company_deleted_at", "owner_company_id", "deleted_at"),
    )


class CompanyUnitModel(TimestampMixin, Base):
    __tablename__ = "company_units"
    __table_args__ = (Index("ix_company_units_company_enabled", "company_id", "is_enabled"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id_unit", ondelete="RESTRICT"), primary_key=True
    )
    alias: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    unit: Mapped[UnitModel] = relationship("UnitModel")


class ProductModel(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "products"

    id_product: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_sub_category: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("sub_categories.id_sub_category", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    id_category: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("categories.id_category", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    original_code: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    internal_code: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    size: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    dimensions: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    dimensions_legacy: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    dimension_length: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    dimension_width: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    dimension_height: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    dimension_unit: Mapped[str | None] = mapped_column(String(4), nullable=True)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    weight_unit: Mapped[str | None] = mapped_column(String(4), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    presentation: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    product_kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default="goods")
    lifecycle_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    can_purchase: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    can_sell: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sales_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    internal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    document_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sales_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String(80)), nullable=False, server_default=text("ARRAY[]::varchar[]"))
    origin_country_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("countries.id_country", ondelete="RESTRICT"), nullable=True)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    manufacturer_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    storage_condition: Mapped[str | None] = mapped_column(String(20), nullable=True)
    storage_temperature_min_c: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    storage_temperature_max_c: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    storage_humidity_max_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_fragile: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    keep_dry: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    keep_upright: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    stackable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    max_stack_height: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    handling_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_unit: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sale_unit: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        Index(
            "uq_products_company_sku_visible",
            "company_id",
            func.lower(sku),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        UniqueConstraint("company_id", "id_product", name="uq_products_company_id_product"),
        Index("ix_products_company_active_name", "company_id", "is_active", "name"),
        Index("ix_products_company_deleted_at", "company_id", "deleted_at"),
        CheckConstraint(
            "dimension_length IS NULL OR dimension_length >= 0",
            name="ck_products_dimension_length_nonnegative",
        ),
        CheckConstraint(
            "dimension_width IS NULL OR dimension_width >= 0",
            name="ck_products_dimension_width_nonnegative",
        ),
        CheckConstraint(
            "dimension_height IS NULL OR dimension_height >= 0",
            name="ck_products_dimension_height_nonnegative",
        ),
        CheckConstraint(
            "weight IS NULL OR weight >= 0",
            name="ck_products_weight_nonnegative",
        ),
        CheckConstraint(
            "dimension_unit IS NULL OR dimension_unit IN ('mm', 'cm', 'm', 'in', 'ft')",
            name="ck_products_dimension_unit",
        ),
        CheckConstraint(
            "weight_unit IS NULL OR weight_unit IN ('mg', 'g', 'kg', 't', 'oz', 'lb')",
            name="ck_products_weight_unit",
        ),
        CheckConstraint(
            "((dimension_length IS NULL AND dimension_width IS NULL AND dimension_height IS NULL) = (dimension_unit IS NULL))",
            name="ck_products_dimension_unit_pair",
        ),
        CheckConstraint(
            "((weight IS NULL) = (weight_unit IS NULL))",
            name="ck_products_weight_unit_pair",
        ),
        ForeignKeyConstraint(
            ["company_id", "purchase_unit"],
            ["company_units.company_id", "company_units.unit_id"],
            name="fk_products_company_purchase_unit",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["company_id", "sale_unit"],
            ["company_units.company_id", "company_units.unit_id"],
            name="fk_products_company_sale_unit",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["brand_id", "company_id"],
            ["product_brands.id", "product_brands.company_id"],
            name="fk_products_brand_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["manufacturer_id", "company_id"],
            ["product_manufacturers.id", "product_manufacturers.company_id"],
            name="fk_products_manufacturer_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint("product_kind IN ('goods','service')", name="ck_products_product_kind"),
        CheckConstraint("lifecycle_status IN ('draft','active','blocked','discontinued','retired')", name="ck_products_lifecycle_status"),
        CheckConstraint("is_active = (lifecycle_status = 'active')", name="ck_products_active_matches_lifecycle"),
        CheckConstraint("storage_condition IS NULL OR storage_condition IN ('ambient','cool','refrigerated','frozen','dry','other')", name="ck_products_storage_condition"),
        CheckConstraint("storage_temperature_min_c IS NULL OR storage_temperature_max_c IS NULL OR storage_temperature_min_c <= storage_temperature_max_c", name="ck_products_storage_temperature_range"),
        CheckConstraint("storage_humidity_max_percent IS NULL OR (storage_humidity_max_percent >= 0 AND storage_humidity_max_percent <= 100)", name="ck_products_storage_humidity_range"),
        CheckConstraint("max_stack_height IS NULL OR max_stack_height > 0", name="ck_products_stack_height_positive"),
        CheckConstraint("product_kind = 'goods' OR (storage_condition IS NULL AND storage_temperature_min_c IS NULL AND storage_temperature_max_c IS NULL AND storage_humidity_max_percent IS NULL AND is_fragile = false AND keep_dry = false AND keep_upright = false AND max_stack_height IS NULL AND handling_notes IS NULL)", name="ck_products_service_no_storage"),
    )

    category: Mapped[CategoryModel] = relationship("CategoryModel", back_populates="products")
    sub_category: Mapped[SubCategoryModel | None] = relationship(
        "SubCategoryModel", back_populates="products"
    )
    images: Mapped[list[ProductImageModel]] = relationship(
        "ProductImageModel",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImageModel.position",
        lazy="selectin",
    )
    identifiers: Mapped[list[ProductIdentifierModel]] = relationship(
        "ProductIdentifierModel", back_populates="product", cascade="all, delete-orphan", order_by="ProductIdentifierModel.identifier_type"
    )
    supplier_links: Mapped[list[ProductSupplierModel]] = relationship(
        "ProductSupplierModel", back_populates="product", cascade="all, delete-orphan", overlaps="supplier,product_links"
    )
    brand: Mapped[ProductBrandModel | None] = relationship("ProductBrandModel", foreign_keys=[brand_id], viewonly=True)
    manufacturer: Mapped[ProductManufacturerModel | None] = relationship("ProductManufacturerModel", foreign_keys=[manufacturer_id], viewonly=True)
