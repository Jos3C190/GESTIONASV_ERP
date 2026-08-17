"""Add product identifiers and company-safe supplier relations."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_suppliers_company_id_supplier", "suppliers", ["company_id", "id_supplier"])
    op.create_table(
        "product_identifiers",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("identifier_type", sa.String(24), nullable=False),
        sa.Column("value", sa.String(160), nullable=False),
        sa.Column("normalized_value", sa.String(160), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id", "product_id"], ["products.company_id", "products.id_product"], ondelete="CASCADE", name="fk_product_identifiers_product_company"),
        sa.UniqueConstraint("company_id", "identifier_type", "normalized_value", name="uq_product_identifiers_company_value"),
        sa.CheckConstraint("identifier_type IN ('ean','upc','gtin','isbn','manufacturer','internal','other')", name="ck_product_identifiers_type"),
    )
    op.create_index("uq_product_identifiers_primary", "product_identifiers", ["product_id", "identifier_type"], unique=True, postgresql_where=sa.text("is_primary = true"))
    op.create_table(
        "product_suppliers",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("supplier_product_code", sa.String(120), nullable=True),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column("minimum_order_qty", sa.Numeric(14, 4), nullable=True),
        sa.Column("order_multiple", sa.Numeric(14, 4), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id", "product_id"], ["products.company_id", "products.id_product"], ondelete="CASCADE", name="fk_product_suppliers_product_company"),
        sa.ForeignKeyConstraint(["company_id", "supplier_id"], ["suppliers.company_id", "suppliers.id_supplier"], ondelete="RESTRICT", name="fk_product_suppliers_supplier_company"),
        sa.UniqueConstraint("company_id", "product_id", "supplier_id", name="uq_product_suppliers_pair"),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_product_suppliers_status"),
        sa.CheckConstraint("unit_cost IS NULL OR unit_cost >= 0", name="ck_product_suppliers_cost_nonnegative"),
        sa.CheckConstraint("minimum_order_qty IS NULL OR minimum_order_qty > 0", name="ck_product_suppliers_moq_positive"),
        sa.CheckConstraint("order_multiple IS NULL OR order_multiple > 0", name="ck_product_suppliers_multiple_positive"),
        sa.CheckConstraint("lead_time_days IS NULL OR lead_time_days >= 0", name="ck_product_suppliers_lead_time_nonnegative"),
        sa.CheckConstraint("valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from", name="ck_product_suppliers_date_range"),
    )
    op.create_index("uq_product_suppliers_preferred", "product_suppliers", ["product_id"], unique=True, postgresql_where=sa.text("is_preferred = true AND status = 'active'"))
    # Preserve legacy codes as identifiers only when they are unambiguous.
    op.execute("INSERT INTO product_identifiers (company_id, product_id, identifier_type, value, normalized_value, is_primary) SELECT company_id, id_product, 'manufacturer', original_code, upper(regexp_replace(original_code, '[[:space:]-]+', '', 'g')), false FROM products WHERE NULLIF(btrim(original_code), '') IS NOT NULL ON CONFLICT DO NOTHING")
    op.execute("INSERT INTO product_identifiers (company_id, product_id, identifier_type, value, normalized_value, is_primary) SELECT company_id, id_product, 'internal', internal_code, upper(regexp_replace(internal_code, '[[:space:]-]+', '', 'g')), false FROM products WHERE NULLIF(btrim(internal_code), '') IS NOT NULL ON CONFLICT DO NOTHING")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM product_suppliers LIMIT 1")).first() or bind.execute(sa.text("SELECT 1 FROM product_identifiers LIMIT 1")).first():
        raise RuntimeError("No se puede revertir 0036: existen identificadores o relaciones producto-proveedor.")
    op.drop_index("uq_product_suppliers_preferred", table_name="product_suppliers")
    op.drop_table("product_suppliers")
    op.drop_index("uq_product_identifiers_primary", table_name="product_identifiers")
    op.drop_table("product_identifiers")
    op.drop_constraint("uq_suppliers_company_id_supplier", "suppliers", type_="unique")
