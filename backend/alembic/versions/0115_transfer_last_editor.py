"""Remember who last edited a transfer so they cannot also approve it.

Revision ID: 0115
Revises: 0114
"""

from alembic import op

revision = "0115"
down_revision = "0114"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE inventory_transfers
            ADD COLUMN last_edited_by_id uuid,
            ADD CONSTRAINT fk_inventory_transfers_last_edited_by
                FOREIGN KEY (last_edited_by_id) REFERENCES users (id) ON DELETE RESTRICT
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE inventory_transfers
            DROP CONSTRAINT fk_inventory_transfers_last_edited_by,
            DROP COLUMN last_edited_by_id
    """)
