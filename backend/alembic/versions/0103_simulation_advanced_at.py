"""When the simulator last advanced a session, so maps can replay its motion in time."""

from alembic import op

revision = "0103"
down_revision = "0102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tracking_simulations
          ADD COLUMN advanced_at timestamptz NOT NULL DEFAULT now();
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE tracking_simulations DROP COLUMN advanced_at;")
