from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class ProductImageModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "product_images"

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id_product", ondelete="CASCADE"), nullable=False, index=True
    )
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(160), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_cover: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    product = relationship("ProductModel", back_populates="images")
    media_asset = relationship("MediaAsset")

    __table_args__ = (
        UniqueConstraint("product_id", "position", name="uq_product_images_product_position"),
        UniqueConstraint("media_asset_id", name="uq_product_images_media_asset"),
        CheckConstraint(
            "source_type IN ('cloudinary', 'external')",
            name="ck_product_images_source_type",
        ),
        CheckConstraint("position >= 0 AND position < 20", name="ck_product_images_position"),
        CheckConstraint(
            "(source_type = 'external' AND media_asset_id IS NULL) "
            "OR (source_type = 'cloudinary' AND media_asset_id IS NOT NULL)",
            name="ck_product_images_source_asset_parity",
        ),
    )
