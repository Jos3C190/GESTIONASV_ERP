"""Persist itemized retaceo costs, manual allocations and evidence links."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retaceo_costs",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("retaceo_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_purchase_order_expense_id", UUID(as_uuid=True), nullable=True),
        sa.Column("expense_type_id", UUID(as_uuid=True), nullable=True),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["retaceo_id", "company_id"],
            ["retaceos.id", "retaceos.company_id"],
            name="fk_retaceo_costs_retaceo_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_purchase_order_expense_id", "company_id"],
            ["purchase_order_expenses.id", "purchase_order_expenses.company_id"],
            name="fk_retaceo_costs_source_expense_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["expense_type_id", "company_id"],
            ["expense_types.id", "expense_types.company_id"],
            name="fk_retaceo_costs_expense_type_company",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "company_id", name="uq_retaceo_costs_id_company"),
        sa.CheckConstraint(
            "classification IN ('freight','expense','dai','import_vat')",
            name="ck_retaceo_costs_classification",
        ),
        sa.CheckConstraint("amount > 0", name="ck_retaceo_costs_amount_positive"),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_retaceo_costs_title_nonempty"),
    )
    op.create_index(
        "ix_retaceo_costs_retaceo_created", "retaceo_costs", ["retaceo_id", "created_at"]
    )
    op.create_index(
        "uq_retaceo_costs_source_expense",
        "retaceo_costs",
        ["retaceo_id", "source_purchase_order_expense_id"],
        unique=True,
        postgresql_where=sa.text("source_purchase_order_expense_id IS NOT NULL"),
    )

    op.create_table(
        "retaceo_cost_allocations",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("retaceo_cost_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_detail_id", UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["retaceo_cost_id", "company_id"],
            ["retaceo_costs.id", "retaceo_costs.company_id"],
            name="fk_retaceo_cost_allocations_cost_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_detail_id", "company_id"],
            ["purchase_details.id", "purchase_details.company_id"],
            name="fk_retaceo_cost_allocations_purchase_detail_company",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_retaceo_cost_allocations_amount_nonnegative"),
        sa.UniqueConstraint(
            "retaceo_cost_id",
            "purchase_detail_id",
            name="uq_retaceo_cost_allocations_cost_detail",
        ),
    )
    op.create_index(
        "ix_retaceo_cost_allocations_detail",
        "retaceo_cost_allocations",
        ["company_id", "purchase_detail_id"],
    )

    op.create_table(
        "retaceo_cost_documents",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("retaceo_cost_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(160), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["retaceo_cost_id", "company_id"],
            ["retaceo_costs.id", "retaceo_costs.company_id"],
            name="fk_retaceo_cost_documents_cost_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "company_id"],
            ["document_assets.id", "document_assets.company_id"],
            name="fk_retaceo_cost_documents_asset_company",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "retaceo_cost_id", "document_id", name="uq_retaceo_cost_documents_asset"
        ),
    )
    op.create_index(
        "ix_retaceo_cost_documents_cost",
        "retaceo_cost_documents",
        ["company_id", "retaceo_cost_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_retaceo_cost_documents_cost", table_name="retaceo_cost_documents")
    op.drop_table("retaceo_cost_documents")
    op.drop_index("ix_retaceo_cost_allocations_detail", table_name="retaceo_cost_allocations")
    op.drop_table("retaceo_cost_allocations")
    op.drop_index("uq_retaceo_costs_source_expense", table_name="retaceo_costs")
    op.drop_index("ix_retaceo_costs_retaceo_created", table_name="retaceo_costs")
    op.drop_table("retaceo_costs")
