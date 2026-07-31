"""Preserve audit actor identifiers when users are removed.

Revision ID: 0008
Revises: 0007
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A SET NULL cascade would mutate historical rows and conflict with the
    # append-only guarantee. Audit actor UUIDs intentionally outlive users.
    op.drop_constraint("fk_audit_logs_user", "audit_logs", type_="foreignkey")


def downgrade() -> None:
    op.create_foreign_key(
        "fk_audit_logs_user",
        "audit_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
