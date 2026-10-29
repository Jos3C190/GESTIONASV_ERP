"""Link screened document assets to supplier quotation responses."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_quotation_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_quotation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=160), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["purchase_quotation_id", "company_id"],
            ["purchase_quotations.id", "purchase_quotations.company_id"],
            name="fk_purchase_quotation_documents_quotation_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "company_id"],
            ["document_assets.id", "document_assets.company_id"],
            name="fk_purchase_quotation_documents_asset_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], name="fk_purchase_quotation_documents_company",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_purchase_quotation_documents_document"),
    )
    op.create_index(
        "ix_purchase_quotation_documents_quotation",
        "purchase_quotation_documents",
        ["company_id", "purchase_quotation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_purchase_quotation_documents_quotation",
        table_name="purchase_quotation_documents",
    )
    op.drop_table("purchase_quotation_documents")
