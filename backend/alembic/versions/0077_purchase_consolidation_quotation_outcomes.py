"""Record final supplier quotation outcomes when closing a consolidation."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_purchase_quotations_status",
        "purchase_quotations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_purchase_quotations_status",
        "purchase_quotations",
        "status IN ('draft','requested','received','under_evaluation','selected',"
        "'not_selected','rejected','expired','cancelled')",
    )
    op.execute(
        sa.text(
            "UPDATE purchase_quotations AS quotation "
            "SET status = CASE WHEN EXISTS ("
            "SELECT 1 FROM purchase_consolidation_awards AS award "
            "WHERE award.company_id = quotation.company_id "
            "AND award.purchase_quotation_id = quotation.id "
            "AND award.revoked_at IS NULL"
            ") THEN 'selected' ELSE 'not_selected' END "
            "FROM purchase_consolidations AS consolidation "
            "WHERE consolidation.id = quotation.consolidation_id "
            "AND consolidation.company_id = quotation.company_id "
            "AND consolidation.status = 'closed' "
            "AND quotation.status IN ('requested','received','under_evaluation')"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE purchase_quotations AS quotation "
            "SET status = 'under_evaluation' "
            "FROM purchase_consolidations AS consolidation "
            "WHERE consolidation.id = quotation.consolidation_id "
            "AND consolidation.company_id = quotation.company_id "
            "AND consolidation.status = 'closed' "
            "AND quotation.status IN ('selected','not_selected')"
        )
    )
    op.drop_constraint(
        "ck_purchase_quotations_status",
        "purchase_quotations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_purchase_quotations_status",
        "purchase_quotations",
        "status IN ('draft','requested','received','under_evaluation','selected','rejected',"
        "'expired','cancelled')",
    )
