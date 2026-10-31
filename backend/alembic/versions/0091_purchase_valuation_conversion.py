"""Keep a documented valuation conversion without changing purchase currency."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0091"
down_revision = "0090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("purchases", sa.Column("valuation_conversion", JSONB(), nullable=True))
    op.create_check_constraint(
        "ck_purchase_valuation_conversion",
        "purchases",
        "valuation_conversion IS NULL OR ("
        "jsonb_typeof(valuation_conversion) = 'object' AND "
        "valuation_conversion ?& ARRAY['currency','rate','effective_date','reference'] AND "
        "(valuation_conversion->>'currency') ~ '^[A-Z]{3}$' AND "
        "(valuation_conversion->>'rate')::numeric > 0 AND "
        "char_length(btrim(valuation_conversion->>'reference')) BETWEEN 3 AND 500)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_purchase_valuation_conversion", "purchases", type_="check")
    op.drop_column("purchases", "valuation_conversion")
