"""Persist the selected retaceo calculation mode and entered tax rates."""

import sqlalchemy as sa
from alembic import op

revision = "0098"
down_revision = "0097"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "retaceos",
        sa.Column("calculation_mode", sa.String(16), nullable=False, server_default="manual"),
    )
    op.add_column("retaceos", sa.Column("dai_rate", sa.Numeric(10, 6), nullable=True))
    op.add_column("retaceos", sa.Column("vat_rate", sa.Numeric(10, 6), nullable=True))
    op.create_check_constraint(
        "ck_retaceos_calculation_mode", "retaceos", "calculation_mode IN ('automatic', 'manual')"
    )
    op.create_check_constraint(
        "ck_retaceos_calculation_rates",
        "retaceos",
        "(calculation_mode = 'manual' AND dai_rate IS NULL AND vat_rate IS NULL) OR (calculation_mode = 'automatic' AND dai_rate IS NOT NULL AND vat_rate IS NOT NULL AND dai_rate BETWEEN 0 AND 1000 AND vat_rate BETWEEN 0 AND 1000)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_retaceos_calculation_rates", "retaceos", type_="check")
    op.drop_constraint("ck_retaceos_calculation_mode", "retaceos", type_="check")
    op.drop_column("retaceos", "vat_rate")
    op.drop_column("retaceos", "dai_rate")
    op.drop_column("retaceos", "calculation_mode")
