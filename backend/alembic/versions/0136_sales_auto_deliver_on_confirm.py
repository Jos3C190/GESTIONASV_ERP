"""Salida de existencias al confirmar el pedido.

Revision ID: 0136
Revises: 0135

Pedido del ingeniero (24/11/2026): al confirmar la venta se descuenta la existencia y la salida
queda en el kardex. ``sales_settings.auto_deliver_on_confirm`` (encendido por omisión) lo activa
por empresa; una empresa que despacha después puede apagarlo y entregar con «Preparar entrega».
"""

from alembic import op

revision = "0136"
down_revision = "0135"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE sales_settings "
        "ADD COLUMN auto_deliver_on_confirm boolean NOT NULL DEFAULT true"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE sales_settings DROP COLUMN auto_deliver_on_confirm")
