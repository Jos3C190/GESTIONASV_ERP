"""Record immutable, idempotent inventory label print runs.

Revision ID: 0081
Revises: 0080
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_label_prints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_lot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_lot_detail_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("handling_unit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("quantity_printed", sa.Integer(), nullable=False),
        sa.Column("print_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("label_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("printed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "printed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_inventory_label_prints_company_id"),
        sa.UniqueConstraint(
            "company_id", "idempotency_key", name="uq_inventory_label_prints_idempotency"
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            name="fk_inventory_label_prints_item_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_lot_id"],
            ["inventory_lots.company_id", "inventory_lots.id"],
            name="fk_inventory_label_prints_lot_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_lot_detail_id"],
            ["inventory_lot_details.company_id", "inventory_lot_details.id"],
            name="fk_inventory_label_prints_detail_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "handling_unit_id"],
            ["inventory_handling_units.company_id", "inventory_handling_units.id"],
            name="fk_inventory_label_prints_unit_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["printed_by"],
            ["users.id"],
            name="fk_inventory_label_prints_actor",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("quantity_printed > 0", name="ck_inventory_label_prints_quantity"),
        sa.CheckConstraint(
            "reason IN ('initial','reprint')", name="ck_inventory_label_prints_reason"
        ),
        sa.CheckConstraint(
            "(inventory_lot_detail_id IS NOT NULL) <> (handling_unit_id IS NOT NULL)",
            name="ck_inventory_label_prints_target",
        ),
    )
    op.create_index(
        "ix_inventory_label_prints_lot_date",
        "inventory_label_prints",
        ["company_id", "inventory_lot_id", "print_date"],
    )
    op.create_index(
        "ix_inventory_label_prints_unit_date",
        "inventory_label_prints",
        ["company_id", "handling_unit_id", "print_date"],
    )
    op.execute(
        """
        CREATE FUNCTION guard_inventory_label_print_history() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Inventory label print history is immutable';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER immutable_inventory_label_prints
        BEFORE UPDATE OR DELETE ON inventory_label_prints
        FOR EACH ROW EXECUTE FUNCTION guard_inventory_label_print_history();
        """
    )


def downgrade() -> None:
    raise RuntimeError("0081 conserva historial de impresión; requiere reversión documentada.")
