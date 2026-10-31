"""Link verified purchase receipts to idempotent inventory movements."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchases",
        sa.Column("inventory_movement_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_purchases_inventory_movement_company",
        "purchases",
        "inventory_movements",
        ["company_id", "inventory_movement_id"],
        ["company_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_purchases_inventory_movement",
        "purchases",
        ["company_id", "inventory_movement_id"],
    )

    op.add_column(
        "purchase_details",
        sa.Column("quantity_accepted", sa.Numeric(18, 6), nullable=True),
    )
    op.add_column(
        "purchase_details",
        sa.Column("inventory_location_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_purchase_details_inventory_location",
        "purchase_details",
        "locations",
        ["inventory_location_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_purchase_details_accepted_within_counted",
        "purchase_details",
        "quantity_accepted IS NULL OR "
        "(quantity_accepted >= 0 AND quantity_accepted <= quantity_received)",
    )
    op.create_check_constraint(
        "ck_purchase_details_accepted_location_required",
        "purchase_details",
        "quantity_accepted IS NULL OR "
        "(quantity_accepted = 0 AND inventory_location_id IS NULL) OR "
        "(quantity_accepted > 0 AND inventory_location_id IS NOT NULL)",
    )

    # Historical verified receipts keep accepted quantity/location unknown. No
    # inventory movement is fabricated during this schema-only migration.


def downgrade() -> None:
    op.drop_constraint(
        "ck_purchase_details_accepted_location_required", "purchase_details", type_="check"
    )
    op.drop_constraint(
        "ck_purchase_details_accepted_within_counted", "purchase_details", type_="check"
    )
    op.drop_constraint(
        "fk_purchase_details_inventory_location", "purchase_details", type_="foreignkey"
    )
    op.drop_column("purchase_details", "inventory_location_id")
    op.drop_column("purchase_details", "quantity_accepted")

    op.drop_constraint("uq_purchases_inventory_movement", "purchases", type_="unique")
    op.drop_constraint(
        "fk_purchases_inventory_movement_company", "purchases", type_="foreignkey"
    )
    op.drop_column("purchases", "inventory_movement_id")
