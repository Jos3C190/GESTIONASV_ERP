"""Add the closed state to purchase consolidations."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_purchase_consolidations_status",
        "purchase_consolidations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_purchase_consolidations_status",
        "purchase_consolidations",
        "status IN ('draft','frozen','closed','cancelled')",
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE purchase_consolidations SET status = 'frozen' WHERE status = 'closed'"
        )
    )
    op.drop_constraint(
        "ck_purchase_consolidations_status",
        "purchase_consolidations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_purchase_consolidations_status",
        "purchase_consolidations",
        "status IN ('draft','frozen','cancelled')",
    )
