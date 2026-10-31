"""Keep inventory movement actor identifiers immutable after user removal.

Revision ID: 0078
Revises: 0077
"""

from __future__ import annotations

from alembic import op

revision = "0078"
down_revision = "0077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A SET NULL FK tries to UPDATE the append-only ledger when its user is
    # deleted. Retain the UUID as historical attribution instead.
    op.execute(
        "ALTER TABLE inventory_movements "
        "DROP CONSTRAINT IF EXISTS inventory_movements_posted_by_fkey"
    )


def downgrade() -> None:
    # The ledger may already contain actor UUIDs for users removed while this
    # revision was active. Recreating the FK would either reject those historic
    # rows or require mutating immutable ledger records, so the safe downgrade
    # is intentionally a no-op.
    pass
