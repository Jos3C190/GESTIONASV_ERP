"""Enrich products with lifecycle, commercial names and storage data."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("product_kind", sa.String(16), nullable=False, server_default="goods"))
    op.add_column("products", sa.Column("lifecycle_status", sa.String(20), nullable=False, server_default="active"))
    op.add_column("products", sa.Column("can_purchase", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("products", sa.Column("can_sell", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("products", sa.Column("sales_name", sa.String(200), nullable=True))
    op.add_column("products", sa.Column("internal_name", sa.String(200), nullable=True))
    op.add_column("products", sa.Column("document_name", sa.String(160), nullable=True))
    op.add_column("products", sa.Column("sales_description", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("purchase_description", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("internal_notes", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("keywords", sa.ARRAY(sa.String(80)), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")))
    op.add_column("products", sa.Column("origin_country_id", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("brand_id", sa.UUID(), nullable=True))
    op.add_column("products", sa.Column("manufacturer_id", sa.UUID(), nullable=True))
    op.add_column("products", sa.Column("storage_condition", sa.String(20), nullable=True))
    op.add_column("products", sa.Column("storage_temperature_min_c", sa.Numeric(6, 2), nullable=True))
    op.add_column("products", sa.Column("storage_temperature_max_c", sa.Numeric(6, 2), nullable=True))
    op.add_column("products", sa.Column("storage_humidity_max_percent", sa.Numeric(5, 2), nullable=True))
    op.add_column("products", sa.Column("is_fragile", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("products", sa.Column("keep_dry", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("products", sa.Column("keep_upright", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("products", sa.Column("stackable", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("products", sa.Column("max_stack_height", sa.Numeric(8, 2), nullable=True))
    op.add_column("products", sa.Column("handling_notes", sa.Text(), nullable=True))

    op.create_table(
        "product_brands",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("normalized_name", sa.String(160), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "company_id", name="uq_product_brands_id_company"),
        sa.UniqueConstraint("company_id", "normalized_name", name="uq_product_brands_company_name"),
        sa.UniqueConstraint("company_id", "code", name="uq_product_brands_company_code"),
    )
    op.create_table(
        "product_manufacturers",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("legal_name", sa.String(240), nullable=False),
        sa.Column("commercial_name", sa.String(200), nullable=True),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id_country", ondelete="RESTRICT"), nullable=True),
        sa.Column("website", sa.String(2048), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "company_id", name="uq_product_manufacturers_id_company"),
    )
    op.create_unique_constraint("uq_products_company_id_product", "products", ["company_id", "id_product"])
    op.create_foreign_key("fk_products_origin_country", "products", "countries", ["origin_country_id"], ["id_country"], ondelete="RESTRICT")
    op.create_foreign_key("fk_products_brand_company", "products", "product_brands", ["brand_id", "company_id"], ["id", "company_id"], ondelete="SET NULL")
    op.create_foreign_key("fk_products_manufacturer_company", "products", "product_manufacturers", ["manufacturer_id", "company_id"], ["id", "company_id"], ondelete="SET NULL")
    # Backfill before adding the consistency check, so legacy inactive rows remain valid.
    op.execute("UPDATE products SET lifecycle_status = CASE WHEN is_active THEN 'active' ELSE 'blocked' END")
    op.create_check_constraint("ck_products_product_kind", "products", "product_kind IN ('goods','service')")
    op.create_check_constraint("ck_products_lifecycle_status", "products", "lifecycle_status IN ('draft','active','blocked','discontinued','retired')")
    op.create_check_constraint("ck_products_active_matches_lifecycle", "products", "is_active = (lifecycle_status = 'active')")
    op.create_check_constraint("ck_products_storage_condition", "products", "storage_condition IS NULL OR storage_condition IN ('ambient','cool','refrigerated','frozen','dry','other')")
    op.create_check_constraint("ck_products_storage_temperature_range", "products", "storage_temperature_min_c IS NULL OR storage_temperature_max_c IS NULL OR storage_temperature_min_c <= storage_temperature_max_c")
    op.create_check_constraint("ck_products_storage_humidity_range", "products", "storage_humidity_max_percent IS NULL OR (storage_humidity_max_percent >= 0 AND storage_humidity_max_percent <= 100)")
    op.create_check_constraint("ck_products_stack_height_positive", "products", "max_stack_height IS NULL OR max_stack_height > 0")
    op.create_check_constraint("ck_products_service_no_storage", "products", "product_kind = 'goods' OR (storage_condition IS NULL AND storage_temperature_min_c IS NULL AND storage_temperature_max_c IS NULL AND storage_humidity_max_percent IS NULL AND is_fragile = false AND keep_dry = false AND keep_upright = false AND max_stack_height IS NULL AND handling_notes IS NULL)")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM product_brands LIMIT 1")).first() or bind.execute(sa.text("SELECT 1 FROM product_manufacturers LIMIT 1")).first():
        raise RuntimeError("No se puede revertir 0035: existen catálogos de marca o fabricante.")
    if bind.execute(sa.text("SELECT 1 FROM products WHERE sales_name IS NOT NULL OR internal_name IS NOT NULL OR document_name IS NOT NULL OR origin_country_id IS NOT NULL OR brand_id IS NOT NULL OR manufacturer_id IS NOT NULL OR storage_condition IS NOT NULL OR storage_temperature_min_c IS NOT NULL OR storage_temperature_max_c IS NOT NULL OR storage_humidity_max_percent IS NOT NULL OR is_fragile OR keep_dry OR keep_upright OR max_stack_height IS NOT NULL OR handling_notes IS NOT NULL OR cardinality(keywords) > 0 LIMIT 1")).first():
        raise RuntimeError("No se puede revertir 0035: existen datos maestros de producto que se perderían.")
    for name in ("ck_products_service_no_storage", "ck_products_stack_height_positive", "ck_products_storage_humidity_range", "ck_products_storage_temperature_range", "ck_products_storage_condition", "ck_products_active_matches_lifecycle", "ck_products_lifecycle_status", "ck_products_product_kind"):
        op.drop_constraint(name, "products", type_="check")
    for name in ("fk_products_manufacturer_company", "fk_products_brand_company", "fk_products_origin_country"):
        op.drop_constraint(name, "products", type_="foreignkey")
    op.drop_constraint("uq_products_company_id_product", "products", type_="unique")
    for name in ("handling_notes", "max_stack_height", "stackable", "keep_upright", "keep_dry", "is_fragile", "storage_humidity_max_percent", "storage_temperature_max_c", "storage_temperature_min_c", "storage_condition", "manufacturer_id", "brand_id", "origin_country_id", "keywords", "internal_notes", "purchase_description", "sales_description", "document_name", "internal_name", "sales_name", "can_sell", "can_purchase", "lifecycle_status", "product_kind"):
        op.drop_column("products", name)
    op.drop_table("product_manufacturers")
    op.drop_table("product_brands")
