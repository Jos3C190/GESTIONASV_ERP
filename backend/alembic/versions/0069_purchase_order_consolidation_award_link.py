"""Link purchase-order details to their consolidation award."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_order_details",
        sa.Column("purchase_consolidation_award_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_purchase_order_details_consolidation_award_company",
        "purchase_order_details",
        "purchase_consolidation_awards",
        ["purchase_consolidation_award_id", "company_id"],
        ["id", "company_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_purchase_order_details_company_award",
        "purchase_order_details",
        ["company_id", "purchase_consolidation_award_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_purchase_order_details_company_award",
        table_name="purchase_order_details",
    )
    op.drop_constraint(
        "fk_purchase_order_details_consolidation_award_company",
        "purchase_order_details",
        type_="foreignkey",
    )
    op.drop_column("purchase_order_details", "purchase_consolidation_award_id")
