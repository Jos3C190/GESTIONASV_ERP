"""Persist consolidation RFQ versions and separate offered quantities."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_quotations",
        sa.Column("response_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "purchase_quotations",
        sa.Column("consolidation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "purchase_quotations",
        sa.Column("consolidation_code", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "purchase_quotations",
        sa.Column("version_number", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "purchase_quotations",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_purchase_quotations_consolidation_company",
        "purchase_quotations",
        "purchase_consolidations",
        ["consolidation_id", "company_id"],
        ["id", "company_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_purchase_quotations_consolidation_supplier_version",
        "purchase_quotations",
        ["company_id", "consolidation_id", "supplier_id", "version_number"],
    )
    op.create_check_constraint(
        "ck_purchase_quotations_version_positive",
        "purchase_quotations",
        "version_number > 0",
    )
    op.create_check_constraint(
        "ck_purchase_quotations_consolidation_version",
        "purchase_quotations",
        "(consolidation_id IS NULL AND consolidation_code IS NULL AND version_number = 1) OR "
        "(consolidation_id IS NOT NULL AND consolidation_code IS NOT NULL)",
    )
    op.create_index(
        "ix_purchase_quotations_consolidation_supplier",
        "purchase_quotations",
        ["company_id", "consolidation_id", "supplier_id"],
    )

    op.add_column(
        "purchase_quotation_details",
        sa.Column("offered_quantity", sa.Numeric(18, 6), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE purchase_quotation_details AS detail "
            "SET offered_quantity = detail.quantity "
            "FROM purchase_quotations AS quotation "
            "WHERE quotation.id = detail.purchase_quotation_id "
            "AND quotation.company_id = detail.company_id "
            "AND quotation.status IN ('received','under_evaluation','selected','rejected')"
        )
    )
    op.drop_constraint(
        "ck_purchase_quotation_details_available_quantity",
        "purchase_quotation_details",
        type_="check",
    )
    op.create_check_constraint(
        "ck_purchase_quotation_details_available_quantity",
        "purchase_quotation_details",
        "available_quantity IS NULL OR (available_quantity >= 0 AND available_quantity <= "
        "coalesce(offered_quantity, quantity))",
    )
    op.create_check_constraint(
        "ck_purchase_quotation_details_offered_quantity",
        "purchase_quotation_details",
        "offered_quantity IS NULL OR (offered_quantity >= 0 AND offered_quantity <= quantity)",
    )

    op.create_table(
        "purchase_quotation_line_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_quotation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_quotation_detail_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consolidation_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_sku", sa.String(length=80), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("unit_name", sa.String(length=120), nullable=False),
        sa.Column("branch_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("central_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("source_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["purchase_quotation_id", "company_id"],
            ["purchase_quotations.id", "purchase_quotations.company_id"],
            name="fk_purchase_quotation_line_snapshots_quotation_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_quotation_detail_id", "company_id"],
            ["purchase_quotation_details.id", "purchase_quotation_details.company_id"],
            name="fk_purchase_quotation_line_snapshots_detail_company",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "purchase_quotation_detail_id",
            name="uq_purchase_quotation_line_snapshots_detail",
        ),
        sa.CheckConstraint(
            "branch_quantity >= 0 AND central_quantity >= 0",
            name="ck_purchase_quotation_line_snapshots_quantities_nonnegative",
        ),
    )
    op.create_index(
        "ix_purchase_quotation_line_snapshots_quotation",
        "purchase_quotation_line_snapshots",
        ["company_id", "purchase_quotation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_purchase_quotation_line_snapshots_quotation",
        table_name="purchase_quotation_line_snapshots",
    )
    op.drop_table("purchase_quotation_line_snapshots")
    op.drop_constraint(
        "ck_purchase_quotation_details_offered_quantity",
        "purchase_quotation_details",
        type_="check",
    )
    op.drop_constraint(
        "ck_purchase_quotation_details_available_quantity",
        "purchase_quotation_details",
        type_="check",
    )
    op.create_check_constraint(
        "ck_purchase_quotation_details_available_quantity",
        "purchase_quotation_details",
        "available_quantity IS NULL OR (available_quantity >= 0 AND available_quantity <= quantity)",
    )
    op.drop_column("purchase_quotation_details", "offered_quantity")
    op.drop_index("ix_purchase_quotations_consolidation_supplier", table_name="purchase_quotations")
    op.drop_constraint(
        "ck_purchase_quotations_consolidation_version",
        "purchase_quotations",
        type_="check",
    )
    op.drop_constraint(
        "ck_purchase_quotations_version_positive",
        "purchase_quotations",
        type_="check",
    )
    op.drop_constraint(
        "uq_purchase_quotations_consolidation_supplier_version",
        "purchase_quotations",
        type_="unique",
    )
    op.drop_constraint(
        "fk_purchase_quotations_consolidation_company",
        "purchase_quotations",
        type_="foreignkey",
    )
    op.drop_column("purchase_quotations", "sent_at")
    op.drop_column("purchase_quotations", "version_number")
    op.drop_column("purchase_quotations", "consolidation_code")
    op.drop_column("purchase_quotations", "consolidation_id")
    op.drop_column("purchase_quotations", "response_notes")
