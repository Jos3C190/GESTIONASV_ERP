"""Clasificación fiscal de productos y código de Hacienda de las unidades por empresa.

Revision ID: 0120
Revises: 0119

Cada producto declara su tratamiento de IVA (gravado, exento o no sujeto), un tipo de ítem
opcional (CAT-011; si falta se deriva del tipo de producto) y los tributos adicionales que
lleva (CAT-015, sin el IVA 20 ni el C3). Cada unidad habilitada en una empresa recibe su
código de unidad de medida de Hacienda (CAT-014); las filas existentes toman el valor
sugerido según el código de la unidad.

El downgrade se niega si algún producto dejó de ser gravado o tiene tributos o tipo de ítem.
"""

from alembic import op
from sqlalchemy import text

revision = "0120"
down_revision = "0119"
branch_labels = None
depends_on = None

#: Sugerencia de CAT-014 por código de unidad del ERP; las demás quedan como «Otra» (99).
SUGGESTED_UNIT_CODES = {
    "UNIT": "59",
    "KILOGRAM": "34",
    "GRAM": "39",
    "POUND": "36",
    "LITER": "23",
    "MILLILITER": "26",
    "GALLON": "22",
    "METER": "1",
}
_PERMISSION = ("products:fiscal", "Gestionar la clasificación fiscal del producto")


def upgrade() -> None:
    op.execute("""
        ALTER TABLE products
            ADD COLUMN tax_treatment varchar(16) NOT NULL DEFAULT 'taxed',
            ADD COLUMN dte_item_type varchar(1),
            ADD COLUMN additional_tax_codes varchar(4)[] NOT NULL DEFAULT '{}',
            ADD CONSTRAINT ck_products_tax_treatment
                CHECK (tax_treatment IN ('taxed','exempt','not_subject')),
            ADD CONSTRAINT ck_products_dte_item_type
                CHECK (dte_item_type IS NULL OR dte_item_type IN ('1','2','3')),
            ADD CONSTRAINT ck_products_additional_taxes_taxed
                CHECK (tax_treatment = 'taxed' OR cardinality(additional_tax_codes) = 0),
            ADD CONSTRAINT ck_products_additional_taxes_not_iva
                CHECK (NOT (additional_tax_codes && ARRAY['20','C3']::varchar(4)[]))
    """)
    op.execute("""
        ALTER TABLE company_units
            ADD COLUMN hacienda_unit_code varchar(2),
            ADD CONSTRAINT ck_company_units_hacienda_unit_code
                CHECK (hacienda_unit_code IS NULL OR hacienda_unit_code ~ '^[0-9]{1,2}$')
    """)
    connection = op.get_bind()
    connection.execute(text("UPDATE company_units SET hacienda_unit_code = '99'"))
    for unit_code, hacienda_code in SUGGESTED_UNIT_CODES.items():
        connection.execute(
            text("""
                UPDATE company_units cu SET hacienda_unit_code = :hacienda
                  FROM units u
                 WHERE u.id_unit = cu.unit_id AND upper(u.code) = :code
            """),
            {"hacienda": hacienda_code, "code": unit_code},
        )
    code, description = _PERMISSION
    op.execute(f"""
        INSERT INTO permissions (id, code, description, module, created_at)
        VALUES (gen_random_uuid(), '{code}', '{description}', 'products', now())
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
    classified = (
        op.get_bind()
        .execute(
            text("""
                SELECT count(*) FROM products
                 WHERE tax_treatment <> 'taxed' OR dte_item_type IS NOT NULL
                    OR cardinality(additional_tax_codes) > 0
            """)
        )
        .scalar()
    )
    if classified:
        raise RuntimeError(
            f"Hay {classified} productos con clasificación fiscal que se perdería; "
            "vuelve a dejarlos gravados y sin tributos antes de revertir la migración 0120."
        )
    code, _ = _PERMISSION
    op.execute(f"""
        DELETE FROM role_permissions WHERE permission_id IN
          (SELECT id FROM permissions WHERE code = '{code}');
        DELETE FROM permissions WHERE code = '{code}';
    """)
    op.execute("ALTER TABLE company_units DROP COLUMN hacienda_unit_code")
    op.execute("""
        ALTER TABLE products
            DROP COLUMN additional_tax_codes,
            DROP COLUMN dte_item_type,
            DROP COLUMN tax_treatment
    """)
