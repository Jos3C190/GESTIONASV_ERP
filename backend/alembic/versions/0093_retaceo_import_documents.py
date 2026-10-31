"""Keep manually entered import references with the retaceo version."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0093"
down_revision = "0092"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, column_type in (
        ("origin_country", sa.String(120)),
        ("import_invoice_number", sa.String(80)),
        ("import_invoice_date", sa.Date()),
        ("import_policy_number", sa.String(80)),
        ("import_policy_date", sa.Date()),
    ):
        op.add_column("retaceos", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    connection = op.get_bind()
    populated = connection.scalar(
        sa.text(
            "SELECT count(*) FROM retaceos WHERE origin_country IS NOT NULL "
            "OR import_invoice_number IS NOT NULL OR import_invoice_date IS NOT NULL "
            "OR import_policy_number IS NOT NULL OR import_policy_date IS NOT NULL"
        )
    )
    if populated:
        raise RuntimeError(
            "Hay referencias de importación documentadas; preserve esos datos antes de retirar las columnas."
        )
    for name in (
        "origin_country",
        "import_invoice_number",
        "import_invoice_date",
        "import_policy_number",
        "import_policy_date",
    ):
        op.drop_column("retaceos", name)
