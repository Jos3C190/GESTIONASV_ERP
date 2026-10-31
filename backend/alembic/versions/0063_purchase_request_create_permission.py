"""Add least-privilege permission for creating purchase requests."""

from __future__ import annotations

from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO permissions (id, code, description, module, created_at) "
        "VALUES (gen_random_uuid(), 'purchase_requests:create', "
        "'Crear, editar y enviar solicitudes propias', 'purchase_requests', now()) "
        "ON CONFLICT DO NOTHING"
    )
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id, created_at) "
        "SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p "
        "WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE "
        "AND r.company_id IS NULL AND r.deleted_at IS NULL "
        "AND p.deleted_at IS NULL AND p.code = 'purchase_requests:create' "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    # Preserve shared permission data and any role assignments on rollback.
    pass
