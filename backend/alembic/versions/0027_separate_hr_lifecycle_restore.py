"""Restrict administrative trash restore to administrator roles.

Revision ID: 0027
Revises: 0026
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

RESTORE_CODES = ("employees:restore", "departments:restore")


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM role_permissions rp "
            "USING roles r, permissions p "
            "WHERE rp.role_id = r.id AND rp.permission_id = p.id "
            "AND r.name = 'RECURSOS_HUMANOS' "
            "AND r.company_id IS NULL "
            "AND p.code = ANY(:codes)"
        ),
        {"codes": list(RESTORE_CODES)},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id, created_at) "
            "SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p "
            "WHERE r.name = 'RECURSOS_HUMANOS' "
            "AND r.company_id IS NULL "
            "AND p.code = ANY(:codes) "
            "ON CONFLICT DO NOTHING"
        ),
        {"codes": list(RESTORE_CODES)},
    )
