"""Reconcile purchase-request RBAC data for databases already at 0044."""

from __future__ import annotations

from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("purchase_requests:read", "Ver solicitudes de compra", "purchase_requests"),
    (
        "purchase_requests:manage",
        "Crear, editar, enviar y cancelar solicitudes",
        "purchase_requests",
    ),
    ("purchase_requests:approve", "Aprobar o rechazar solicitudes", "purchase_requests"),
)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    """Install missing catalogue rows and reconcile global SUPER_ADMIN grants."""
    for code, description, module in PERMISSIONS:
        op.execute(
            "INSERT INTO permissions (id, code, description, module, created_at) "
            f"VALUES (gen_random_uuid(), {_sql_literal(code)}, "
            f"{_sql_literal(description)}, {_sql_literal(module)}, now()) "
            "ON CONFLICT DO NOTHING"
        )

    permission_codes = ",".join(_sql_literal(code) for code, _description, _module in PERMISSIONS)
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id, created_at) "
        "SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p "
        "WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE "
        "AND r.company_id IS NULL AND r.deleted_at IS NULL "
        f"AND p.deleted_at IS NULL AND p.code IN ({permission_codes}) "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    """Keep shared RBAC data when rolling back the reconciliation revision."""
    pass
