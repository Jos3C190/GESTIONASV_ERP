"""Invalidación y reemplazo de documentos fiscales.

Revision ID: 0131
Revises: 0130

Bloque V4b del área de Ventas. Un documento sellado no se borra: se invalida con un evento firmado
(rescindir la operación) o se reemplaza por uno correcto y después se invalida (error en los datos).

- ``sales_fiscal_documents`` agrega el estado ``invalidated`` y los vínculos de reemplazo
  (``replaces_document_id`` en el nuevo, ``superseded_by_id`` en el original).
- El documento activo de un pedido es el pendiente, en contingencia, emitido o simulado que no esté
  siendo reemplazado: un rechazado o un invalidado ya no bloquea volver a facturarlo.
- ``sales_fiscal_invalidations`` guarda cada solicitud de invalidación con su evento.
- Permiso ``sales_invoices:invalidate``.
"""

from alembic import op
from sqlalchemy import text

revision = "0131"
down_revision = "0130"
branch_labels = None
depends_on = None

_PERMISSION = ("sales_invoices:invalidate", "Invalidar y corregir documentos fiscales emitidos")
_ACTIVE = "status IN ('pending','contingency','issued','simulated') AND superseded_by_id IS NULL"


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE sales_fiscal_documents
            ADD COLUMN replaces_document_id uuid,
            ADD COLUMN superseded_by_id uuid,
            DROP CONSTRAINT ck_sales_fiscal_documents_status,
            ADD CONSTRAINT ck_sales_fiscal_documents_status CHECK (
                status IN ('pending','contingency','issued','simulated','rejected','failed',
                           'invalidated')
            ),
            DROP CONSTRAINT ck_sales_fiscal_documents_identity,
            ADD CONSTRAINT ck_sales_fiscal_documents_identity CHECK (
                status NOT IN ('contingency','issued','simulated','invalidated')
                OR (generation_code IS NOT NULL AND control_number IS NOT NULL
                    AND issued_at IS NOT NULL)
            ),
            ADD CONSTRAINT ck_sales_fiscal_documents_replacement CHECK (
                replaces_document_id IS DISTINCT FROM id AND superseded_by_id IS DISTINCT FROM id
            ),
            ADD CONSTRAINT fk_sales_fiscal_documents_replaces
                FOREIGN KEY (company_id, replaces_document_id)
                REFERENCES sales_fiscal_documents (company_id, id) ON DELETE RESTRICT,
            ADD CONSTRAINT fk_sales_fiscal_documents_superseded
                FOREIGN KEY (company_id, superseded_by_id)
                REFERENCES sales_fiscal_documents (company_id, id) ON DELETE RESTRICT;
        DROP INDEX uq_sales_fiscal_documents_active_sale;
        CREATE UNIQUE INDEX uq_sales_fiscal_documents_active_sale
            ON sales_fiscal_documents (company_id, sale_id) WHERE {_ACTIVE};
        CREATE UNIQUE INDEX uq_sales_fiscal_documents_replaces
            ON sales_fiscal_documents (company_id, replaces_document_id)
            WHERE replaces_document_id IS NOT NULL AND status NOT IN ('failed','rejected');
    """)
    op.execute("""
        CREATE TABLE sales_fiscal_invalidations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            document_id uuid NOT NULL,
            kind smallint NOT NULL,
            reason varchar(200),
            requester_name varchar(100) NOT NULL,
            requester_document_type varchar(2) NOT NULL,
            requester_document_number varchar(25) NOT NULL,
            responsible_name varchar(100),
            responsible_document_type varchar(2),
            responsible_document_number varchar(25),
            replacement_document_id uuid,
            cancel_order boolean NOT NULL DEFAULT false,
            status varchar(16) NOT NULL DEFAULT 'pending',
            idempotency_key varchar(120) NOT NULL,
            attempts integer NOT NULL DEFAULT 0,
            event_generation_code uuid,
            event_seal varchar(100),
            error_code varchar(80),
            error_message text,
            requested_by_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            resolved_at timestamptz,
            CONSTRAINT uq_sales_fiscal_invalidations_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_sales_fiscal_invalidations_idempotency UNIQUE (company_id, idempotency_key),
            CONSTRAINT fk_sales_fiscal_invalidations_document
                FOREIGN KEY (company_id, document_id)
                REFERENCES sales_fiscal_documents (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_fiscal_invalidations_replacement
                FOREIGN KEY (company_id, replacement_document_id)
                REFERENCES sales_fiscal_documents (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_fiscal_invalidations_requester
                FOREIGN KEY (requested_by_id, company_id)
                REFERENCES user_companies (user_id, company_id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_fiscal_invalidations_kind CHECK (
                (kind = 1 AND replacement_document_id IS NOT NULL AND NOT cancel_order)
                OR (kind = 2 AND replacement_document_id IS NULL)
            ),
            CONSTRAINT ck_sales_fiscal_invalidations_status CHECK (
                status IN ('pending','accepted','rejected','failed')
            ),
            CONSTRAINT ck_sales_fiscal_invalidations_people CHECK (
                requester_document_type IN ('36','13','37','03','02')
                AND char_length(btrim(requester_name)) BETWEEN 3 AND 100
                AND char_length(btrim(requester_document_number)) BETWEEN 1 AND 25
            ),
            CONSTRAINT ck_sales_fiscal_invalidations_result CHECK (
                (status = 'pending') = (resolved_at IS NULL)
                AND (status <> 'accepted' OR event_generation_code IS NOT NULL)
                AND (status NOT IN ('rejected','failed') OR error_message IS NOT NULL)
                AND attempts >= 0
            )
        );
        CREATE UNIQUE INDEX uq_sales_fiscal_invalidations_pending
            ON sales_fiscal_invalidations (company_id, document_id) WHERE status = 'pending';
        CREATE INDEX ix_sales_fiscal_invalidations_status
            ON sales_fiscal_invalidations (status, updated_at);
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
    stored = bind.execute(text("SELECT count(*) FROM sales_fiscal_invalidations")).scalar()
    linked = bind.execute(
        text(
            "SELECT count(*) FROM sales_fiscal_documents WHERE status = 'invalidated' "
            "OR replaces_document_id IS NOT NULL OR superseded_by_id IS NOT NULL"
        )
    ).scalar()
    # Antes de 0131 un pedido tenía un solo documento no fallido; uno rechazado y otro posterior
    # no cabrían en el índice anterior.
    repeated = bind.execute(
        text(
            "SELECT count(*) FROM (SELECT 1 FROM sales_fiscal_documents WHERE status <> 'failed' "
            "GROUP BY company_id, sale_id HAVING count(*) > 1) AS repeated"
        )
    ).scalar()
    if stored or linked or repeated:
        raise RuntimeError(
            f"Hay {stored} invalidaciones, {linked} documentos invalidados o de reemplazo y "
            f"{repeated} pedidos facturados de nuevo; la migración 0131 los perdería. Respáldalos "
            "antes de revertir."
        )
    code, _ = _PERMISSION
    op.execute(f"""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code = '{code}');
        DELETE FROM permissions WHERE code = '{code}';
    """)
    op.execute("""
        DROP TABLE sales_fiscal_invalidations;
        DROP INDEX uq_sales_fiscal_documents_replaces;
        DROP INDEX uq_sales_fiscal_documents_active_sale;
        CREATE UNIQUE INDEX uq_sales_fiscal_documents_active_sale
            ON sales_fiscal_documents (company_id, sale_id) WHERE status <> 'failed';
        ALTER TABLE sales_fiscal_documents
            DROP CONSTRAINT fk_sales_fiscal_documents_superseded,
            DROP CONSTRAINT fk_sales_fiscal_documents_replaces,
            DROP CONSTRAINT ck_sales_fiscal_documents_replacement,
            DROP CONSTRAINT ck_sales_fiscal_documents_identity,
            ADD CONSTRAINT ck_sales_fiscal_documents_identity CHECK (
                status NOT IN ('contingency','issued','simulated') OR (generation_code IS NOT NULL
                AND control_number IS NOT NULL AND issued_at IS NOT NULL)
            ),
            DROP CONSTRAINT ck_sales_fiscal_documents_status,
            ADD CONSTRAINT ck_sales_fiscal_documents_status CHECK (
                status IN ('pending','contingency','issued','simulated','rejected','failed')
            ),
            DROP COLUMN superseded_by_id,
            DROP COLUMN replaces_document_id
    """)
