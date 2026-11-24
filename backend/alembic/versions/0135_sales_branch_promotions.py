"""Promociones por sucursal.

Revision ID: 0135
Revises: 0134

Pedido del ingeniero (24/11/2026): un producto puede tener una promoción en una sucursal (por
ejemplo, 10 % en San Miguel). En una línea con promoción el descuento lo fija la promoción: no se
suman el del cliente, el de volumen ni el manual del vendedor, y el documento no admite descuento
global. La promoción nunca deja la línea bajo el costo del kardex.

- ``sales_branch_promotions``: producto, sucursal, porcentaje y vigencia; terminarla la cierra
  (``ended_at``) sin borrarla.
- Las líneas de cotización y de pedido aceptan la fuente de descuento ``promotion``.
- Permiso ``sales_promotions:manage``.
"""

from alembic import op
from sqlalchemy import text

revision = "0135"
down_revision = "0134"
branch_labels = None
depends_on = None

_PERMISSION = ("sales_promotions:manage", "Crear y terminar promociones por sucursal")
_SOURCES_OLD = "('none','customer','volume')"
_SOURCES_NEW = "('none','customer','volume','promotion')"
_LINES = (
    ("sales_quotation_lines", "ck_sales_quotation_lines_discounts"),
    ("sales_lines", "ck_sales_lines_discounts"),
)


def _discount_check(sources: str) -> str:
    return (
        "discount_percent >= 0 AND discount_percent <= 100 "
        "AND suggested_discount_percent >= 0 AND suggested_discount_percent <= 100 "
        f"AND suggested_discount_source IN {sources}"
    )


def upgrade() -> None:
    op.execute("""
        CREATE TABLE sales_branch_promotions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
            branch_id uuid NOT NULL,
            product_id integer NOT NULL,
            discount_percent numeric(5, 2) NOT NULL,
            valid_from date NOT NULL,
            valid_to date,
            notes varchar(200),
            created_by uuid REFERENCES users (id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            ended_by uuid REFERENCES users (id) ON DELETE SET NULL,
            ended_at timestamptz,
            CONSTRAINT fk_sales_branch_promotions_branch FOREIGN KEY (branch_id, company_id)
                REFERENCES branches (id, company_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sales_branch_promotions_product FOREIGN KEY (company_id, product_id)
                REFERENCES products (company_id, id_product) ON DELETE RESTRICT,
            CONSTRAINT ck_sales_branch_promotions_percent
                CHECK (discount_percent > 0 AND discount_percent < 100),
            CONSTRAINT ck_sales_branch_promotions_validity
                CHECK (valid_to IS NULL OR valid_to >= valid_from)
        );
        CREATE INDEX ix_sales_branch_promotions_lookup
            ON sales_branch_promotions (company_id, branch_id, product_id, valid_from)
            WHERE ended_at IS NULL;
    """)
    for table, name in _LINES:
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT {name}, "
            f"ADD CONSTRAINT {name} CHECK ({_discount_check(_SOURCES_NEW)})"
        )
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
    stored = bind.execute(text("SELECT count(*) FROM sales_branch_promotions")).scalar()
    used = sum(
        bind.execute(
            text(f"SELECT count(*) FROM {table} WHERE suggested_discount_source = 'promotion'")
        ).scalar()
        or 0
        for table, _name in _LINES
    )
    if stored or used:
        raise RuntimeError(
            f"Hay {stored} promociones y {used} líneas de venta con descuento de promoción; la "
            "migración 0135 los perdería. Respáldalos antes de revertir."
        )
    code, _ = _PERMISSION
    op.execute(f"""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code = '{code}');
        DELETE FROM permissions WHERE code = '{code}';
    """)
    for table, name in _LINES:
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT {name}, "
            f"ADD CONSTRAINT {name} CHECK ({_discount_check(_SOURCES_OLD)})"
        )
    op.execute("DROP TABLE sales_branch_promotions")
