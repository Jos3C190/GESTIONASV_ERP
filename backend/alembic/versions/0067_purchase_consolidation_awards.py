"""Persist human purchase awards per consolidated product and quantity."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_consolidation_awards",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consolidation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consolidation_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_quotation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_quotation_detail_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name="fk_purchase_consolidation_awards_company", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["consolidation_id", "company_id"],
            ["purchase_consolidations.id", "purchase_consolidations.company_id"],
            name="fk_purchase_consolidation_awards_header_company", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["consolidation_line_id", "company_id"],
            ["purchase_consolidation_lines.id", "purchase_consolidation_lines.company_id"],
            name="fk_purchase_consolidation_awards_line_company", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_quotation_id", "company_id"],
            ["purchase_quotations.id", "purchase_quotations.company_id"],
            name="fk_purchase_consolidation_awards_quotation_company", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_quotation_detail_id", "company_id"],
            ["purchase_quotation_details.id", "purchase_quotation_details.company_id"],
            name="fk_purchase_consolidation_awards_quotation_detail_company", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "supplier_id"], ["suppliers.company_id", "suppliers.id_supplier"],
            name="fk_purchase_consolidation_awards_supplier_company", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"], ["users.id"],
            name="fk_purchase_consolidation_awards_decided_by", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_id"], ["users.id"],
            name="fk_purchase_consolidation_awards_revoked_by", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "company_id", name="uq_purchase_consolidation_awards_id_company"),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_consolidation_awards_quantity_positive"),
        sa.CheckConstraint("length(trim(reason)) > 0", name="ck_purchase_consolidation_awards_reason_required"),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_id IS NULL AND revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by_id IS NOT NULL "
            "AND length(trim(coalesce(revocation_reason, ''))) > 0)",
            name="ck_purchase_consolidation_awards_revocation_complete",
        ),
    )
    op.create_index(
        "ix_purchase_consolidation_awards_line_active",
        "purchase_consolidation_awards",
        ["company_id", "consolidation_id", "consolidation_line_id", "revoked_at"],
    )
    op.create_index(
        "ix_purchase_consolidation_awards_quote_detail",
        "purchase_consolidation_awards",
        ["company_id", "purchase_quotation_detail_id", "revoked_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_purchase_consolidation_awards_quote_detail",
        table_name="purchase_consolidation_awards",
    )
    op.drop_index(
        "ix_purchase_consolidation_awards_line_active",
        table_name="purchase_consolidation_awards",
    )
    op.drop_table("purchase_consolidation_awards")
