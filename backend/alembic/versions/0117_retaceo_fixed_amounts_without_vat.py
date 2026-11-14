"""Retaceo with fixed amounts and without import VAT.

Revision ID: 0117
Revises: 0116

The landed cost is FOB (from the purchase invoice) + freight and insurance + DAI +
additional expenses, with every amount distributed by FOB on the server. Import VAT is
recoverable tax, not inventory cost, so it is removed from the retaceo together with the
automatic mode (percentages) that only existed to compute it.

Upgrade deletes the stored VAT cost lines. Their allocations and document links go away by
cascade; the uploaded files (``document_assets``) are kept. This data is test data, so the
downgrade only restores the columns and the four-value classification: the deleted VAT
amounts, rates and modes are gone for good.
"""

import sqlalchemy as sa
from alembic import op

revision = "0117"
down_revision = "0116"
branch_labels = None
depends_on = None

_AMOUNTS_BEFORE = (
    "total_freight >= 0 AND total_expenses >= 0 AND total_dai >= 0 "
    "AND import_vat >= 0 AND total_cost >= 0"
)
_AMOUNTS_AFTER = "total_freight >= 0 AND total_expenses >= 0 AND total_dai >= 0 AND total_cost >= 0"
_RATES_CHECK = (
    "(calculation_mode = 'manual' AND dai_rate IS NULL AND vat_rate IS NULL) OR "
    "(calculation_mode = 'automatic' AND dai_rate IS NOT NULL AND vat_rate IS NOT NULL "
    "AND dai_rate BETWEEN 0 AND 1000 AND vat_rate BETWEEN 0 AND 1000)"
)


def upgrade() -> None:
    op.execute("DELETE FROM retaceo_costs WHERE classification = 'import_vat'")
    op.drop_constraint("ck_retaceo_costs_classification", "retaceo_costs", type_="check")
    op.create_check_constraint(
        "ck_retaceo_costs_classification",
        "retaceo_costs",
        "classification IN ('freight','expense','dai')",
    )
    op.drop_constraint("ck_retaceos_calculation_rates", "retaceos", type_="check")
    op.drop_constraint("ck_retaceos_calculation_mode", "retaceos", type_="check")
    op.drop_constraint("ck_retaceos_amounts_nonnegative", "retaceos", type_="check")
    op.create_check_constraint("ck_retaceos_amounts_nonnegative", "retaceos", _AMOUNTS_AFTER)
    op.drop_column("retaceos", "import_vat")
    op.drop_column("retaceos", "vat_rate")
    op.drop_column("retaceos", "dai_rate")
    op.drop_column("retaceos", "calculation_mode")


def downgrade() -> None:
    op.add_column(
        "retaceos",
        sa.Column("calculation_mode", sa.String(16), nullable=False, server_default="manual"),
    )
    op.add_column("retaceos", sa.Column("dai_rate", sa.Numeric(10, 6), nullable=True))
    op.add_column("retaceos", sa.Column("vat_rate", sa.Numeric(10, 6), nullable=True))
    op.add_column(
        "retaceos",
        sa.Column("import_vat", sa.Numeric(18, 6), nullable=False, server_default="0"),
    )
    op.drop_constraint("ck_retaceos_amounts_nonnegative", "retaceos", type_="check")
    op.create_check_constraint("ck_retaceos_amounts_nonnegative", "retaceos", _AMOUNTS_BEFORE)
    op.create_check_constraint(
        "ck_retaceos_calculation_mode", "retaceos", "calculation_mode IN ('automatic', 'manual')"
    )
    op.create_check_constraint("ck_retaceos_calculation_rates", "retaceos", _RATES_CHECK)
    op.drop_constraint("ck_retaceo_costs_classification", "retaceo_costs", type_="check")
    op.create_check_constraint(
        "ck_retaceo_costs_classification",
        "retaceo_costs",
        "classification IN ('freight','expense','dai','import_vat')",
    )
