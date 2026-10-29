"""Allow company-level purchase orders and receipts for the mother warehouse."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("purchase_orders", "purchases", "retaceos"):
        op.alter_column(table, "branch_id", nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    tables = ("purchase_orders", "purchases", "retaceos")
    tables_with_unassigned = [
        table
        for table in tables
        if bind.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table} WHERE branch_id IS NULL)"))
    ]
    if tables_with_unassigned:
        names = ", ".join(tables_with_unassigned)
        raise RuntimeError(
            "No se puede revertir 0074 mientras existan órdenes o recepciones sin sucursal "
            f"en: {names}."
        )

    for table in reversed(tables):
        op.alter_column(table, "branch_id", nullable=False)
