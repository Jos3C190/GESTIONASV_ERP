"""Require a closed retaceo for new receipts; preserve historical workflow."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0092"
down_revision = "0091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchases",
        sa.Column(
            "inventory_workflow",
            sa.String(32),
            nullable=False,
            server_default="receipt_before_retaceo",
        ),
    )
    # Existing rows keep their policy, including pending documents and receipts.
    op.alter_column("purchases", "inventory_workflow", server_default="retaceo_before_inventory")
    op.create_check_constraint(
        "ck_purchase_inventory_workflow",
        "purchases",
        "inventory_workflow IN ('receipt_before_retaceo', 'retaceo_before_inventory')",
    )


def downgrade() -> None:
    # Removing the policy while new documents exist would silently change their
    # accounting workflow. Require an explicit data migration instead.
    connection = op.get_bind()
    count = connection.scalar(
        sa.text(
            "SELECT count(*) FROM purchases WHERE inventory_workflow = 'retaceo_before_inventory'"
        )
    )
    if count:
        raise RuntimeError("Existen compras con el flujo nuevo; no se puede retirar su política.")
    op.drop_constraint("ck_purchase_inventory_workflow", "purchases", type_="check")
    op.drop_column("purchases", "inventory_workflow")
