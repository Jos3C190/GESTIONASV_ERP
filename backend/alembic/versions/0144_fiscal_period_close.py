"""Cierre de período fiscal por empresa y mes.

Revision ID: 0144
Revises: 0143

Bloque V8b2. ``fiscal_period_closes`` guarda cada cierre de un mes ya terminado con el resumen de los
libros de IVA como constancia; reabrir pide motivo y deja la fila como historial. A lo sumo un cierre
vigente por empresa y mes. Permiso ``fiscal_periods:manage`` (cerrar y reabrir) para ``SUPER_ADMIN``.
"""

from alembic import op
from sqlalchemy import text

revision = "0144"
down_revision = "0143"
branch_labels = None
depends_on = None

_PERMISSION = ("fiscal_periods:manage", "Cerrar y reabrir períodos fiscales (meses declarados)")


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fiscal_period_closes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            period date NOT NULL CHECK (extract(day FROM period) = 1),
            status varchar(12) NOT NULL DEFAULT 'closed',
            summary jsonb NOT NULL DEFAULT '{}'::jsonb,
            closed_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            closed_at timestamptz NOT NULL DEFAULT now(),
            reopen_reason varchar(500),
            reopened_by_id uuid REFERENCES users (id) ON DELETE RESTRICT,
            reopened_at timestamptz,
            CONSTRAINT ck_fiscal_period_closes_status CHECK (
                (status = 'closed' AND reopen_reason IS NULL AND reopened_by_id IS NULL
                 AND reopened_at IS NULL)
                OR (status = 'reopened' AND reopen_reason IS NOT NULL AND length(btrim(reopen_reason)) >= 10
                    AND reopened_by_id IS NOT NULL AND reopened_at IS NOT NULL)
            )
        );
        CREATE UNIQUE INDEX uq_fiscal_period_closes_active
            ON fiscal_period_closes (company_id, period) WHERE status = 'closed';
        CREATE INDEX ix_fiscal_period_closes_period
            ON fiscal_period_closes (company_id, period, closed_at);
    """)
    code, description = _PERMISSION
    op.execute(f"""
        INSERT INTO permissions (id, code, description, module, created_at)
        VALUES (gen_random_uuid(), '{code}', '{description}', 'sales', now())
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
    closes = bind.execute(text("SELECT count(*) FROM fiscal_period_closes")).scalar()
    if closes:
        raise RuntimeError(
            f"Hay {closes} cierres de período; la migración 0144 no los borra. Respáldalos antes de "
            "revertir."
        )
    code, _ = _PERMISSION
    op.execute(f"""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code = '{code}');
        DELETE FROM permissions WHERE code = '{code}';
    """)
    op.execute("DROP TABLE fiscal_period_closes;")
