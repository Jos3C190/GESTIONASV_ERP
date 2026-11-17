"""Envíos por correo del documento fiscal al cliente.

Revision ID: 0127
Revises: 0126

Bloque V3c del área de Ventas. Cada envío (automático al emitirse o pedido por un usuario)
queda registrado con sus destinatarios, su estado, sus intentos y el ``Message-ID`` con el que
salió. Un documento tiene a lo sumo un envío automático.
"""

from alembic import op
from sqlalchemy import text

revision = "0127"
down_revision = "0126"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE sales_fiscal_document_emails (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            document_id uuid NOT NULL,
            recipients text[] NOT NULL,
            origin varchar(8) NOT NULL,
            status varchar(8) NOT NULL DEFAULT 'pending',
            attempts integer NOT NULL DEFAULT 0,
            error_code varchar(80),
            error_message text,
            message_id varchar(255),
            requested_by_id uuid,
            sent_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_fiscal_document_emails_company_id UNIQUE (company_id, id),
            CONSTRAINT fk_sales_fiscal_document_emails_document
                FOREIGN KEY (company_id, document_id)
                REFERENCES sales_fiscal_documents (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_fiscal_document_emails_requester
                FOREIGN KEY (requested_by_id, company_id)
                REFERENCES user_companies (user_id, company_id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_fiscal_document_emails_origin CHECK (
                origin IN ('auto','manual')
                AND (origin = 'manual') = (requested_by_id IS NOT NULL)
            ),
            CONSTRAINT ck_sales_fiscal_document_emails_status
                CHECK (status IN ('pending','sent','failed')),
            CONSTRAINT ck_sales_fiscal_document_emails_recipients
                CHECK (cardinality(recipients) BETWEEN 1 AND 5),
            CONSTRAINT ck_sales_fiscal_document_emails_sent CHECK (
                (status = 'sent') = (sent_at IS NOT NULL AND message_id IS NOT NULL)
            ),
            CONSTRAINT ck_sales_fiscal_document_emails_attempts CHECK (attempts >= 0)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_sales_fiscal_document_emails_auto
            ON sales_fiscal_document_emails (company_id, document_id) WHERE origin = 'auto'
    """)
    op.execute("""
        CREATE INDEX ix_sales_fiscal_document_emails_document
            ON sales_fiscal_document_emails (company_id, document_id, created_at)
    """)
    op.execute("""
        CREATE INDEX ix_sales_fiscal_document_emails_pending
            ON sales_fiscal_document_emails (updated_at) WHERE status = 'pending'
    """)


def downgrade() -> None:
    stored = (
        op.get_bind().execute(text("SELECT count(*) FROM sales_fiscal_document_emails")).scalar()
    )
    if stored:
        raise RuntimeError(
            f"Hay {stored} envíos de documentos fiscales registrados; la migración 0127 no los "
            "borra. Respáldalos antes de revertir."
        )
    op.execute("DROP TABLE sales_fiscal_document_emails")
