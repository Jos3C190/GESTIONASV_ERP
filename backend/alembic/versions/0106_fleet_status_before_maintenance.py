"""Remember a vehicle's status while it is in the workshop.

Revision ID: 0106
Revises: 0105
"""

from alembic import op

revision = "0106"
down_revision = "0105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE fleet_vehicles ADD COLUMN status_before_maintenance varchar(16)")


def downgrade() -> None:
    op.execute("ALTER TABLE fleet_vehicles DROP COLUMN status_before_maintenance")
