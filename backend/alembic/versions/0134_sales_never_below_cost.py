"""Nunca se vende bajo el costo del kardex.

Revision ID: 0134
Revises: 0133

Pedido del ingeniero (24/11/2026): el precio de venta nunca puede quedar por debajo del costo
promedio del kardex, ni con descuentos. Deja de ser un motivo de autorización y pasa a ser un
bloqueo sin excepción, así que se retira el permiso de rol «Puede vender bajo costo».
"""

from alembic import op

revision = "0134"
down_revision = "0133"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sales_discount_policies DROP COLUMN can_sell_below_cost")


def downgrade() -> None:
    # Vuelve el permiso apagado para todos los roles: nadie queda autorizado a vender bajo costo.
    op.execute(
        "ALTER TABLE sales_discount_policies "
        "ADD COLUMN can_sell_below_cost boolean NOT NULL DEFAULT false"
    )
