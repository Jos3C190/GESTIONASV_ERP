"""Manual retaceo entry and actual expenses separate from order budgets."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0095"
down_revision = "0094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing records keep their accounting policy and amounts.
    op.add_column(
        "retaceos",
        sa.Column("manual_entry", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("retaceo_costs", sa.Column("incurred_on", sa.Date(), nullable=True))
    op.add_column(
        "purchase_order_expenses",
        sa.Column("is_actual", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("purchase_order_expenses", sa.Column("incurred_on", sa.Date(), nullable=True))
    op.add_column("purchase_order_expenses", sa.Column("reference", sa.String(240), nullable=True))
    op.create_check_constraint(
        "ck_order_actual_expense_documented",
        "purchase_order_expenses",
        "NOT is_actual OR (incurred_on IS NOT NULL AND description IS NOT NULL AND reference IS NOT NULL AND length(trim(description)) > 0 AND length(trim(reference)) > 0)",
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM retaceos WHERE manual_entry) OR EXISTS (SELECT 1 FROM purchase_order_expenses WHERE is_actual)"
        )
    ):
        raise RuntimeError(
            "Existen retaceos manuales o gastos reales; conserve su política y trazabilidad."
        )
    op.drop_constraint(
        "ck_order_actual_expense_documented", "purchase_order_expenses", type_="check"
    )
    op.drop_column("purchase_order_expenses", "reference")
    op.drop_column("purchase_order_expenses", "incurred_on")
    op.drop_column("purchase_order_expenses", "is_actual")
    op.drop_column("retaceo_costs", "incurred_on")
    op.drop_column("retaceos", "manual_entry")
