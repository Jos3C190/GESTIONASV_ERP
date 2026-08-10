"""Enforce company-safe product unit references.

Revision ID: 0024
Revises: 0023
"""

from __future__ import annotations

from alembic import op


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    missing = connection.exec_driver_sql(
        """
        SELECT count(*) FROM products p
        WHERE NOT EXISTS (
            SELECT 1 FROM company_units cu
            WHERE cu.company_id=p.company_id AND cu.unit_id=p.purchase_unit
        ) OR NOT EXISTS (
            SELECT 1 FROM company_units cu
            WHERE cu.company_id=p.company_id AND cu.unit_id=p.sale_unit
        )
        """
    ).scalar_one()
    if missing:
        raise RuntimeError("Products contain unit references unavailable to their company.")

    op.drop_constraint("products_purchase_unit_fkey", "products", type_="foreignkey")
    op.drop_constraint("products_sale_unit_fkey", "products", type_="foreignkey")
    op.create_foreign_key(
        "fk_products_company_purchase_unit",
        "products",
        "company_units",
        ["company_id", "purchase_unit"],
        ["company_id", "unit_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_products_company_sale_unit",
        "products",
        "company_units",
        ["company_id", "sale_unit"],
        ["company_id", "unit_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_products_company_sale_unit", "products", type_="foreignkey")
    op.drop_constraint("fk_products_company_purchase_unit", "products", type_="foreignkey")
    op.create_foreign_key(
        "products_purchase_unit_fkey", "products", "units", ["purchase_unit"], ["id_unit"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "products_sale_unit_fkey", "products", "units", ["sale_unit"], ["id_unit"], ondelete="RESTRICT"
    )
