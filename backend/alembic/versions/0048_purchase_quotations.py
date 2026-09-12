"""Create purchase quotations, RFQ coverage and quotation expenses."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_purchase_request_details_id_company_id",
        "purchase_request_details",
        ["id", "company_id"],
    )

    op.create_table(
        "expense_types",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
            name="fk_expense_types_company_id_companies",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("id", "company_id", name="uq_expense_types_id_company_id"),
    )
    op.create_index(
        "uq_expense_types_company_name",
        "expense_types",
        ["company_id", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index(
        "ix_expense_types_company_active",
        "expense_types",
        ["company_id", "is_active"],
    )

    op.create_table(
        "purchase_quotations",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column(
            "quotation_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("payment_terms", sa.Text(), nullable=True),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("discount", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("tax", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", UUID(as_uuid=True), nullable=False),
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
            name="fk_purchase_quotations_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "supplier_id"],
            ["suppliers.company_id", "suppliers.id_supplier"],
            name="fk_purchase_quotations_supplier_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency"],
            ["currencies.code"],
            name="fk_purchase_quotations_currency_currencies",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_purchase_quotations_created_by_id_users",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "company_id", name="uq_purchase_quotations_id_company_id"),
        sa.UniqueConstraint("company_id", "code", name="uq_purchase_quotations_company_code"),
        sa.CheckConstraint(
            "status IN "
            "('draft','requested','received','under_evaluation','selected','rejected',"
            "'expired','cancelled')",
            name="ck_purchase_quotations_status",
        ),
        sa.CheckConstraint(
            "char_length(currency) = 3 AND currency = upper(currency)",
            name="ck_purchase_quotations_currency",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until >= quotation_date",
            name="ck_purchase_quotations_validity",
        ),
        sa.CheckConstraint(
            "delivery_days IS NULL OR delivery_days >= 0",
            name="ck_purchase_quotations_delivery_days",
        ),
        sa.CheckConstraint(
            "subtotal >= 0 AND discount >= 0 AND tax >= 0 AND total >= 0",
            name="ck_purchase_quotations_amounts_nonnegative",
        ),
        sa.CheckConstraint(
            "discount <= subtotal",
            name="ck_purchase_quotations_discount_within_subtotal",
        ),
    )
    op.create_index(
        "ix_purchase_quotations_company_status_date",
        "purchase_quotations",
        ["company_id", "status", "quotation_date"],
    )
    op.create_index(
        "ix_purchase_quotations_company_supplier_date",
        "purchase_quotations",
        ["company_id", "supplier_id", "quotation_date"],
    )

    op.create_table(
        "purchase_quotation_requests",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_quotation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_request_id", UUID(as_uuid=True), nullable=False),
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
            ["purchase_quotation_id", "company_id"],
            ["purchase_quotations.id", "purchase_quotations.company_id"],
            name="fk_purchase_quotation_requests_quotation_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_request_id", "company_id"],
            ["purchase_requests.id", "purchase_requests.company_id"],
            name="fk_purchase_quotation_requests_request_company",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "id",
            "company_id",
            name="uq_purchase_quotation_requests_id_company_id",
        ),
        sa.UniqueConstraint(
            "purchase_quotation_id",
            "purchase_request_id",
            name="uq_purchase_quotation_requests_pair",
        ),
    )
    op.create_index(
        "ix_purchase_quotation_requests_request",
        "purchase_quotation_requests",
        ["purchase_request_id", "created_at"],
    )

    op.create_table(
        "purchase_quotation_request_details",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_quotation_request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_quotation_detail_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_request_detail_id", UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
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
            ["purchase_quotation_request_id", "company_id"],
            ["purchase_quotation_requests.id", "purchase_quotation_requests.company_id"],
            name="fk_purchase_quotation_request_details_link_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_request_detail_id", "company_id"],
            ["purchase_request_details.id", "purchase_request_details.company_id"],
            name="fk_purchase_quotation_request_details_request_detail_company",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "purchase_quotation_request_id",
            "purchase_request_detail_id",
            name="uq_purchase_quotation_request_details_pair",
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_purchase_quotation_request_details_quantity_positive",
        ),
    )
    op.create_index(
        "ix_purchase_quotation_request_details_request_detail",
        "purchase_quotation_request_details",
        ["purchase_request_detail_id"],
    )
    op.create_index(
        "ix_purchase_quotation_request_details_quotation_detail",
        "purchase_quotation_request_details",
        ["purchase_quotation_detail_id"],
    )

    op.create_table(
        "purchase_quotation_details",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_quotation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("discount", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(9, 6), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
        sa.Column("available_quantity", sa.Numeric(18, 6), nullable=True),
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
            ["purchase_quotation_id", "company_id"],
            ["purchase_quotations.id", "purchase_quotations.company_id"],
            name="fk_purchase_quotation_details_quotation_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            name="fk_purchase_quotation_details_product_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            name="fk_purchase_quotation_details_unit_company",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "id",
            "company_id",
            name="uq_purchase_quotation_details_id_company_id",
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_purchase_quotation_details_quantity_positive",
        ),
        sa.CheckConstraint(
            "unit_price >= 0",
            name="ck_purchase_quotation_details_unit_price",
        ),
        sa.CheckConstraint(
            "discount >= 0 AND subtotal >= 0 AND tax_amount >= 0 AND total >= 0",
            name="ck_purchase_quotation_details_amounts_nonnegative",
        ),
        sa.CheckConstraint(
            "tax_rate >= 0 AND tax_rate <= 100",
            name="ck_purchase_quotation_details_tax_rate",
        ),
        sa.CheckConstraint(
            "discount <= subtotal",
            name="ck_purchase_quotation_details_discount_within_subtotal",
        ),
        sa.CheckConstraint(
            "delivery_days IS NULL OR delivery_days >= 0",
            name="ck_purchase_quotation_details_delivery_days",
        ),
        sa.CheckConstraint(
            "available_quantity IS NULL OR "
            "(available_quantity >= 0 AND available_quantity <= quantity)",
            name="ck_purchase_quotation_details_available_quantity",
        ),
    )
    op.create_index(
        "ix_purchase_quotation_details_company_product",
        "purchase_quotation_details",
        ["company_id", "product_id"],
    )

    op.create_foreign_key(
        "fk_purchase_quotation_request_details_quotation_detail_company",
        "purchase_quotation_request_details",
        "purchase_quotation_details",
        ["purchase_quotation_detail_id", "company_id"],
        ["id", "company_id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "purchase_quotation_expenses",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_quotation_id", UUID(as_uuid=True), nullable=False),
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
            ["purchase_quotation_id", "company_id"],
            ["purchase_quotations.id", "purchase_quotations.company_id"],
            name="fk_purchase_quotation_expenses_quotation_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["expense_type_id", "company_id"],
            ["expense_types.id", "expense_types.company_id"],
            name="fk_purchase_quotation_expenses_type_company",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_purchase_quotation_expenses_amount_positive",
        ),
    )
    op.create_index(
        "ix_purchase_quotation_expenses_quotation",
        "purchase_quotation_expenses",
        ["purchase_quotation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("purchase_quotation_expenses")
    op.drop_table("purchase_quotation_request_details")
    op.drop_table("purchase_quotation_details")
    op.drop_table("purchase_quotation_requests")
    op.drop_table("purchase_quotations")
    op.drop_table("expense_types")
    op.drop_constraint(
        "uq_purchase_request_details_id_company_id",
        "purchase_request_details",
        type_="unique",
    )
