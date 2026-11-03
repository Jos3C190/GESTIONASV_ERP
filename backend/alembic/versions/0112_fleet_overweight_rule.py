"""Stopping a dispatch over capacity is each company's choice, off by default.

Revision ID: 0112
Revises: 0111
"""

from alembic import op
from sqlalchemy import text

revision = "0112"
down_revision = "0111"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE fleet_settings ADD COLUMN block_overweight boolean NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    blocked = (
        op.get_bind()
        .execute(text("SELECT count(*) FROM fleet_settings WHERE block_overweight"))
        .scalar()
    )
    if blocked:
        raise RuntimeError(f"Hay {blocked} empresas con esta regla encendida.")
    op.execute("ALTER TABLE fleet_settings DROP COLUMN block_overweight")
