"""Link inventory packaging conversions to company units."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_packaging_definitions",
        sa.Column("packaging_unit_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_inventory_packaging_unit_company",
        "inventory_packaging_definitions",
        "company_units",
        ["company_id", "packaging_unit_id"],
        ["company_id", "unit_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_inventory_packaging_current_unit",
        "inventory_packaging_definitions",
        ["company_id", "inventory_item_id", "packaging_unit_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_current AND is_active AND packaging_unit_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_inventory_packaging_current_unit",
        table_name="inventory_packaging_definitions",
    )
    op.drop_constraint(
        "fk_inventory_packaging_unit_company",
        "inventory_packaging_definitions",
        type_="foreignkey",
    )
    op.drop_column("inventory_packaging_definitions", "packaging_unit_id")
