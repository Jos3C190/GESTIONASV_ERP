"""Add primary images for suppliers and supplier contacts."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def _assert_empty(bind: sa.Connection, table: str) -> None:
    count = bind.execute(sa.text(f"SELECT count(*) FROM {table}"))
    if int(count.scalar_one()) > 0:
        raise RuntimeError(
            f"No se puede hacer downgrade 0032: {table} contiene imágenes asociadas. "
            "Elimine las relaciones de forma controlada antes de revertir."
        )


def upgrade() -> None:
    op.add_column(
        "supplier_contacts",
        sa.Column(
            "uuid",
            UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )
    op.create_unique_constraint("uq_supplier_contacts_uuid", "supplier_contacts", ["uuid"])
    op.create_index("ix_supplier_contacts_uuid", "supplier_contacts", ["uuid"])

    op.create_table(
        "supplier_images",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("media_asset_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("alt_text", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('cloudinary', 'external')",
            name="ck_supplier_images_source_type",
        ),
        sa.CheckConstraint(
            "(source_type = 'external' AND media_asset_id IS NULL) "
            "OR (source_type = 'cloudinary' AND media_asset_id IS NOT NULL)",
            name="ck_supplier_images_source_asset_parity",
        ),
        sa.CheckConstraint("char_length(url) <= 2048", name="ck_supplier_images_url_length"),
        sa.CheckConstraint(
            "alt_text IS NULL OR char_length(alt_text) <= 160",
            name="ck_supplier_images_alt_length",
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id_supplier"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_id", name="uq_supplier_images_supplier"),
        sa.UniqueConstraint("media_asset_id", name="uq_supplier_images_media_asset"),
    )
    op.create_index("ix_supplier_images_supplier_id", "supplier_images", ["supplier_id"])
    op.create_index("ix_supplier_images_media_asset_id", "supplier_images", ["media_asset_id"])

    op.create_table(
        "supplier_contact_images",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("supplier_contact_id", sa.Integer(), nullable=False),
        sa.Column("media_asset_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("alt_text", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('cloudinary', 'external')",
            name="ck_supplier_contact_images_source_type",
        ),
        sa.CheckConstraint(
            "(source_type = 'external' AND media_asset_id IS NULL) "
            "OR (source_type = 'cloudinary' AND media_asset_id IS NOT NULL)",
            name="ck_supplier_contact_images_source_asset_parity",
        ),
        sa.CheckConstraint("char_length(url) <= 2048", name="ck_supplier_contact_images_url_length"),
        sa.CheckConstraint(
            "alt_text IS NULL OR char_length(alt_text) <= 160",
            name="ck_supplier_contact_images_alt_length",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_contact_id"],
            ["supplier_contacts.id_supplier_contact"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_contact_id", name="uq_supplier_contact_images_contact"),
        sa.UniqueConstraint("media_asset_id", name="uq_supplier_contact_images_media_asset"),
    )
    op.create_index(
        "ix_supplier_contact_images_contact_id", "supplier_contact_images", ["supplier_contact_id"]
    )
    op.create_index(
        "ix_supplier_contact_images_media_asset_id", "supplier_contact_images", ["media_asset_id"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    _assert_empty(bind, "supplier_images")
    _assert_empty(bind, "supplier_contact_images")
    op.drop_index("ix_supplier_contact_images_media_asset_id", table_name="supplier_contact_images")
    op.drop_index("ix_supplier_contact_images_contact_id", table_name="supplier_contact_images")
    op.drop_table("supplier_contact_images")
    op.drop_index("ix_supplier_images_media_asset_id", table_name="supplier_images")
    op.drop_index("ix_supplier_images_supplier_id", table_name="supplier_images")
    op.drop_table("supplier_images")
    op.drop_index("ix_supplier_contacts_uuid", table_name="supplier_contacts")
    op.drop_constraint("uq_supplier_contacts_uuid", "supplier_contacts", type_="unique")
    op.drop_column("supplier_contacts", "uuid")
