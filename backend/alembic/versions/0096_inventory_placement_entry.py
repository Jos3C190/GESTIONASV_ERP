"""Stage new receipts and post stock only when physical placement is confirmed."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0096"
down_revision = "0095"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_purchase_inventory_workflow", "purchases", type_="check")
    op.create_check_constraint(
        "ck_purchase_inventory_workflow",
        "purchases",
        "inventory_workflow IN ('receipt_before_retaceo', 'retaceo_before_inventory', 'placement_before_inventory')",
    )
    op.alter_column("purchases", "inventory_workflow", server_default="placement_before_inventory")
    # Continue untouched pre-inventory receipts with the new sequence. Never
    # reinterpret receipts that already have a lot or an inventory movement.
    op.execute("""
        UPDATE purchases AS p SET inventory_workflow = 'placement_before_inventory'
        WHERE p.inventory_workflow = 'retaceo_before_inventory'
          AND p.status IN ('draft', 'received') AND p.inventory_movement_id IS NULL
          AND NOT EXISTS (SELECT 1 FROM inventory_lots AS l
                          WHERE l.company_id = p.company_id AND l.purchase_id = p.id)
    """)
    op.add_column(
        "inventory_handling_units", sa.Column("inventory_posted_at", sa.DateTime(timezone=True))
    )
    op.execute("UPDATE inventory_handling_units SET inventory_posted_at = created_at")
    op.alter_column("inventory_handling_units", "inventory_posted_at", server_default=sa.func.now())
    op.create_index(
        "ix_handling_units_pending_entry",
        "inventory_handling_units",
        ["company_id", "warehouse_id"],
        postgresql_where=sa.text("inventory_posted_at IS NULL AND closed_at IS NULL"),
    )
    op.add_column("inventory_lot_details", sa.Column("entry_value", sa.Numeric(24, 6)))
    op.add_column("inventory_lot_details", sa.Column("entry_currency", sa.String(3)))
    op.create_check_constraint(
        "ck_lot_entry_value",
        "inventory_lot_details",
        "(entry_value IS NULL AND entry_currency IS NULL) OR (entry_value IS NOT NULL AND entry_value >= 0 AND entry_currency IS NOT NULL)",
    )
    op.create_table(
        "inventory_preparation_actions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handling_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_preparation_action_key"),
        sa.ForeignKeyConstraint(
            ["company_id", "handling_unit_id"],
            ["inventory_handling_units.company_id", "inventory_handling_units.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("action IN ('split','place')", name="ck_preparation_action"),
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM purchases WHERE inventory_workflow = 'placement_before_inventory') OR EXISTS (SELECT 1 FROM inventory_preparation_actions)"
        )
    ):
        raise RuntimeError("Hay recepciones del flujo de ubicación; conserve su historial.")
    op.drop_table("inventory_preparation_actions")
    op.drop_constraint("ck_lot_entry_value", "inventory_lot_details", type_="check")
    op.drop_column("inventory_lot_details", "entry_currency")
    op.drop_column("inventory_lot_details", "entry_value")
    op.drop_index("ix_handling_units_pending_entry", table_name="inventory_handling_units")
    op.drop_column("inventory_handling_units", "inventory_posted_at")
    op.drop_constraint("ck_purchase_inventory_workflow", "purchases", type_="check")
    op.create_check_constraint(
        "ck_purchase_inventory_workflow",
        "purchases",
        "inventory_workflow IN ('receipt_before_retaceo', 'retaceo_before_inventory')",
    )
    op.alter_column("purchases", "inventory_workflow", server_default="retaceo_before_inventory")
