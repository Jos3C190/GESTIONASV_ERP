"""Control de crédito y gestión de cobro.

Revision ID: 0141
Revises: 0140

Bloque V5b del área de Ventas.

- ``sales_customers``: bloqueo manual de crédito con motivo, quién y cuándo.
- ``sales_settings.credit_overdue_grace_days``: días de gracia tras el vencimiento antes de que el
  saldo vencido detenga los pedidos a crédito.
- ``sales_collection_notes``: notas de seguimiento de cobro por cliente, con próxima acción.
- Permiso ``sales_credit:authorize``: autorizar pedidos a crédito fuera de cupo, con mora o de un
  cliente bloqueado, y bloquear o desbloquear clientes.

Los motivos de crédito se guardan en ``sales.authorization_reasons`` junto a los de descuento.
"""

from alembic import op
from sqlalchemy import text

revision = "0141"
down_revision = "0140"
branch_labels = None
depends_on = None

_PERMISSION = (
    "sales_credit:authorize",
    "Autorizar pedidos a crédito fuera de cupo o con mora y bloquear clientes",
)


def upgrade() -> None:
    op.execute("""
        ALTER TABLE sales_customers
            ADD COLUMN credit_blocked boolean NOT NULL DEFAULT false,
            ADD COLUMN credit_block_reason varchar(300),
            ADD COLUMN credit_blocked_by_id uuid REFERENCES users (id) ON DELETE RESTRICT,
            ADD COLUMN credit_blocked_at timestamptz,
            ADD CONSTRAINT ck_sales_customers_credit_block CHECK (
                (NOT credit_blocked AND credit_block_reason IS NULL
                 AND credit_blocked_by_id IS NULL AND credit_blocked_at IS NULL)
                OR (credit_blocked AND length(btrim(credit_block_reason)) >= 5
                    AND credit_blocked_by_id IS NOT NULL AND credit_blocked_at IS NOT NULL)
            );
        ALTER TABLE sales_settings
            ADD COLUMN credit_overdue_grace_days smallint NOT NULL DEFAULT 0,
            ADD CONSTRAINT ck_sales_settings_credit_grace
                CHECK (credit_overdue_grace_days BETWEEN 0 AND 365);
        CREATE TABLE sales_collection_notes (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            customer_id uuid NOT NULL,
            note varchar(1000) NOT NULL CHECK (length(btrim(note)) >= 5),
            next_action_on date,
            created_by_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_sales_collection_notes_customer FOREIGN KEY (company_id, customer_id)
                REFERENCES sales_customers (company_id, id) ON DELETE RESTRICT
        );
        CREATE INDEX ix_sales_collection_notes_customer
            ON sales_collection_notes (company_id, customer_id, created_at DESC);
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
    bind = op.get_bind()
    notes = bind.execute(text("SELECT count(*) FROM sales_collection_notes")).scalar()
    blocked = bind.execute(
        text("SELECT count(*) FROM sales_customers WHERE credit_blocked")
    ).scalar()
    if notes or blocked:
        raise RuntimeError(
            f"Hay {notes} notas de cobro y {blocked} clientes bloqueados; la migración 0141 no los "
            "borra. Respáldalos antes de revertir."
        )
    code, _ = _PERMISSION
    op.execute(f"""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code = '{code}');
        DELETE FROM permissions WHERE code = '{code}';
    """)
    op.execute("""
        DROP TABLE sales_collection_notes;
        ALTER TABLE sales_settings
            DROP CONSTRAINT ck_sales_settings_credit_grace,
            DROP COLUMN credit_overdue_grace_days;
        ALTER TABLE sales_customers
            DROP CONSTRAINT ck_sales_customers_credit_block,
            DROP COLUMN credit_blocked_at,
            DROP COLUMN credit_blocked_by_id,
            DROP COLUMN credit_block_reason,
            DROP COLUMN credit_blocked;
    """)
