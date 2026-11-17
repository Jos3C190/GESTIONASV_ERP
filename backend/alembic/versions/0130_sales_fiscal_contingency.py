"""Documentos fiscales en contingencia.

Revision ID: 0130
Revises: 0129

Bloque V4a del área de Ventas. Un documento generado sin comunicación con Hacienda ya tiene
número de control y versión legible, pero espera el Evento de Contingencia y su transmisión:
queda en el estado ``contingency`` con el tipo (CAT-005) y el motivo de la contingencia, hasta que
el servicio DTE lo sella (``issued``/``simulated``) o Hacienda lo rechaza.

Agrega el permiso ``sales_invoices:contingency`` para activar y cerrar contingencias.
"""

from alembic import op
from sqlalchemy import text

revision = "0130"
down_revision = "0129"
branch_labels = None
depends_on = None

_PERMISSION = ("sales_invoices:contingency", "Activar y cerrar contingencias de facturación")


def upgrade() -> None:
    op.execute("""
        ALTER TABLE sales_fiscal_documents
            ADD COLUMN contingency_type smallint,
            ADD COLUMN contingency_reason text,
            ADD COLUMN contingency_at timestamptz,
            DROP CONSTRAINT ck_sales_fiscal_documents_status,
            ADD CONSTRAINT ck_sales_fiscal_documents_status CHECK (
                status IN ('pending','contingency','issued','simulated','rejected','failed')
            ),
            DROP CONSTRAINT ck_sales_fiscal_documents_identity,
            ADD CONSTRAINT ck_sales_fiscal_documents_identity CHECK (
                status NOT IN ('contingency','issued','simulated') OR (generation_code IS NOT NULL
                AND control_number IS NOT NULL AND issued_at IS NOT NULL)
            ),
            ADD CONSTRAINT ck_sales_fiscal_documents_contingency CHECK (
                (contingency_type IS NULL OR contingency_type BETWEEN 1 AND 5)
                AND (status <> 'contingency' OR (contingency_at IS NOT NULL
                     AND contingency_type IS NOT NULL))
            )
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
    stored = (
        op.get_bind()
        .execute(
            text(
                "SELECT count(*) FROM sales_fiscal_documents "
                "WHERE status = 'contingency' OR contingency_at IS NOT NULL"
            )
        )
        .scalar()
    )
    if stored:
        raise RuntimeError(
            f"Hay {stored} documentos fiscales generados en contingencia; la migración 0130 "
            "perdería su tipo y motivo. Respáldalos antes de revertir."
        )
    code, _ = _PERMISSION
    op.execute(f"""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code = '{code}');
        DELETE FROM permissions WHERE code = '{code}';
    """)
    op.execute("""
        ALTER TABLE sales_fiscal_documents
            DROP CONSTRAINT ck_sales_fiscal_documents_contingency,
            DROP CONSTRAINT ck_sales_fiscal_documents_identity,
            ADD CONSTRAINT ck_sales_fiscal_documents_identity CHECK (
                status NOT IN ('issued','simulated') OR (generation_code IS NOT NULL
                AND control_number IS NOT NULL AND issued_at IS NOT NULL)
            ),
            DROP CONSTRAINT ck_sales_fiscal_documents_status,
            ADD CONSTRAINT ck_sales_fiscal_documents_status CHECK (
                status IN ('pending','issued','simulated','rejected','failed')
            ),
            DROP COLUMN contingency_at,
            DROP COLUMN contingency_reason,
            DROP COLUMN contingency_type
    """)
