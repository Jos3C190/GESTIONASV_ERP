"""Add normalized product image galleries."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_images",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("media_asset_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("alt_text", sa.String(length=160), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_cover", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('cloudinary', 'external')",
            name="ck_product_images_source_type",
        ),
        sa.CheckConstraint("position >= 0 AND position < 20", name="ck_product_images_position"),
        sa.CheckConstraint(
            "(source_type = 'external' AND media_asset_id IS NULL) "
            "OR (source_type = 'cloudinary' AND media_asset_id IS NOT NULL)",
            name="ck_product_images_source_asset_parity",
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id_product"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "position", name="uq_product_images_product_position"),
        sa.UniqueConstraint("media_asset_id", name="uq_product_images_media_asset"),
    )
    op.create_index("ix_product_images_product_id", "product_images", ["product_id"])
    op.create_index("ix_product_images_media_asset_id", "product_images", ["media_asset_id"])
    op.create_index(
        "uq_product_images_cover",
        "product_images",
        ["product_id"],
        unique=True,
        postgresql_where=sa.text("is_cover = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_product_images_cover", table_name="product_images")
    op.drop_index("ix_product_images_media_asset_id", table_name="product_images")
    op.drop_index("ix_product_images_product_id", table_name="product_images")
    op.drop_table("product_images")
