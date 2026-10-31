"""Add canonical identity to received product lines and movement history."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0085"
down_revision = "0084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_lot_details",
        sa.Column("code", sa.String(length=120), nullable=True),
    )
    op.execute(
        """
        UPDATE inventory_lot_details AS detail
        SET code = lot.code || '-D' || upper(replace(detail.id::text, '-', ''))
        FROM inventory_lots AS lot
        WHERE lot.company_id = detail.company_id
          AND lot.id = detail.inventory_lot_id
        """
    )
    op.alter_column("inventory_lot_details", "code", nullable=False)
    op.create_unique_constraint(
        "uq_inventory_lot_details_company_code",
        "inventory_lot_details",
        ["company_id", "code"],
    )
    op.create_check_constraint(
        "ck_inventory_lot_details_code",
        "inventory_lot_details",
        "char_length(code) BETWEEN 3 AND 120",
    )
    op.add_column(
        "inventory_movement_lines",
        sa.Column("inventory_lot_detail_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Movement lines are an append-only ledger protected by a database trigger.
    # Leave historical rows untouched. Readers resolve their exact historical
    # detail through the line's handling_unit_id; new writes persist this FK.
    op.create_foreign_key(
        "fk_inventory_movement_lines_lot_detail_company",
        "inventory_movement_lines",
        "inventory_lot_details",
        ["company_id", "inventory_lot_detail_id"],
        ["company_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_inventory_movement_lines_lot_detail",
        "inventory_movement_lines",
        ["company_id", "inventory_lot_detail_id"],
        postgresql_where=sa.text("inventory_lot_detail_id IS NOT NULL"),
    )


def downgrade() -> None:
    # This removes canonical identifiers and movement-to-detail links created
    # after 0085. It exists for disposable migration-test databases and
    # deliberate operator-managed rollbacks only. Never use it as an automatic
    # recovery path for a live/demo database; restore its validated backup.
    op.drop_index("ix_inventory_movement_lines_lot_detail", table_name="inventory_movement_lines")
    op.drop_constraint(
        "fk_inventory_movement_lines_lot_detail_company",
        "inventory_movement_lines",
        type_="foreignkey",
    )
    op.drop_column("inventory_movement_lines", "inventory_lot_detail_id")
    op.drop_constraint(
        "ck_inventory_lot_details_code", "inventory_lot_details", type_="check"
    )
    op.drop_constraint(
        "uq_inventory_lot_details_company_code", "inventory_lot_details", type_="unique"
    )
    op.drop_column("inventory_lot_details", "code")
