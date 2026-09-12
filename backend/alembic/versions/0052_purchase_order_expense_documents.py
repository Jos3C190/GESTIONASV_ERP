"""Link purchase-order expense documents to the canonical document store."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_document_assets_id_company_id",
        "document_assets",
        ["id", "company_id"],
    )

    op.create_table(
        "purchase_order_expense_documents",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_order_expense_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(160), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
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
            name="fk_purchase_order_expense_documents_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_expense_id", "company_id"],
            ["purchase_order_expenses.id", "purchase_order_expenses.company_id"],
            name="fk_purchase_order_expense_documents_expense_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "company_id"],
            ["document_assets.id", "document_assets.company_id"],
            name="fk_purchase_order_expense_documents_document_company",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "document_id",
            name="uq_purchase_order_expense_documents_document",
        ),
    )
    op.create_index(
        "ix_purchase_order_expense_documents_expense",
        "purchase_order_expense_documents",
        ["purchase_order_expense_id", "created_at"],
    )
    op.create_index(
        "ix_purchase_order_expense_documents_company",
        "purchase_order_expense_documents",
        ["company_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("purchase_order_expense_documents")
    op.drop_constraint(
        "uq_document_assets_id_company_id",
        "document_assets",
        type_="unique",
    )
