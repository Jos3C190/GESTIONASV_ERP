"""ORM models: CountryModel, CategoryModel, SubCategoryModel, UnitModel, ProductModel."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.models.supplier import SupplierModel


class CountryModel(TimestampMixin, Base):
    __tablename__ = "countries"

    id_country: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    iso_code_2: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
    iso_code_3: Mapped[str] = mapped_column(String(3), nullable=False, unique=True)
    phone_code: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    suppliers: Mapped[list[SupplierModel]] = relationship("SupplierModel", back_populates="country")


class CategoryModel(TimestampMixin, Base):
    __tablename__ = "categories"

    id_category: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    uuid: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    sub_categories: Mapped[list[SubCategoryModel]] = relationship(
        "SubCategoryModel", back_populates="category", cascade="all, delete-orphan"
    )
    products: Mapped[list[ProductModel]] = relationship("ProductModel", back_populates="category")


class SubCategoryModel(TimestampMixin, Base):
    __tablename__ = "sub_categories"

    id_sub_category: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    id_category: Mapped[int] = mapped_column(
        Integer, ForeignKey("categories.id_category", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    category: Mapped[CategoryModel] = relationship("CategoryModel", back_populates="sub_categories")
    products: Mapped[list[ProductModel]] = relationship("ProductModel", back_populates="sub_category")


class UnitModel(TimestampMixin, Base):
    __tablename__ = "units"

    id_unit: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProductModel(TimestampMixin, Base):
    __tablename__ = "products"

    id_product: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    uuid: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
        server_default=text("gen_random_uuid()"),
    )
    id_sub_category: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sub_categories.id_sub_category", ondelete="SET NULL"), nullable=True, index=True
    )
    sku: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    id_category: Mapped[int] = mapped_column(
        Integer, ForeignKey("categories.id_category", ondelete="RESTRICT"), nullable=False, index=True
    )
    original_code: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    internal_code: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    size: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    dimensions: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    presentation: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    purchase_unit: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id_unit", ondelete="RESTRICT"), nullable=False, index=True
    )
    sale_unit: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id_unit", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    category: Mapped[CategoryModel] = relationship("CategoryModel", back_populates="products")
    sub_category: Mapped[SubCategoryModel | None] = relationship("SubCategoryModel", back_populates="products")
    purchase_unit_rel: Mapped[UnitModel] = relationship("UnitModel", foreign_keys=[purchase_unit])
    sale_unit_rel: Mapped[UnitModel] = relationship("UnitModel", foreign_keys=[sale_unit])
