"""Notas de crédito y de débito sobre un crédito fiscal.

Revision ID: 0133
Revises: 0132

Bloque V4c del área de Ventas. La nota de crédito (05) rebaja y la de débito (06) aumenta lo
documentado en un comprobante de crédito fiscal (03) sellado (Código Tributario, art. 110).

- ``sales_fiscal_documents`` admite los tipos 05 y 06. Una nota guarda el CCF que ajusta
  (``related_document_id``) y su motivo; pertenece al mismo pedido que el CCF.
- El documento activo del pedido sigue siendo su factura o su CCF: las notas no cuentan.
- ``sales_fiscal_note_lines``: lo que ajusta cada línea de la nota, para calcular el saldo de cada
  línea del CCF (devolución por cantidad, rebaja por monto o cargo).
- Permiso ``sales_invoices:notes``.
"""

from alembic import op
from sqlalchemy import text

revision = "0133"
down_revision = "0132"
branch_labels = None
depends_on = None

_PERMISSION = (
    "sales_invoices:notes",
    "Emitir notas de crédito y de débito sobre un crédito fiscal",
)
_ACTIVE = "status IN ('pending','contingency','issued','simulated') AND superseded_by_id IS NULL"


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE sales_fiscal_documents
            ADD COLUMN related_document_id uuid,
            ADD COLUMN note_reason varchar(300),
            DROP CONSTRAINT ck_sales_fiscal_documents_document,
            ADD CONSTRAINT ck_sales_fiscal_documents_document
                CHECK (document_type IN ('01','03','05','06')),
            ADD CONSTRAINT ck_sales_fiscal_documents_note CHECK (
                (document_type IN ('05','06')) = (related_document_id IS NOT NULL)
                AND (document_type IN ('05','06')) = (note_reason IS NOT NULL)
                AND (note_reason IS NULL OR char_length(btrim(note_reason)) BETWEEN 5 AND 300)
                AND related_document_id IS DISTINCT FROM id
            ),
            ADD CONSTRAINT fk_sales_fiscal_documents_related
                FOREIGN KEY (company_id, related_document_id)
                REFERENCES sales_fiscal_documents (company_id, id) ON DELETE RESTRICT;
        DROP INDEX uq_sales_fiscal_documents_active_sale;
        CREATE UNIQUE INDEX uq_sales_fiscal_documents_active_sale
            ON sales_fiscal_documents (company_id, sale_id)
            WHERE {_ACTIVE} AND document_type IN ('01','03');
        CREATE INDEX ix_sales_fiscal_documents_related
            ON sales_fiscal_documents (company_id, related_document_id)
            WHERE related_document_id IS NOT NULL;
        CREATE TABLE sales_fiscal_note_lines (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            note_id uuid NOT NULL,
            line_number smallint NOT NULL,
            ccf_line_number smallint,
            kind varchar(16) NOT NULL,
            nature varchar(12) NOT NULL,
            description varchar(1000) NOT NULL,
            quantity numeric(18, 6),
            amount numeric(18, 2) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_fiscal_note_lines_number UNIQUE (company_id, note_id, line_number),
            CONSTRAINT fk_sales_fiscal_note_lines_note FOREIGN KEY (company_id, note_id)
                REFERENCES sales_fiscal_documents (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_fiscal_note_lines_kind CHECK (
                kind IN ('return','discount','charge')
                AND nature IN ('taxed','exempt','not_subject')
                AND line_number > 0 AND amount > 0
                AND (ccf_line_number IS NULL OR ccf_line_number > 0)
                AND char_length(btrim(description)) > 0
                AND (kind <> 'return' OR (ccf_line_number IS NOT NULL AND quantity IS NOT NULL AND quantity > 0))
                AND (kind <> 'discount' OR (ccf_line_number IS NOT NULL AND quantity IS NULL))
                AND (kind <> 'charge' OR (quantity IS NOT NULL AND quantity > 0))
            )
        );
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
    notes = (
        op.get_bind()
        .execute(
            text("SELECT count(*) FROM sales_fiscal_documents WHERE document_type IN ('05','06')")
        )
        .scalar()
    )
    if notes:
        raise RuntimeError(
            f"Hay {notes} notas de crédito o de débito guardadas; se conservan diez años y la "
            "migración 0133 no las borra. Respáldalas antes de revertir."
        )
    code, _ = _PERMISSION
    op.execute(f"""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code = '{code}');
        DELETE FROM permissions WHERE code = '{code}';
    """)
    op.execute(f"""
        DROP TABLE sales_fiscal_note_lines;
        DROP INDEX ix_sales_fiscal_documents_related;
        DROP INDEX uq_sales_fiscal_documents_active_sale;
        CREATE UNIQUE INDEX uq_sales_fiscal_documents_active_sale
            ON sales_fiscal_documents (company_id, sale_id) WHERE {_ACTIVE};
        ALTER TABLE sales_fiscal_documents
            DROP CONSTRAINT fk_sales_fiscal_documents_related,
            DROP CONSTRAINT ck_sales_fiscal_documents_note,
            DROP CONSTRAINT ck_sales_fiscal_documents_document,
            ADD CONSTRAINT ck_sales_fiscal_documents_document CHECK (document_type IN ('01','03')),
            DROP COLUMN note_reason,
            DROP COLUMN related_document_id
    """)
