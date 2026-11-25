"""Nota de remisión al despachar un traslado.

Revision ID: 0137
Revises: 0136

Bloque V4d del área de Ventas. La nota de remisión (04) ampara la circulación de los bienes que
salen en un traslado entre bodegas de la misma empresa (Código Tributario, art. 109).

- ``sales_fiscal_documents`` admite el tipo 04. La nota pertenece a un traslado
  (``transfer_id``) y no a un pedido: ``sale_id`` pasa a ser opcional. Los demás tipos siguen
  exigiendo su pedido.
- Un traslado tiene a lo sumo una nota vigente (pendiente, en contingencia, emitida o simulada y
  sin reemplazo).
"""

from alembic import op
from sqlalchemy import text

revision = "0137"
down_revision = "0136"
branch_labels = None
depends_on = None

_ACTIVE = "status IN ('pending','contingency','issued','simulated') AND superseded_by_id IS NULL"


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE sales_fiscal_documents
            ADD COLUMN transfer_id uuid,
            ALTER COLUMN sale_id DROP NOT NULL,
            DROP CONSTRAINT ck_sales_fiscal_documents_document,
            ADD CONSTRAINT ck_sales_fiscal_documents_document
                CHECK (document_type IN ('01','03','04','05','06')),
            ADD CONSTRAINT ck_sales_fiscal_documents_origin CHECK (
                (document_type = '04') = (transfer_id IS NOT NULL)
                AND (document_type = '04') = (sale_id IS NULL)
            ),
            ADD CONSTRAINT fk_sales_fiscal_documents_transfer
                FOREIGN KEY (company_id, transfer_id)
                REFERENCES inventory_transfers (company_id, id) ON DELETE RESTRICT;
        CREATE UNIQUE INDEX uq_sales_fiscal_documents_active_transfer
            ON sales_fiscal_documents (company_id, transfer_id)
            WHERE {_ACTIVE} AND document_type = '04';
    """)


def downgrade() -> None:
    notes = (
        op.get_bind()
        .execute(text("SELECT count(*) FROM sales_fiscal_documents WHERE document_type = '04'"))
        .scalar()
    )
    if notes:
        raise RuntimeError(
            f"Hay {notes} notas de remisión guardadas; se conservan diez años y la migración 0137 "
            "no las borra. Respáldalas antes de revertir."
        )
    op.execute("""
        DROP INDEX uq_sales_fiscal_documents_active_transfer;
        ALTER TABLE sales_fiscal_documents
            DROP CONSTRAINT fk_sales_fiscal_documents_transfer,
            DROP CONSTRAINT ck_sales_fiscal_documents_origin,
            DROP CONSTRAINT ck_sales_fiscal_documents_document,
            ADD CONSTRAINT ck_sales_fiscal_documents_document
                CHECK (document_type IN ('01','03','05','06')),
            ALTER COLUMN sale_id SET NOT NULL,
            DROP COLUMN transfer_id
    """)
