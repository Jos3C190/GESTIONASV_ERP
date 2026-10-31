"""Store manually classified branch demand on consolidation sources."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_consolidation_sources",
        sa.Column("demand_level", sa.String(length=16), nullable=True),
    )
    op.create_check_constraint(
        "ck_purchase_consolidation_source_demand_level",
        "purchase_consolidation_sources",
        "demand_level IS NULL OR demand_level IN ('low','medium','high')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_purchase_consolidation_source_demand_level",
        "purchase_consolidation_sources",
        type_="check",
    )
    op.drop_column("purchase_consolidation_sources", "demand_level")
