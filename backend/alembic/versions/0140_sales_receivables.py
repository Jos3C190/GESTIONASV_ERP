"""Cuentas por cobrar: recibos de cobro y comprobantes de retención recibidos.

Revision ID: 0140
Revises: 0139

Bloque V5a del área de Ventas. La cuenta por cobrar no se guarda: el saldo de cada documento se
calcula con su DTE (``totalPagar``), sus notas, retornos y lo aplicado por los recibos vigentes.

- ``sales_receipts``: recibo de cobro (no es un DTE), con número correlativo por empresa, cliente,
  sucursal, fecha y total cobrado. Se anula con motivo y nunca se edita.
- ``sales_receipt_payments``: formas de pago del recibo (efectivo, tarjeta, transferencia, cheque u
  otro, con referencia).
- ``sales_receipt_applications``: lo aplicado a cada documento; lo no aplicado es saldo a favor.
- ``sales_withholding_certificates``: comprobante de retención del 1 % que entregó el cliente por
  un documento; respalda la retención ya descontada en el DTE (casilla 162 del F-07).
- Permisos ``sales_receivables:read`` y ``sales_receivables:collect``.
"""

from alembic import op
from sqlalchemy import text

revision = "0140"
down_revision = "0139"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("sales_receivables:read", "Ver la cartera, los estados de cuenta y los recibos de cobro"),
    (
        "sales_receivables:collect",
        "Registrar y anular recibos de cobro y comprobantes de retención",
    ),
)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE sales_receipts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            branch_id uuid NOT NULL,
            customer_id uuid NOT NULL,
            number integer NOT NULL CHECK (number > 0),
            received_on date NOT NULL,
            total numeric(18, 2) NOT NULL CHECK (total > 0),
            notes varchar(300),
            status varchar(12) NOT NULL DEFAULT 'issued',
            idempotency_key varchar(120) NOT NULL,
            created_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            annul_reason varchar(300),
            annulled_by_id uuid REFERENCES users (id) ON DELETE RESTRICT,
            annulled_at timestamptz,
            CONSTRAINT uq_sales_receipts_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_sales_receipts_number UNIQUE (company_id, number),
            CONSTRAINT uq_sales_receipts_idempotency UNIQUE (company_id, idempotency_key),
            CONSTRAINT fk_sales_receipts_branch FOREIGN KEY (branch_id, company_id)
                REFERENCES branches (id, company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_receipts_customer FOREIGN KEY (company_id, customer_id)
                REFERENCES sales_customers (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_receipts_status CHECK (
                (status = 'issued' AND annul_reason IS NULL AND annulled_by_id IS NULL
                 AND annulled_at IS NULL)
                OR (status = 'annulled' AND length(btrim(annul_reason)) >= 5
                    AND annulled_by_id IS NOT NULL AND annulled_at IS NOT NULL)
            )
        );
        CREATE INDEX ix_sales_receipts_customer
            ON sales_receipts (company_id, customer_id, received_on);

        CREATE TABLE sales_receipt_payments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            receipt_id uuid NOT NULL,
            line_number smallint NOT NULL CHECK (line_number > 0),
            method varchar(12) NOT NULL
                CHECK (method IN ('cash', 'card', 'transfer', 'check', 'other')),
            amount numeric(18, 2) NOT NULL CHECK (amount > 0),
            reference varchar(100),
            CONSTRAINT uq_sales_receipt_payments_line UNIQUE (company_id, receipt_id, line_number),
            CONSTRAINT fk_sales_receipt_payments_receipt FOREIGN KEY (company_id, receipt_id)
                REFERENCES sales_receipts (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_receipt_payments_reference CHECK (
                method = 'cash' OR length(btrim(coalesce(reference, ''))) >= 1
            )
        );

        CREATE TABLE sales_receipt_applications (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            receipt_id uuid NOT NULL,
            document_id uuid NOT NULL,
            amount numeric(18, 2) NOT NULL CHECK (amount > 0),
            applied_on date NOT NULL,
            created_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_sales_receipt_applications_receipt FOREIGN KEY (company_id, receipt_id)
                REFERENCES sales_receipts (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_receipt_applications_document FOREIGN KEY (company_id, document_id)
                REFERENCES sales_fiscal_documents (company_id, id) ON DELETE RESTRICT
        );
        CREATE INDEX ix_sales_receipt_applications_document
            ON sales_receipt_applications (company_id, document_id);
        CREATE INDEX ix_sales_receipt_applications_receipt
            ON sales_receipt_applications (company_id, receipt_id);

        CREATE TABLE sales_withholding_certificates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            document_id uuid NOT NULL,
            certificate_number varchar(100) NOT NULL CHECK (length(btrim(certificate_number)) >= 1),
            issued_on date NOT NULL,
            amount numeric(18, 2) NOT NULL CHECK (amount > 0),
            created_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_withholding_certificates_document UNIQUE (company_id, document_id),
            CONSTRAINT fk_sales_withholding_certificates_document FOREIGN KEY (company_id, document_id)
                REFERENCES sales_fiscal_documents (company_id, id) ON DELETE RESTRICT
        );
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
    bind = op.get_bind()
    receipts = bind.execute(text("SELECT count(*) FROM sales_receipts")).scalar()
    certificates = bind.execute(
        text("SELECT count(*) FROM sales_withholding_certificates")
    ).scalar()
    if receipts or certificates:
        raise RuntimeError(
            f"Hay {receipts} recibos de cobro y {certificates} comprobantes de retención; la "
            "migración 0140 no los borra. Respáldalos antes de revertir."
        )
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE FROM role_permissions WHERE permission_id IN
              (SELECT id FROM permissions WHERE code = '{code}');
            DELETE FROM permissions WHERE code = '{code}';
        """)
    op.execute("""
        DROP TABLE sales_withholding_certificates;
        DROP TABLE sales_receipt_applications;
        DROP TABLE sales_receipt_payments;
        DROP TABLE sales_receipts;
    """)
