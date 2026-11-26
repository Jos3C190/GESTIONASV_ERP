"""Cambio de producto: pedido vinculado a una devolución.

Revision ID: 0143
Revises: 0142

Bloque V8b1 del área de Ventas. El cliente devuelve mercadería (B08, con su nota o retorno de V8a) y se
lleva otro producto: el pedido nuevo guarda la devolución que cambia (``sales.exchange_return_id``). A lo
sumo un pedido de cambio no cancelado por devolución.
"""

from alembic import op
from sqlalchemy import text

revision = "0143"
down_revision = "0142"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE sales ADD COLUMN exchange_return_id uuid;
        ALTER TABLE sales ADD CONSTRAINT fk_sales_exchange_return
            FOREIGN KEY (company_id, exchange_return_id)
            REFERENCES sales_returns (company_id, id) ON DELETE RESTRICT;
        CREATE UNIQUE INDEX uq_sales_exchange_return_active
            ON sales (company_id, exchange_return_id)
            WHERE exchange_return_id IS NOT NULL AND status <> 'cancelled';
    """)


def downgrade() -> None:
    bind = op.get_bind()
    linked = bind.execute(
        text("SELECT count(*) FROM sales WHERE exchange_return_id IS NOT NULL")
    ).scalar()
    if linked:
        raise RuntimeError(
            f"Hay {linked} pedidos de cambio vinculados a devoluciones; la migración 0143 no los "
            "borra. Respáldalos antes de revertir."
        )
    op.execute("""
        DROP INDEX uq_sales_exchange_return_active;
        ALTER TABLE sales DROP CONSTRAINT fk_sales_exchange_return;
        ALTER TABLE sales DROP COLUMN exchange_return_id;
    """)
