"""Evento de retorno sobre una factura.

Revision ID: 0138
Revises: 0137

Bloque V4d2 del área de Ventas. El evento de retorno (tipo 18 de CAT-002) documenta los bienes que
el cliente devuelve de una factura (01) sellada: reduce la venta y el débito fiscal del emisor
(Normativa DTE 2.0, regla 13.3). Es un evento, sin número de control, así que vive en su propia
tabla y no en ``sales_fiscal_documents``.

- ``sales_fiscal_returns``: la solicitud, su estado ante el servicio DTE (sello o marcador) y su
  anulación (invalidación tipo 2 del evento: solicitante, responsable y su propio estado).
- ``sales_fiscal_return_lines``: qué se devolvió de cada línea de la factura (cantidad, monto con
  IVA e IVA), para el saldo de la factura entre retornos.
- ``sales_fiscal_document_emails.return_id``: el envío del evento al cliente.
- Permiso ``sales_invoices:returns``.
"""

from alembic import op
from sqlalchemy import text

revision = "0138"
down_revision = "0137"
branch_labels = None
depends_on = None

_PERMISSION = (
    "sales_invoices:returns",
    "Registrar y anular eventos de retorno sobre facturas",
)
_PEOPLE = "('36','13','37','03','02')"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE sales_fiscal_returns (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            document_id uuid NOT NULL,
            reason varchar(300) NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'pending',
            idempotency_key varchar(120) NOT NULL,
            request_payload jsonb NOT NULL,
            total numeric(18, 2) NOT NULL,
            attempts integer NOT NULL DEFAULT 0,
            generation_code uuid,
            seal varchar(100),
            dte_json jsonb,
            json_object_key text,
            pdf_object_key text,
            error_code varchar(80),
            error_message text,
            issued_at timestamptz,
            created_by_id uuid NOT NULL,
            annul_status varchar(16),
            annul_idempotency_key varchar(120),
            annul_attempts integer NOT NULL DEFAULT 0,
            annul_requester_name varchar(100),
            annul_requester_document_type varchar(2),
            annul_requester_document_number varchar(25),
            annul_responsible_name varchar(100),
            annul_responsible_document_type varchar(2),
            annul_responsible_document_number varchar(25),
            annul_generation_code uuid,
            annul_seal varchar(100),
            annul_error_code varchar(80),
            annul_error_message text,
            annul_requested_by_id uuid,
            annul_requested_at timestamptz,
            annulled_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_fiscal_returns_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_sales_fiscal_returns_idempotency UNIQUE (company_id, idempotency_key),
            CONSTRAINT uq_sales_fiscal_returns_generation UNIQUE (company_id, generation_code),
            CONSTRAINT uq_sales_fiscal_returns_annul_key UNIQUE (company_id, annul_idempotency_key),
            CONSTRAINT fk_sales_fiscal_returns_document FOREIGN KEY (company_id, document_id)
                REFERENCES sales_fiscal_documents (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_fiscal_returns_creator FOREIGN KEY (created_by_id, company_id)
                REFERENCES user_companies (user_id, company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_fiscal_returns_annul_requester
                FOREIGN KEY (annul_requested_by_id, company_id)
                REFERENCES user_companies (user_id, company_id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_fiscal_returns_status CHECK (
                status IN ('pending','issued','simulated','rejected','failed','invalidated')
                AND char_length(btrim(reason)) BETWEEN 5 AND 300
                AND total >= 0 AND attempts >= 0 AND annul_attempts >= 0
                AND (status NOT IN ('issued','simulated','invalidated')
                     OR (generation_code IS NOT NULL AND issued_at IS NOT NULL))
                AND (status <> 'issued' OR seal IS NOT NULL)
            ),
            CONSTRAINT ck_sales_fiscal_returns_annul CHECK (
                (annul_status IS NULL OR annul_status IN ('pending','accepted','rejected','failed'))
                AND (annul_status IS NULL) = (annul_idempotency_key IS NULL)
                AND (annul_status IS NULL) = (annul_requester_name IS NULL)
                AND (annul_status IS NULL) = (annul_requested_by_id IS NULL)
                AND (annul_requester_document_type IS NULL
                     OR annul_requester_document_type IN {_PEOPLE})
                AND (status = 'invalidated') = (annul_status = 'accepted' AND annulled_at IS NOT NULL)
            )
        );
        CREATE INDEX ix_sales_fiscal_returns_document
            ON sales_fiscal_returns (company_id, document_id, created_at);
        CREATE INDEX ix_sales_fiscal_returns_pending
            ON sales_fiscal_returns (updated_at)
            WHERE status = 'pending' OR annul_status = 'pending';
        CREATE TABLE sales_fiscal_return_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            return_id uuid NOT NULL,
            line_number smallint NOT NULL,
            invoice_line_number smallint NOT NULL,
            nature varchar(12) NOT NULL,
            description varchar(1000) NOT NULL,
            quantity numeric(18, 6) NOT NULL,
            amount numeric(18, 2) NOT NULL,
            vat numeric(18, 2) NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_fiscal_return_lines_number UNIQUE (company_id, return_id, line_number),
            CONSTRAINT fk_sales_fiscal_return_lines_return FOREIGN KEY (company_id, return_id)
                REFERENCES sales_fiscal_returns (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_fiscal_return_lines_values CHECK (
                nature IN ('taxed','exempt','not_subject')
                AND line_number > 0 AND invoice_line_number > 0
                AND quantity > 0 AND amount > 0 AND vat >= 0 AND vat <= amount
                AND (nature = 'taxed' OR vat = 0)
                AND char_length(btrim(description)) > 0
            )
        );
        ALTER TABLE sales_fiscal_document_emails
            ADD COLUMN return_id uuid,
            ADD CONSTRAINT fk_sales_fiscal_document_emails_return
                FOREIGN KEY (company_id, return_id)
                REFERENCES sales_fiscal_returns (company_id, id) ON DELETE RESTRICT,
            ADD CONSTRAINT ck_sales_fiscal_document_emails_subject
                CHECK (invalidation_id IS NULL OR return_id IS NULL);
        -- El envío automático de la factura no cuenta los de sus retornos; cada retorno tiene el suyo.
        DROP INDEX uq_sales_fiscal_document_emails_auto;
        CREATE UNIQUE INDEX uq_sales_fiscal_document_emails_auto
            ON sales_fiscal_document_emails (company_id, document_id)
            WHERE origin = 'auto' AND invalidation_id IS NULL AND return_id IS NULL;
        CREATE UNIQUE INDEX uq_sales_fiscal_document_emails_return
            ON sales_fiscal_document_emails (company_id, return_id)
            WHERE origin = 'auto' AND return_id IS NOT NULL;
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
    returns = op.get_bind().execute(text("SELECT count(*) FROM sales_fiscal_returns")).scalar()
    if returns:
        raise RuntimeError(
            f"Hay {returns} eventos de retorno guardados; se conservan diez años y la migración "
            "0138 no los borra. Respáldalos antes de revertir."
        )
    code, _ = _PERMISSION
    op.execute(f"""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code = '{code}');
        DELETE FROM permissions WHERE code = '{code}';
    """)
    op.execute("""
        DROP INDEX uq_sales_fiscal_document_emails_return;
        DROP INDEX uq_sales_fiscal_document_emails_auto;
        CREATE UNIQUE INDEX uq_sales_fiscal_document_emails_auto
            ON sales_fiscal_document_emails (company_id, document_id)
            WHERE origin = 'auto' AND invalidation_id IS NULL;
        ALTER TABLE sales_fiscal_document_emails
            DROP CONSTRAINT ck_sales_fiscal_document_emails_subject,
            DROP CONSTRAINT fk_sales_fiscal_document_emails_return,
            DROP COLUMN return_id;
        DROP TABLE sales_fiscal_return_lines;
        DROP TABLE sales_fiscal_returns;
    """)
