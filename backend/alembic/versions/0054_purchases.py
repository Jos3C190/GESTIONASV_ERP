"""Create supplier purchase receipts and received details."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchases",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("purchase_order_id", UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "purchase_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("supplier_invoice_number", sa.String(80), nullable=True),
        sa.Column("supplier_invoice_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("subtotal", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("discount", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("tax", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_purchases_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id", "company_id"],
            ["purchase_orders.id", "purchase_orders.company_id"],
            name="fk_purchases_order_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "supplier_id"],
            ["suppliers.company_id", "suppliers.id_supplier"],
            name="fk_purchases_supplier_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_purchases_branch_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id", "branch_id"],
            ["warehouses.id", "warehouses.branch_id"],
            name="fk_purchases_warehouse_branch",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_purchases_created_by_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency"],
            ["currencies.code"],
            name="fk_purchases_currency_currencies",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "company_id", name="uq_purchases_id_company_id"),
        sa.UniqueConstraint("company_id", "code", name="uq_purchases_company_code"),
        sa.CheckConstraint(
            "status IN ('draft','received','verified','cancelled','closed')",
            name="ck_purchases_status",
        ),
        sa.CheckConstraint(
            "char_length(currency) = 3 AND currency = upper(currency)",
            name="ck_purchases_currency",
        ),
        sa.CheckConstraint(
            "subtotal >= 0 AND discount >= 0 AND tax >= 0 AND total >= 0",
            name="ck_purchases_amounts_nonnegative",
        ),
        sa.CheckConstraint(
            "discount <= subtotal",
            name="ck_purchases_discount_within_subtotal",
        ),
    )
    op.create_index(
        "ix_purchases_company_status_date",
        "purchases",
        ["company_id", "status", "purchase_date"],
    )
    op.create_index(
        "ix_purchases_order_date",
        "purchases",
        ["purchase_order_id", "purchase_date"],
    )
    op.create_index(
        "ix_purchases_branch_warehouse_date",
        "purchases",
        ["branch_id", "warehouse_id", "purchase_date"],
    )

    op.create_table(
        "purchase_details",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_order_detail_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity_ordered", sa.Numeric(18, 6), nullable=False),
        sa.Column("quantity_received", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("discount", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(9, 6), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["purchase_id", "company_id"],
            ["purchases.id", "purchases.company_id"],
            name="fk_purchase_details_purchase_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_detail_id", "company_id"],
            ["purchase_order_details.id", "purchase_order_details.company_id"],
            name="fk_purchase_details_order_detail_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            name="fk_purchase_details_product_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            name="fk_purchase_details_unit_company",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "company_id", name="uq_purchase_details_id_company_id"),
        sa.UniqueConstraint(
            "purchase_id",
            "purchase_order_detail_id",
            name="uq_purchase_details_purchase_order_detail",
        ),
        sa.CheckConstraint(
            "quantity_ordered > 0",
            name="ck_purchase_details_ordered_positive",
        ),
        sa.CheckConstraint(
            "quantity_received > 0",
            name="ck_purchase_details_received_positive",
        ),
        sa.CheckConstraint(
            "quantity_received <= quantity_ordered",
            name="ck_purchase_details_received_within_ordered",
        ),
        sa.CheckConstraint(
            "unit_price >= 0",
            name="ck_purchase_details_unit_price",
        ),
        sa.CheckConstraint(
            "discount >= 0 AND subtotal >= 0 AND tax_amount >= 0 AND total >= 0",
            name="ck_purchase_details_amounts_nonnegative",
        ),
        sa.CheckConstraint(
            "tax_rate >= 0 AND tax_rate <= 100",
            name="ck_purchase_details_tax_rate",
        ),
        sa.CheckConstraint(
            "discount <= subtotal",
            name="ck_purchase_details_discount_within_subtotal",
        ),
    )
    op.create_index(
        "ix_purchase_details_purchase",
        "purchase_details",
        ["purchase_id", "created_at"],
    )
    op.create_index(
        "ix_purchase_details_company_order_detail",
        "purchase_details",
        ["company_id", "purchase_order_detail_id"],
    )


def downgrade() -> None:
    op.drop_table("purchase_details")
    op.drop_table("purchases")
