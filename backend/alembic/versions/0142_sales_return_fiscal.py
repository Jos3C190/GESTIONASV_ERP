"""Efecto fiscal de las devoluciones y reintegros de dinero.

Revision ID: 0142
Revises: 0141

Bloque V8a del área de Ventas.

- ``sales_return_fiscal_adjustments``: cada aceptación de una devolución (B08) de un pedido facturado
  deja su ajuste fiscal: la nota de crédito (si el documento es un crédito fiscal) o el evento de
  retorno (si es una factura), con las líneas y cantidades; o el motivo por el que no se pudo
  emitir (plazo vencido, documento sin sellar, pedido sin facturar…). Una devolución puede
  aceptarse en varias veces, así que hay una fila por aceptación.
- ``sales_refunds``: reintegro de dinero al cliente desde el saldo a favor de un recibo de cobro;
  no es un documento tributario. Se anula con motivo y restituye el saldo.
"""

from alembic import op
from sqlalchemy import text

revision = "0142"
down_revision = "0141"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE sales_return_fiscal_adjustments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            return_id uuid NOT NULL,
            document_id uuid,
            fiscal_note_id uuid,
            fiscal_return_id uuid,
            status varchar(12) NOT NULL,
            message varchar(500),
            lines jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_sales_return_fiscal_adjustments_return FOREIGN KEY (company_id, return_id)
                REFERENCES sales_returns (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_return_fiscal_adjustments_document
                FOREIGN KEY (company_id, document_id)
                REFERENCES sales_fiscal_documents (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_return_fiscal_adjustments_note FOREIGN KEY (company_id, fiscal_note_id)
                REFERENCES sales_fiscal_documents (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_return_fiscal_adjustments_event
                FOREIGN KEY (company_id, fiscal_return_id)
                REFERENCES sales_fiscal_returns (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_return_fiscal_adjustments_status CHECK (
                (status = 'issued' AND document_id IS NOT NULL AND message IS NULL
                 AND (fiscal_note_id IS NULL) <> (fiscal_return_id IS NULL))
                OR (status = 'skipped' AND fiscal_note_id IS NULL AND fiscal_return_id IS NULL
                    AND length(btrim(message)) >= 5)
            )
        );
        CREATE INDEX ix_sales_return_fiscal_adjustments_return
            ON sales_return_fiscal_adjustments (company_id, return_id, created_at);

        CREATE TABLE sales_refunds (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            branch_id uuid NOT NULL,
            customer_id uuid NOT NULL,
            receipt_id uuid NOT NULL,
            number integer NOT NULL CHECK (number > 0),
            refunded_on date NOT NULL,
            amount numeric(18, 2) NOT NULL CHECK (amount > 0),
            method varchar(12) NOT NULL
                CHECK (method IN ('cash', 'card', 'transfer', 'check', 'other')),
            reference varchar(100),
            reason varchar(300) NOT NULL CHECK (length(btrim(reason)) >= 5),
            status varchar(12) NOT NULL DEFAULT 'issued',
            idempotency_key varchar(120) NOT NULL,
            created_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            annul_reason varchar(300),
            annulled_by_id uuid REFERENCES users (id) ON DELETE RESTRICT,
            annulled_at timestamptz,
            CONSTRAINT uq_sales_refunds_number UNIQUE (company_id, number),
            CONSTRAINT uq_sales_refunds_idempotency UNIQUE (company_id, idempotency_key),
            CONSTRAINT fk_sales_refunds_branch FOREIGN KEY (branch_id, company_id)
                REFERENCES branches (id, company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_refunds_customer FOREIGN KEY (company_id, customer_id)
                REFERENCES sales_customers (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_refunds_receipt FOREIGN KEY (company_id, receipt_id)
                REFERENCES sales_receipts (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_refunds_reference CHECK (
                method = 'cash' OR length(btrim(coalesce(reference, ''))) >= 1
            ),
            CONSTRAINT ck_sales_refunds_status CHECK (
                (status = 'issued' AND annul_reason IS NULL AND annulled_by_id IS NULL
                 AND annulled_at IS NULL)
                OR (status = 'annulled' AND length(btrim(annul_reason)) >= 5
                    AND annulled_by_id IS NOT NULL AND annulled_at IS NOT NULL)
            )
        );
        CREATE INDEX ix_sales_refunds_receipt ON sales_refunds (company_id, receipt_id);
    """)


def downgrade() -> None:
    bind = op.get_bind()
    adjustments = bind.execute(
        text("SELECT count(*) FROM sales_return_fiscal_adjustments")
    ).scalar()
    refunds = bind.execute(text("SELECT count(*) FROM sales_refunds")).scalar()
    if adjustments or refunds:
        raise RuntimeError(
            f"Hay {adjustments} ajustes fiscales de devoluciones y {refunds} reintegros; la "
            "migración 0142 no los borra. Respáldalos antes de revertir."
        )
    op.execute("""
        DROP TABLE sales_refunds;
        DROP TABLE sales_return_fiscal_adjustments;
    """)
