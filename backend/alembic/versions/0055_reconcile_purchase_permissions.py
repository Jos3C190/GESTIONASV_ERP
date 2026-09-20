"""Reconcile purchase-receipt RBAC catalogue rows and SUPER_ADMIN grants."""

from __future__ import annotations

from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("purchases:read", "Ver compras y recepciones", "purchases"),
    (
        "purchases:manage",
        "Crear, editar y cancelar borradores de recepción",
        "purchases",
    ),
    ("purchases:receive", "Confirmar recepciones de órdenes de compra", "purchases"),
    ("purchases:verify", "Verificar y cerrar recepciones de compra", "purchases"),
)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    """Install missing permission rows and reconcile global SUPER_ADMIN grants."""
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
    """Keep shared RBAC catalogue rows when rolling back this revision."""
    pass
