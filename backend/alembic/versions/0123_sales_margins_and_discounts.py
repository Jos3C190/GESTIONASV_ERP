"""Margen objetivo, descuento del cliente, escalas por volumen y topes de descuento por rol.

Revision ID: 0123
Revises: 0122

Bloque V2c del área de Ventas. El margen se mide sobre el precio sin IVA:
(precio - costo) ÷ precio. El costo sale de ``inventory_cost_averages``, que ya incluye el
retaceo.

El downgrade se niega si hay márgenes, escalas, políticas o descuentos de cliente guardados.
"""

from alembic import op
from sqlalchemy import text

revision = "0123"
down_revision = "0122"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("sales_costs:read", "Ver el costo y el margen de los precios de venta"),
    ("sales_discounts:manage", "Configurar los topes de descuento por rol"),
)
_NO_ID = "'00000000-0000-0000-0000-000000000000'::uuid"


def upgrade() -> None:
    op.execute("""
        ALTER TABLE sales_price_lists
            ADD COLUMN target_margin_percent numeric(5, 2),
            ADD CONSTRAINT ck_sales_price_lists_target_margin CHECK (
                target_margin_percent IS NULL
                OR (target_margin_percent >= 0 AND target_margin_percent <= 95)
            )
    """)
    op.execute("""
        CREATE TABLE sales_price_list_category_margins (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            price_list_id uuid NOT NULL,
            category_id integer NOT NULL,
            target_margin_percent numeric(5, 2) NOT NULL,
            updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_sales_category_margins_list FOREIGN KEY (company_id, price_list_id)
                REFERENCES sales_price_lists (company_id, id) ON DELETE CASCADE,
            CONSTRAINT fk_sales_category_margins_category FOREIGN KEY (category_id, company_id)
                REFERENCES categories (id_category, company_id) ON DELETE RESTRICT,
            CONSTRAINT uq_sales_category_margins UNIQUE (price_list_id, category_id),
            CONSTRAINT ck_sales_category_margins_percent
                CHECK (target_margin_percent >= 0 AND target_margin_percent <= 95)
        )
    """)
    op.execute("""
        ALTER TABLE sales_customers
            ADD COLUMN discount_percent numeric(5, 2) NOT NULL DEFAULT 0,
            ADD CONSTRAINT ck_sales_customers_discount
                CHECK (discount_percent >= 0 AND discount_percent <= 100)
    """)
    op.execute(f"""
        CREATE TABLE sales_volume_discounts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            price_list_id uuid NOT NULL,
            product_id integer NOT NULL,
            variant_id uuid,
            unit_id integer NOT NULL,
            min_quantity numeric(18, 6) NOT NULL,
            discount_percent numeric(5, 2) NOT NULL,
            valid_from date NOT NULL,
            valid_to date,
            created_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_sales_volume_discounts_list FOREIGN KEY (company_id, price_list_id)
                REFERENCES sales_price_lists (company_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_volume_discounts_product FOREIGN KEY (company_id, product_id)
                REFERENCES products (company_id, id_product) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_volume_discounts_variant
                FOREIGN KEY (company_id, product_id, variant_id)
                REFERENCES product_variants (company_id, product_id, id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_volume_discounts_unit FOREIGN KEY (company_id, unit_id)
                REFERENCES company_units (company_id, unit_id) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_volume_discounts_quantity CHECK (min_quantity > 0),
            CONSTRAINT ck_sales_volume_discounts_percent
                CHECK (discount_percent > 0 AND discount_percent <= 100),
            CONSTRAINT ck_sales_volume_discounts_validity
                CHECK (valid_to IS NULL OR valid_to >= valid_from),
            CONSTRAINT ex_sales_volume_discounts_overlap EXCLUDE USING gist (
                price_list_id WITH =,
                product_id WITH =,
                (COALESCE(variant_id, {_NO_ID})) WITH =,
                unit_id WITH =,
                min_quantity WITH =,
                daterange(valid_from, valid_to, '[]') WITH &&
            )
        )
    """)
    op.execute("""
        CREATE INDEX ix_sales_volume_discounts_lookup
            ON sales_volume_discounts (company_id, price_list_id, product_id, unit_id)
    """)
    op.execute("""
        CREATE TABLE sales_discount_policies (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            role_id uuid NOT NULL REFERENCES roles (id) ON DELETE CASCADE,
            max_line_discount_percent numeric(5, 2) NOT NULL DEFAULT 0,
            max_global_discount_percent numeric(5, 2) NOT NULL DEFAULT 0,
            can_sell_below_cost boolean NOT NULL DEFAULT false,
            updated_by uuid REFERENCES users (id) ON DELETE SET NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sales_discount_policies_role UNIQUE (company_id, role_id),
            CONSTRAINT ck_sales_discount_policies_line
                CHECK (max_line_discount_percent >= 0 AND max_line_discount_percent <= 100),
            CONSTRAINT ck_sales_discount_policies_global
                CHECK (max_global_discount_percent >= 0 AND max_global_discount_percent <= 100)
        )
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
    stored = (
        op.get_bind()
        .execute(
            text(
                "SELECT (SELECT count(*) FROM sales_price_list_category_margins)"
                " + (SELECT count(*) FROM sales_volume_discounts)"
                " + (SELECT count(*) FROM sales_discount_policies)"
                " + (SELECT count(*) FROM sales_customers WHERE discount_percent > 0)"
                " + (SELECT count(*) FROM sales_price_lists"
                "    WHERE target_margin_percent IS NOT NULL)"
            )
        )
        .scalar()
    )
    if stored:
        raise RuntimeError(
            f"Hay {stored} márgenes, escalas, topes o descuentos de cliente que se perderían; "
            "elimínalos antes de revertir la migración 0123."
        )
    for code, _ in _PERMISSIONS:
        op.execute(f"""
            DELETE FROM role_permissions WHERE permission_id IN
              (SELECT id FROM permissions WHERE code = '{code}');
            DELETE FROM permissions WHERE code = '{code}';
        """)
    op.execute("DROP TABLE sales_discount_policies")
    op.execute("DROP TABLE sales_volume_discounts")
    op.execute("ALTER TABLE sales_customers DROP COLUMN discount_percent")
    op.execute("DROP TABLE sales_price_list_category_margins")
    op.execute("ALTER TABLE sales_price_lists DROP COLUMN target_margin_percent")
