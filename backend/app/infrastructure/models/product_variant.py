"""ORM models for product families, attribute values and variants."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.infrastructure.models.catalog import ProductModel
    from app.infrastructure.models.media import MediaAsset
    from app.infrastructure.models.product_master import ProductIdentifierModel


class ProductFamilyAttributeModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "product_family_attributes"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            ondelete="CASCADE",
            name="fk_product_family_attributes_product_company",
        ),
        UniqueConstraint("company_id", "id", name="uq_product_family_attributes_company_id"),
        UniqueConstraint("company_id", "product_id", "id", name="uq_product_family_attributes_scope_id"),
        UniqueConstraint("company_id", "product_id", "code", name="uq_product_family_attributes_code"),
        CheckConstraint("position >= 0 AND position < 5", name="ck_product_family_attributes_position"),
        Index("ix_product_family_attributes_product", "company_id", "product_id", "is_active"),
    )

    product: Mapped[ProductModel] = relationship("ProductModel", back_populates="variant_attributes")
    values: Mapped[list[ProductFamilyAttributeValueModel]] = relationship(
        "ProductFamilyAttributeValueModel",
        back_populates="attribute",
        cascade="all, delete-orphan",
        order_by="ProductFamilyAttributeValueModel.position",
    )


class ProductFamilyAttributeValueModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "product_family_attribute_values"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    attribute_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_label: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "product_id", "attribute_id"],
            ["product_family_attributes.company_id", "product_family_attributes.product_id", "product_family_attributes.id"],
            ondelete="CASCADE",
            name="fk_product_family_values_attribute_scope",
        ),
        UniqueConstraint("company_id", "attribute_id", "id", name="uq_product_family_values_attribute_id"),
        UniqueConstraint("company_id", "product_id", "attribute_id", "id", name="uq_product_family_values_scope_id"),
        UniqueConstraint("company_id", "attribute_id", "code", name="uq_product_family_values_code"),
        UniqueConstraint("company_id", "attribute_id", "normalized_label", name="uq_product_family_values_label"),
        CheckConstraint("position >= 0", name="ck_product_family_values_position"),
        Index("ix_product_family_values_attribute", "company_id", "attribute_id", "is_active"),
    )

    attribute: Mapped[ProductFamilyAttributeModel] = relationship(
        "ProductFamilyAttributeModel", back_populates="values"
    )


class ProductVariantModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "product_variants"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    name_override: Mapped[str | None] = mapped_column(String(200), nullable=True)
    combination_key: Mapped[str] = mapped_column(String(512), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            ondelete="CASCADE",
            name="fk_product_variants_product_company",
        ),
        UniqueConstraint("company_id", "id", name="uq_product_variants_company_id"),
        UniqueConstraint("company_id", "product_id", "id", name="uq_product_variants_scope_id"),
        UniqueConstraint("company_id", "product_id", "combination_key", name="uq_product_variants_combination"),
        CheckConstraint("lifecycle_status IN ('draft','active','blocked','discontinued','retired')", name="ck_product_variants_lifecycle_status"),
        CheckConstraint("is_active = (lifecycle_status = 'active')", name="ck_product_variants_active_matches_lifecycle"),
        Index("ix_product_variants_product_status", "company_id", "product_id", "lifecycle_status"),
    )

    product: Mapped[ProductModel] = relationship("ProductModel", back_populates="variants")
    attribute_values: Mapped[list[ProductVariantAttributeValueModel]] = relationship(
        "ProductVariantAttributeValueModel",
        back_populates="variant",
        cascade="all, delete-orphan",
    )
    identifiers: Mapped[list[ProductIdentifierModel]] = relationship(
        "ProductIdentifierModel", back_populates="variant", cascade="all, delete-orphan"
    )
    image: Mapped[ProductVariantImageModel | None] = relationship(
        "ProductVariantImageModel", back_populates="variant", uselist=False, cascade="all, delete-orphan"
    )


class ProductVariantAttributeValueModel(Base):
    __tablename__ = "product_variant_attribute_values"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    attribute_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    value_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "product_id", "variant_id"],
            ["product_variants.company_id", "product_variants.product_id", "product_variants.id"],
            ondelete="CASCADE",
            name="fk_product_variant_values_variant_scope",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id", "attribute_id"],
            ["product_family_attributes.company_id", "product_family_attributes.product_id", "product_family_attributes.id"],
            ondelete="CASCADE",
            name="fk_product_variant_values_attribute_scope",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id", "attribute_id", "value_id"],
            ["product_family_attribute_values.company_id", "product_family_attribute_values.product_id", "product_family_attribute_values.attribute_id", "product_family_attribute_values.id"],
            ondelete="RESTRICT",
            name="fk_product_variant_values_value_scope",
        ),
        # One value per attribute and no duplicate value in a combination.
        PrimaryKeyConstraint("variant_id", "attribute_id", name="pk_product_variant_attribute_values"),
        UniqueConstraint("company_id", "product_id", "variant_id", "value_id", name="uq_product_variant_values_value"),
    )

    variant: Mapped[ProductVariantModel] = relationship(
        "ProductVariantModel", back_populates="attribute_values"
    )
    attribute: Mapped[ProductFamilyAttributeModel] = relationship("ProductFamilyAttributeModel")
    value: Mapped[ProductFamilyAttributeValueModel] = relationship("ProductFamilyAttributeValueModel")


class ProductVariantImageModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "product_variant_images"

    variant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=True, unique=True
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(160), nullable=True)

    __table_args__ = (
        CheckConstraint("source_type IN ('cloudinary', 'external')", name="ck_product_variant_images_source_type"),
        CheckConstraint(
            "(source_type = 'external' AND media_asset_id IS NULL) OR "
            "(source_type = 'cloudinary' AND media_asset_id IS NOT NULL)",
            name="ck_product_variant_images_source_asset_parity",
        ),
    )

    variant: Mapped[ProductVariantModel] = relationship("ProductVariantModel", back_populates="image")
    media_asset: Mapped[MediaAsset | None] = relationship("MediaAsset")


class ProductSkuRegistryModel(UUIDPKMixin, Base):
    __tablename__ = "product_sku_registry"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    normalized_sku: Mapped[str] = mapped_column(String(100), nullable=False)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            ondelete="CASCADE",
            name="fk_product_sku_registry_product_company",
        ),
        ForeignKeyConstraint(
            ["company_id", "variant_id"],
            ["product_variants.company_id", "product_variants.id"],
            ondelete="CASCADE",
            name="fk_product_sku_registry_variant_company",
        ),
        UniqueConstraint("company_id", "normalized_sku", name="uq_product_sku_registry_company_sku"),
        CheckConstraint("(product_id IS NOT NULL) <> (variant_id IS NOT NULL)", name="ck_product_sku_registry_target"),
        Index("ix_product_sku_registry_product", "company_id", "product_id"),
    )
