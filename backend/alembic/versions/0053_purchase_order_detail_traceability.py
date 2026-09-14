"""Persist purchase-quotation detail traceability on purchase-order details."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    legacy_count = op.get_bind().execute(
        sa.text("SELECT count(*) FROM purchase_order_details")
    ).scalar_one()
    if legacy_count:
        raise RuntimeError(
            "Migration 0053 cannot infer purchase_quotation_detail_id for existing "
            "purchase_order_details. Remove or explicitly remediate legacy purchase-order "
            "data before retrying; heuristic matching is intentionally unsupported."
        )

    op.add_column(
        "purchase_order_details",
        sa.Column(
            "purchase_quotation_detail_id",
            UUID(as_uuid=True),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_purchase_order_details_quotation_detail_company",
        "purchase_order_details",
        "purchase_quotation_details",
        ["purchase_quotation_detail_id", "company_id"],
        ["id", "company_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_purchase_order_details_company_quotation_detail",
        "purchase_order_details",
        ["company_id", "purchase_quotation_detail_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_purchase_order_details_company_quotation_detail",
        table_name="purchase_order_details",
    )
    op.drop_constraint(
        "fk_purchase_order_details_quotation_detail_company",
        "purchase_order_details",
        type_="foreignkey",
    )
    op.drop_column(
        "purchase_order_details",
        "purchase_quotation_detail_id",
    )
