"""Allow safely detaching original supplier quotation documents.

Revision ID: 0068
Revises: 0067
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_quotation_documents",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_purchase_quotation_documents_active",
        "purchase_quotation_documents",
        ["company_id", "purchase_quotation_id", "deleted_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_purchase_quotation_documents_active",
        table_name="purchase_quotation_documents",
    )
    op.drop_column("purchase_quotation_documents", "deleted_at")
