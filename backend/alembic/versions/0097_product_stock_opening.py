"""Allow an explicit physical opening entry without rewriting existing records."""

from alembic import op

revision = "0097"
down_revision = "0096"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_inventory_movements_type", "inventory_movements", type_="check")
    op.create_check_constraint(
        "ck_inventory_movements_type",
        "inventory_movements",
        "movement_type IN ('opening','receipt','putaway','transfer','pick','shipment','adjustment_in','adjustment_out','reversal')",
    )


def downgrade() -> None:
    # PostgreSQL will reject a downgrade if opening rows exist; never relabel history.
    op.drop_constraint("ck_inventory_movements_type", "inventory_movements", type_="check")
    op.create_check_constraint(
        "ck_inventory_movements_type",
        "inventory_movements",
        "movement_type IN ('receipt','putaway','transfer','pick','shipment','adjustment_in','adjustment_out','reversal')",
    )
