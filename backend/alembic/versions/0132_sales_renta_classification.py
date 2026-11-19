"""Clasificación de renta de cada documento de venta.

Revision ID: 0132
Revises: 0131

Desde el período de enero de 2025 los anexos de ventas del F-07 llevan, por documento, el tipo de
operación y el tipo de ingreso para renta (Manual de anexos del F-07 V14). El DTE no los lleva: se
eligen al facturar y el ERP los guarda.

- ``company_economic_activities``: la clasificación sugerida para las ventas de esa actividad.
- ``sales_fiscal_documents``: la clasificación del documento. Los emitidos antes quedan vacíos.
"""

from alembic import op

revision = "0132"
down_revision = "0131"
branch_labels = None
depends_on = None

_OPERATION = "(1, 2, 3, 4, 12, 13)"
_INCOME = "(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13)"


def _check(table: str) -> str:
    return f"""
        ALTER TABLE {table}
            ADD COLUMN renta_operation_type smallint,
            ADD COLUMN renta_income_type smallint,
            ADD CONSTRAINT ck_{table}_renta CHECK (
                (renta_operation_type IS NULL) = (renta_income_type IS NULL)
                AND (renta_operation_type IS NULL OR renta_operation_type IN {_OPERATION})
                AND (renta_income_type IS NULL OR renta_income_type IN {_INCOME})
                AND (renta_operation_type NOT IN (12, 13) OR renta_income_type = renta_operation_type)
                AND (renta_income_type NOT IN (12, 13) OR renta_income_type = renta_operation_type)
            )
    """


def upgrade() -> None:
    op.execute(_check("company_economic_activities"))
    op.execute(_check("sales_fiscal_documents"))


def downgrade() -> None:
    for table in ("sales_fiscal_documents", "company_economic_activities"):
        op.execute(f"""
            ALTER TABLE {table}
                DROP CONSTRAINT ck_{table}_renta,
                DROP COLUMN renta_income_type,
                DROP COLUMN renta_operation_type
        """)
