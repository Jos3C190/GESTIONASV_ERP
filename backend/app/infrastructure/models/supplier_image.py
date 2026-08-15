"""ORM models for supplier logos and contact avatars."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.infrastructure.models.supplier import SupplierContactModel, SupplierModel


class SupplierImageModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "supplier_images"

    supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id_supplier", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(160), nullable=True)

    supplier: Mapped[SupplierModel] = relationship("SupplierModel", back_populates="image")
    __table_args__ = (
        UniqueConstraint("supplier_id", name="uq_supplier_images_supplier"),
        UniqueConstraint("media_asset_id", name="uq_supplier_images_media_asset"),
        CheckConstraint(
            "source_type IN ('cloudinary', 'external')",
            name="ck_supplier_images_source_type",
        ),
        CheckConstraint(
            "(source_type = 'external' AND media_asset_id IS NULL) "
            "OR (source_type = 'cloudinary' AND media_asset_id IS NOT NULL)",
            name="ck_supplier_images_source_asset_parity",
        ),
        CheckConstraint("char_length(url) <= 2048", name="ck_supplier_images_url_length"),
        CheckConstraint(
            "alt_text IS NULL OR char_length(alt_text) <= 160",
            name="ck_supplier_images_alt_length",
        ),
    )


class SupplierContactImageModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "supplier_contact_images"

    supplier_contact_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("supplier_contacts.id_supplier_contact", ondelete="CASCADE"),
        nullable=False,
    )
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(160), nullable=True)

    supplier_contact: Mapped[SupplierContactModel] = relationship(
        "SupplierContactModel", back_populates="image"
    )
    __table_args__ = (
        UniqueConstraint("supplier_contact_id", name="uq_supplier_contact_images_contact"),
        UniqueConstraint("media_asset_id", name="uq_supplier_contact_images_media_asset"),
        CheckConstraint(
            "source_type IN ('cloudinary', 'external')",
            name="ck_supplier_contact_images_source_type",
        ),
        CheckConstraint(
            "(source_type = 'external' AND media_asset_id IS NULL) "
            "OR (source_type = 'cloudinary' AND media_asset_id IS NOT NULL)",
            name="ck_supplier_contact_images_source_asset_parity",
        ),
        CheckConstraint("char_length(url) <= 2048", name="ck_supplier_contact_images_url_length"),
        CheckConstraint(
            "alt_text IS NULL OR char_length(alt_text) <= 160",
            name="ck_supplier_contact_images_alt_length",
        ),
    )
