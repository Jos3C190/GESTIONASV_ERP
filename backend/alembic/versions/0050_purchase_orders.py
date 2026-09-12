"""Create purchase orders, order details and order expenses."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_warehouses_id_branch_id",
        "warehouses",
        ["id", "branch_id"],
    )

    op.create_table(
        "purchase_orders",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_quotation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "order_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expected_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("payment_terms", sa.Text(), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("discount", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("tax", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column(
            "additional_expenses",
            sa.Numeric(18, 6),
            nullable=False,
            server_default="0",
        ),
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
            name="fk_purchase_orders_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "supplier_id"],
            ["suppliers.company_id", "suppliers.id_supplier"],
            name="fk_purchase_orders_supplier_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_purchase_orders_branch_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id", "branch_id"],
            ["warehouses.id", "warehouses.branch_id"],
            name="fk_purchase_orders_warehouse_branch",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_quotation_id", "company_id"],
            ["purchase_quotations.id", "purchase_quotations.company_id"],
            name="fk_purchase_orders_quotation_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency"],
            ["currencies.code"],
            name="fk_purchase_orders_currency_currencies",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_purchase_orders_created_by_id_users",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "company_id", name="uq_purchase_orders_id_company_id"),
        sa.UniqueConstraint("company_id", "code", name="uq_purchase_orders_company_code"),
        sa.CheckConstraint(
            "status IN "
            "('draft','pending_approval','approved','sent','partially_received',"
            "'received','cancelled','closed')",
            name="ck_purchase_orders_status",
        ),
        sa.CheckConstraint(
            "char_length(currency) = 3 AND currency = upper(currency)",
            name="ck_purchase_orders_currency",
        ),
        sa.CheckConstraint(
            "expected_date IS NULL OR expected_date >= order_date",
            name="ck_purchase_orders_expected_date",
        ),
        sa.CheckConstraint(
            "subtotal >= 0 AND discount >= 0 AND tax >= 0 "
            "AND additional_expenses >= 0 AND total >= 0",
            name="ck_purchase_orders_amounts_nonnegative",
        ),
        sa.CheckConstraint(
            "discount <= subtotal",
            name="ck_purchase_orders_discount_within_subtotal",
        ),
    )
    op.create_index(
        "ix_purchase_orders_company_status_date",
        "purchase_orders",
        ["company_id", "status", "order_date"],
    )
    op.create_index(
        "ix_purchase_orders_company_supplier_date",
        "purchase_orders",
        ["company_id", "supplier_id", "order_date"],
    )
    op.create_index(
        "ix_purchase_orders_quotation",
        "purchase_orders",
        ["purchase_quotation_id", "created_at"],
    )
    op.create_index(
        "ix_purchase_orders_branch_warehouse_status",
        "purchase_orders",
        ["branch_id", "warehouse_id", "status"],
    )

    op.create_table(
        "purchase_order_details",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_order_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
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
            ["purchase_order_id", "company_id"],
            ["purchase_orders.id", "purchase_orders.company_id"],
            name="fk_purchase_order_details_order_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            name="fk_purchase_order_details_product_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            name="fk_purchase_order_details_unit_company",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "id",
            "company_id",
            name="uq_purchase_order_details_id_company_id",
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_purchase_order_details_quantity_positive",
        ),
        sa.CheckConstraint(
            "unit_price >= 0",
            name="ck_purchase_order_details_unit_price",
        ),
        sa.CheckConstraint(
            "discount >= 0 AND subtotal >= 0 AND tax_amount >= 0 AND total >= 0",
            name="ck_purchase_order_details_amounts_nonnegative",
        ),
        sa.CheckConstraint(
            "tax_rate >= 0 AND tax_rate <= 100",
            name="ck_purchase_order_details_tax_rate",
        ),
        sa.CheckConstraint(
            "discount <= subtotal",
            name="ck_purchase_order_details_discount_within_subtotal",
        ),
    )
    op.create_index(
        "ix_purchase_order_details_order",
        "purchase_order_details",
        ["purchase_order_id", "created_at"],
    )
    op.create_index(
        "ix_purchase_order_details_company_product",
        "purchase_order_details",
        ["company_id", "product_id"],
    )

    op.create_table(
        "purchase_order_expenses",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_order_id", UUID(as_uuid=True), nullable=False),
        sa.Column("expense_type_id", UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 6), nullable=False),
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
            ["purchase_order_id", "company_id"],
            ["purchase_orders.id", "purchase_orders.company_id"],
            name="fk_purchase_order_expenses_order_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["expense_type_id", "company_id"],
            ["expense_types.id", "expense_types.company_id"],
            name="fk_purchase_order_expenses_type_company",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "id",
            "company_id",
            name="uq_purchase_order_expenses_id_company_id",
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_purchase_order_expenses_amount_positive",
        ),
    )
    op.create_index(
        "ix_purchase_order_expenses_order",
        "purchase_order_expenses",
        ["purchase_order_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("purchase_order_expenses")
    op.drop_table("purchase_order_details")
    op.drop_table("purchase_orders")
    op.drop_constraint(
        "uq_warehouses_id_branch_id",
        "warehouses",
        type_="unique",
    )
