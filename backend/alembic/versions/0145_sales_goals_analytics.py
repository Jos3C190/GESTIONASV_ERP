"""Metas mensuales de venta por sucursal y permisos del análisis comercial.

Revision ID: 0145
Revises: 0144

Bloque V9a. ``sales_branch_goals`` guarda la meta de venta sin IVA de cada sucursal por mes (una por
sucursal y mes). Permisos nuevos: ``sales_analytics:read`` (ver ventas, análisis y metas, también en
el tablero) y ``sales_goals:manage`` (definir metas), para ``SUPER_ADMIN``. ``fiscal_periods:manage``
pasa al módulo ``fiscal``.
"""

from alembic import op
from sqlalchemy import text

revision = "0145"
down_revision = "0144"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("sales_analytics:read", "Ver las cifras de venta, el análisis comercial y las metas", "sales"),
    ("sales_goals:manage", "Definir las metas mensuales de venta por sucursal", "sales"),
)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE sales_branch_goals (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            branch_id uuid NOT NULL,
            period date NOT NULL CHECK (extract(day FROM period) = 1),
            amount numeric(18, 2) NOT NULL CHECK (amount > 0),
            updated_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_branch_goals_period UNIQUE (company_id, branch_id, period),
            CONSTRAINT fk_sales_branch_goals_branch FOREIGN KEY (branch_id, company_id)
                REFERENCES branches (id, company_id) ON DELETE RESTRICT
        );
        UPDATE permissions SET module = 'fiscal' WHERE code = 'fiscal_periods:manage';
    """)
    for code, description, module in _PERMISSIONS:
        op.execute(f"""
            INSERT INTO permissions (id, code, description, module, created_at)
            VALUES (gen_random_uuid(), '{code}', '{description}', '{module}', now())
            ON CONFLICT DO NOTHING
        """)
        op.execute(f"""
            INSERT INTO role_permissions (role_id, permission_id, created_at)
            SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p
            WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE AND r.company_id IS NULL
              AND r.deleted_at IS NULL AND p.deleted_at IS NULL AND p.code = '{code}'
            ON CONFLICT DO NOTHING
        """)


def downgrade() -> None:
    bind = op.get_bind()
    goals = bind.execute(text("SELECT count(*) FROM sales_branch_goals")).scalar()
    if goals:
        raise RuntimeError(
            f"Hay {goals} metas de venta; la migración 0145 no las borra. Respáldalas antes de "
            "revertir."
        )
    for code, _, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE FROM role_permissions WHERE permission_id IN
              (SELECT id FROM permissions WHERE code = '{code}');
            DELETE FROM permissions WHERE code = '{code}';
        """)
    op.execute("""
        UPDATE permissions SET module = 'sales' WHERE code = 'fiscal_periods:manage';
        DROP TABLE sales_branch_goals;
    """)
