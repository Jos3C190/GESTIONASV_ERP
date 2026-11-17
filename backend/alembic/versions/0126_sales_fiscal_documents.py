"""Documento fiscal del pedido: la factura o el crédito fiscal emitido por el servicio DTE.

Revision ID: 0126
Revises: 0125

Bloque V3b del área de Ventas. El ERP guarda su copia de cada DTE: el snapshot del emisor, la
solicitud enviada al servicio, el JSON devuelto, el sello, la respuesta de Hacienda y las llaves del
JSON y el PDF en el almacenamiento. Un pedido tiene a lo sumo un documento vigente (los fallidos
se pueden volver a intentar).
"""

from alembic import op
from sqlalchemy import text

revision = "0126"
down_revision = "0125"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("sales_invoices:read", "Consultar los documentos fiscales emitidos"),
    ("sales_invoices:issue", "Facturar pedidos y reintentar documentos fiscales"),
)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE sales_fiscal_documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            branch_id uuid NOT NULL,
            sale_id uuid NOT NULL,
            establishment_id uuid NOT NULL,
            point_of_sale_id uuid NOT NULL,
            document_type varchar(2) NOT NULL,
            mode varchar(16) NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'pending',
            idempotency_key varchar(120) NOT NULL,
            generation_code uuid,
            control_number varchar(31),
            total numeric(18, 2) NOT NULL,
            issuer_snapshot jsonb NOT NULL,
            request_payload jsonb NOT NULL,
            dte_json jsonb,
            seal varchar(100),
            service_response jsonb,
            json_object_key text,
            pdf_object_key text,
            error_code varchar(80),
            error_message text,
            attempts integer NOT NULL DEFAULT 0,
            issued_at timestamptz,
            created_by_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_fiscal_documents_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_sales_fiscal_documents_idempotency UNIQUE (company_id, idempotency_key),
            CONSTRAINT uq_sales_fiscal_documents_generation UNIQUE (company_id, generation_code),
            CONSTRAINT fk_sales_fiscal_documents_sale FOREIGN KEY (company_id, sale_id)
                REFERENCES sales (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_fiscal_documents_branch FOREIGN KEY (branch_id, company_id)
                REFERENCES branches (id, company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_fiscal_documents_establishment
                FOREIGN KEY (company_id, establishment_id)
                REFERENCES fiscal_establishments (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_fiscal_documents_point_of_sale
                FOREIGN KEY (company_id, point_of_sale_id)
                REFERENCES fiscal_points_of_sale (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_fiscal_documents_creator FOREIGN KEY (created_by_id, company_id)
                REFERENCES user_companies (user_id, company_id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_fiscal_documents_document CHECK (document_type IN ('01','03')),
            CONSTRAINT ck_sales_fiscal_documents_mode
                CHECK (mode IN ('simulated','hacienda-test','production')),
            CONSTRAINT ck_sales_fiscal_documents_status
                CHECK (status IN ('pending','issued','simulated','rejected','failed')),
            CONSTRAINT ck_sales_fiscal_documents_identity CHECK (
                status NOT IN ('issued','simulated')
                OR (generation_code IS NOT NULL AND control_number IS NOT NULL
                    AND issued_at IS NOT NULL)
            ),
            CONSTRAINT ck_sales_fiscal_documents_seal CHECK (status <> 'issued' OR seal IS NOT NULL),
            CONSTRAINT ck_sales_fiscal_documents_total CHECK (total >= 0 AND attempts >= 0)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_sales_fiscal_documents_active_sale
            ON sales_fiscal_documents (company_id, sale_id) WHERE status <> 'failed'
    """)
    op.execute("""
        CREATE INDEX ix_sales_fiscal_documents_company_status
            ON sales_fiscal_documents (company_id, branch_id, status, created_at)
    """)
    for code, description in _PERMISSIONS:
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
    stored = op.get_bind().execute(text("SELECT count(*) FROM sales_fiscal_documents")).scalar()
    if stored:
        raise RuntimeError(
            f"Hay {stored} documentos fiscales guardados; se conservan diez años y la migración "
            "0126 no los borra. Respáldalos antes de revertir."
        )
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE FROM role_permissions WHERE permission_id IN
              (SELECT id FROM permissions WHERE code = '{code}');
            DELETE FROM permissions WHERE code = '{code}';
        """)
    op.execute("DROP TABLE sales_fiscal_documents")
