"""Listas de precios de venta por empresa, con vigencia y precio por sucursal.

Revision ID: 0122
Revises: 0121

Bloque V2b del área de Ventas. Un precio no se edita: un cambio cierra la vigencia anterior y
abre otra, de modo que el historial queda completo. Una restricción de exclusión impide que dos
precios de la misma lista, producto, variante, unidad y sucursal se traslapen en el tiempo.

El downgrade se niega si hay listas de precios guardadas.
"""

from alembic import op
from sqlalchemy import text

revision = "0122"
down_revision = "0121"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("price_lists:read", "Consultar listas de precios de venta"),
    ("price_lists:manage", "Gestionar listas de precios y sus precios"),
)
_NO_ID = "'00000000-0000-0000-0000-000000000000'::uuid"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("""
        CREATE TABLE sales_price_lists (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            code varchar(20) NOT NULL,
            name varchar(120) NOT NULL,
            description text,
            prices_include_vat boolean NOT NULL,
            is_default boolean NOT NULL DEFAULT false,
            is_active boolean NOT NULL DEFAULT true,
            created_by uuid REFERENCES users (id) ON DELETE SET NULL,
            updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_price_lists_company_id UNIQUE (company_id, id),
            CONSTRAINT uq_sales_price_lists_code UNIQUE (company_id, code),
            CONSTRAINT ck_sales_price_lists_code CHECK (code ~ '^[A-Z0-9][A-Z0-9-]{0,19}$'),
            CONSTRAINT ck_sales_price_lists_name CHECK (char_length(btrim(name)) >= 2),
            CONSTRAINT ck_sales_price_lists_default_active CHECK (NOT is_default OR is_active)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_sales_price_lists_default
            ON sales_price_lists (company_id) WHERE is_default
    """)
    op.execute(f"""
        CREATE TABLE sales_price_list_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            price_list_id uuid NOT NULL,
            product_id integer NOT NULL,
            variant_id uuid,
            unit_id integer NOT NULL,
            branch_id uuid,
            price numeric(19, 8) NOT NULL,
            valid_from date NOT NULL,
            valid_to date,
            created_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_sales_price_list_items_list FOREIGN KEY (company_id, price_list_id)
                REFERENCES sales_price_lists (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_price_list_items_product FOREIGN KEY (company_id, product_id)
                REFERENCES products (company_id, id_product) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_price_list_items_variant FOREIGN KEY (company_id, product_id, variant_id)
                REFERENCES product_variants (company_id, product_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_price_list_items_unit FOREIGN KEY (company_id, unit_id)
                REFERENCES company_units (company_id, unit_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_price_list_items_branch FOREIGN KEY (branch_id, company_id)
                REFERENCES branches (id, company_id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_price_list_items_price CHECK (price >= 0),
            CONSTRAINT ck_sales_price_list_items_validity
                CHECK (valid_to IS NULL OR valid_to >= valid_from),
            CONSTRAINT ex_sales_price_list_items_overlap EXCLUDE USING gist (
                price_list_id WITH =,
                product_id WITH =,
                (COALESCE(variant_id, {_NO_ID})) WITH =,
                unit_id WITH =,
                (COALESCE(branch_id, {_NO_ID})) WITH =,
                daterange(valid_from, valid_to, '[]') WITH &&
            )
        )
    """)
    op.execute("""
        CREATE INDEX ix_sales_price_list_items_lookup
            ON sales_price_list_items (company_id, price_list_id, product_id, unit_id, valid_from)
    """)
    op.execute("""
        ALTER TABLE sales_customers
            ADD COLUMN price_list_id uuid,
            ADD CONSTRAINT fk_sales_customers_price_list FOREIGN KEY (company_id, price_list_id)
                REFERENCES sales_price_lists (company_id, id) ON DELETE RESTRICT
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
    stored = op.get_bind().execute(text("SELECT count(*) FROM sales_price_lists")).scalar()
    if stored:
        raise RuntimeError(
            f"Hay {stored} listas de precios que se perderían; "
            "elimínalas antes de revertir la migración 0122."
        )
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE FROM role_permissions WHERE permission_id IN
              (SELECT id FROM permissions WHERE code = '{code}');
            DELETE FROM permissions WHERE code = '{code}';
        """)
    op.execute("ALTER TABLE sales_customers DROP COLUMN price_list_id")
    op.execute("DROP TABLE sales_price_list_items")
    op.execute("DROP TABLE sales_price_lists")
