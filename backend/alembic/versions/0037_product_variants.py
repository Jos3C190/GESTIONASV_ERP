"""Add product families, attributes and catalog variants.

Variants are deliberately catalog-only in this revision.  Inventory, purchase,
sales and price documents will reference ``product_variants.id`` in a later
bounded context.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


VARIANT_PERMISSION = ("products:variants", "Gestionar variantes y atributos de productos", "products")


def upgrade() -> None:
    bind = op.get_bind()
    duplicate_skus = bind.execute(
        sa.text(
            "SELECT company_id, lower(btrim(sku)) AS normalized_sku "
            "FROM products WHERE deleted_at IS NULL "
            "GROUP BY company_id, lower(btrim(sku)) HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate_skus:
        raise RuntimeError(
            "No se puede activar el registro global de SKU: existen productos visibles "
            "duplicados después de normalizar mayúsculas y espacios."
        )
    bind.execute(
        sa.text(
            "INSERT INTO permissions (id, code, description, module, created_at) "
            "VALUES (gen_random_uuid(), :code, :description, :module, now()) "
            "ON CONFLICT DO NOTHING"
        ),
        dict(zip(("code", "description", "module"), VARIANT_PERMISSION, strict=False)),
    )

    op.add_column(
        "products",
        sa.Column("variant_mode", sa.String(16), nullable=False, server_default="standalone"),
    )
    op.create_check_constraint(
        "ck_products_variant_mode",
        "products",
        "variant_mode IN ('standalone', 'template')",
    )

    op.create_table(
        "product_sku_registry",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("normalized_sku", sa.String(100), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("variant_id", UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id", "product_id"], ["products.company_id", "products.id_product"], ondelete="CASCADE", name="fk_product_sku_registry_product_company"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "normalized_sku", name="uq_product_sku_registry_company_sku"),
        sa.CheckConstraint("(product_id IS NOT NULL) <> (variant_id IS NOT NULL)", name="ck_product_sku_registry_target"),
    )
    op.create_index("ix_product_sku_registry_product", "product_sku_registry", ["company_id", "product_id"])

    op.create_table(
        "product_family_attributes",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id", "product_id"], ["products.company_id", "products.id_product"], ondelete="CASCADE", name="fk_product_family_attributes_product_company"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_product_family_attributes_company_id"),
        # The scoped child FKs include product_id as well as the attribute id.
        # PostgreSQL requires the complete referenced column set to be backed
        # by a unique constraint, not only the tenant/id pair.
        sa.UniqueConstraint("company_id", "product_id", "id", name="uq_product_family_attributes_scope_id"),
        sa.UniqueConstraint("company_id", "product_id", "code", name="uq_product_family_attributes_code"),
        sa.CheckConstraint("position >= 0 AND position < 5", name="ck_product_family_attributes_position"),
    )
    op.create_index("ix_product_family_attributes_product", "product_family_attributes", ["company_id", "product_id", "is_active"])

    op.create_table(
        "product_family_attribute_values",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("attribute_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("normalized_label", sa.String(120), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id", "product_id", "attribute_id"], ["product_family_attributes.company_id", "product_family_attributes.product_id", "product_family_attributes.id"], ondelete="CASCADE", name="fk_product_family_values_attribute_scope"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "attribute_id", "id", name="uq_product_family_values_attribute_id"),
        sa.UniqueConstraint("company_id", "product_id", "attribute_id", "id", name="uq_product_family_values_scope_id"),
        sa.UniqueConstraint("company_id", "attribute_id", "code", name="uq_product_family_values_code"),
        sa.UniqueConstraint("company_id", "attribute_id", "normalized_label", name="uq_product_family_values_label"),
        sa.CheckConstraint("position >= 0", name="ck_product_family_values_position"),
    )
    op.create_index("ix_product_family_values_attribute", "product_family_attribute_values", ["company_id", "attribute_id", "is_active"])

    op.create_table(
        "product_variants",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("name_override", sa.String(200), nullable=True),
        sa.Column("combination_key", sa.String(512), nullable=False),
        sa.Column("lifecycle_status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id", "product_id"], ["products.company_id", "products.id_product"], ondelete="CASCADE", name="fk_product_variants_product_company"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_product_variants_company_id"),
        sa.UniqueConstraint("company_id", "product_id", "id", name="uq_product_variants_scope_id"),
        sa.UniqueConstraint("company_id", "product_id", "combination_key", name="uq_product_variants_combination"),
        sa.CheckConstraint("lifecycle_status IN ('draft','active','blocked','discontinued','retired')", name="ck_product_variants_lifecycle_status"),
        sa.CheckConstraint("is_active = (lifecycle_status = 'active')", name="ck_product_variants_active_matches_lifecycle"),
    )
    op.create_index("ix_product_variants_product_status", "product_variants", ["company_id", "product_id", "lifecycle_status"])

    op.create_foreign_key(
        "fk_product_sku_registry_variant_company",
        "product_sku_registry",
        "product_variants",
        ["company_id", "variant_id"],
        ["company_id", "id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "product_variant_attribute_values",
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("attribute_id", UUID(as_uuid=True), nullable=False),
        sa.Column("value_id", UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id", "product_id", "variant_id"], ["product_variants.company_id", "product_variants.product_id", "product_variants.id"], ondelete="CASCADE", name="fk_product_variant_values_variant_scope"),
        sa.ForeignKeyConstraint(["company_id", "product_id", "attribute_id"], ["product_family_attributes.company_id", "product_family_attributes.product_id", "product_family_attributes.id"], ondelete="CASCADE", name="fk_product_variant_values_attribute_scope"),
        sa.ForeignKeyConstraint(["company_id", "product_id", "attribute_id", "value_id"], ["product_family_attribute_values.company_id", "product_family_attribute_values.product_id", "product_family_attribute_values.attribute_id", "product_family_attribute_values.id"], ondelete="RESTRICT", name="fk_product_variant_values_value_scope"),
        sa.PrimaryKeyConstraint("variant_id", "attribute_id"),
        sa.UniqueConstraint("company_id", "product_id", "variant_id", "value_id", name="uq_product_variant_values_value"),
    )

    op.create_table(
        "product_variant_images",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("variant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("media_asset_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("alt_text", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("variant_id", name="uq_product_variant_images_variant"),
        sa.UniqueConstraint("media_asset_id", name="uq_product_variant_images_media_asset"),
        sa.CheckConstraint("source_type IN ('cloudinary', 'external')", name="ck_product_variant_images_source_type"),
        sa.CheckConstraint("(source_type = 'external' AND media_asset_id IS NULL) OR (source_type = 'cloudinary' AND media_asset_id IS NOT NULL)", name="ck_product_variant_images_source_asset_parity"),
    )

    op.drop_constraint("fk_product_identifiers_product_company", "product_identifiers", type_="foreignkey")
    op.alter_column("product_identifiers", "product_id", nullable=True)
    op.add_column("product_identifiers", sa.Column("variant_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_product_identifiers_product_company", "product_identifiers", "products", ["company_id", "product_id"], ["company_id", "id_product"], ondelete="CASCADE")
    op.create_foreign_key("fk_product_identifiers_variant_company", "product_identifiers", "product_variants", ["company_id", "variant_id"], ["company_id", "id"], ondelete="CASCADE")
    op.create_check_constraint("ck_product_identifiers_exact_target", "product_identifiers", "(product_id IS NOT NULL) <> (variant_id IS NOT NULL)")
    op.create_index("uq_product_identifiers_variant_primary", "product_identifiers", ["variant_id", "identifier_type"], unique=True, postgresql_where=sa.text("is_primary = true AND variant_id IS NOT NULL"))

    # Reserve all currently visible product SKUs.  Soft-deleted legacy rows are
    # intentionally excluded because the existing product index permits reuse.
    op.execute(
        sa.text(
            "INSERT INTO product_sku_registry (company_id, normalized_sku, product_id) "
            "SELECT company_id, lower(btrim(sku)), id_product FROM products "
            "WHERE deleted_at IS NULL"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("product_variant_images", "product_variant_attribute_values", "product_variants", "product_family_attribute_values", "product_family_attributes"):
        if bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError(f"No se puede revertir 0037: {table} contiene datos.")
    if bind.execute(sa.text("SELECT 1 FROM product_sku_registry WHERE variant_id IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("No se puede revertir 0037: existen SKU de variantes.")
    if bind.execute(sa.text("SELECT 1 FROM products WHERE variant_mode <> 'standalone' LIMIT 1")).first():
        raise RuntimeError("No se puede revertir 0037: existen productos configurados como familia.")
    if bind.execute(sa.text("SELECT 1 FROM product_identifiers WHERE variant_id IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("No se puede revertir 0037: existen identificadores de variantes.")

    op.drop_index("uq_product_identifiers_variant_primary", table_name="product_identifiers")
    op.drop_constraint("ck_product_identifiers_exact_target", "product_identifiers", type_="check")
    op.drop_constraint("fk_product_identifiers_variant_company", "product_identifiers", type_="foreignkey")
    op.drop_constraint("fk_product_identifiers_product_company", "product_identifiers", type_="foreignkey")
    op.drop_column("product_identifiers", "variant_id")
    op.alter_column("product_identifiers", "product_id", nullable=False)
    op.create_foreign_key("fk_product_identifiers_product_company", "product_identifiers", "products", ["company_id", "product_id"], ["company_id", "id_product"], ondelete="CASCADE")

    op.drop_table("product_variant_images")
    op.drop_table("product_variant_attribute_values")
    op.drop_constraint("fk_product_sku_registry_variant_company", "product_sku_registry", type_="foreignkey")
    op.drop_index("ix_product_variants_product_status", table_name="product_variants")
    op.drop_table("product_variants")
    op.drop_index("ix_product_family_values_attribute", table_name="product_family_attribute_values")
    op.drop_table("product_family_attribute_values")
    op.drop_index("ix_product_family_attributes_product", table_name="product_family_attributes")
    op.drop_table("product_family_attributes")
    op.drop_index("ix_product_sku_registry_product", table_name="product_sku_registry")
    op.drop_table("product_sku_registry")
    op.drop_constraint("ck_products_variant_mode", "products", type_="check")
    op.drop_column("products", "variant_mode")
