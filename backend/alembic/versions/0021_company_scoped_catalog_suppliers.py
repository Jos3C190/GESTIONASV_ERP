"""Scope product catalogues and suppliers to a company.

Revision ID: 0021
Revises: 0020
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


TENANT_TABLES = ("categories", "sub_categories", "products", "suppliers")


def _backfill_company() -> None:
    connection = op.get_bind()
    company_ids = list(connection.execute(sa.text("SELECT id FROM companies ORDER BY created_at, id")).scalars())
    existing_rows = sum(
        int(connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one())
        for table in TENANT_TABLES
    )
    if existing_rows and len(company_ids) != 1:
        raise RuntimeError(
            "Catalogues/suppliers contain data and cannot be assigned safely: "
            "the migration requires exactly one company. Run the tenant mapping command first."
        )
    if not company_ids:
        return
    company_id = company_ids[0]
    connection.execute(
        sa.text("UPDATE categories SET company_id=:company_id WHERE company_id IS NULL"),
        {"company_id": company_id},
    )
    connection.execute(
        sa.text(
            "UPDATE sub_categories sc SET company_id=c.company_id FROM categories c "
            "WHERE sc.id_category=c.id_category AND sc.company_id IS NULL"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE products p SET company_id=c.company_id FROM categories c "
            "WHERE p.id_category=c.id_category AND p.company_id IS NULL"
        )
    )
    connection.execute(
        sa.text("UPDATE suppliers SET company_id=:company_id WHERE company_id IS NULL"),
        {"company_id": company_id},
    )


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.add_column(table, sa.Column("company_id", UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_company_id_companies",
            table,
            "companies",
            ["company_id"],
            ["id"],
            ondelete="CASCADE",
        )

    _backfill_company()

    for table in TENANT_TABLES:
        op.alter_column(table, "company_id", nullable=False)
        op.create_index(f"ix_{table}_company_id", table, ["company_id"])

    op.drop_constraint("categories_name_key", "categories", type_="unique")
    op.drop_constraint("products_sku_key", "products", type_="unique")
    op.drop_constraint("suppliers_code_key", "suppliers", type_="unique")

    op.create_unique_constraint("uq_categories_company_name", "categories", ["company_id", "name"])
    op.create_unique_constraint(
        "uq_subcategories_company_category_name",
        "sub_categories",
        ["company_id", "id_category", "name"],
    )
    op.create_unique_constraint("uq_products_company_sku", "products", ["company_id", "sku"])
    op.create_unique_constraint("uq_suppliers_company_code", "suppliers", ["company_id", "code"])
    op.create_unique_constraint("uq_categories_id_company", "categories", ["id_category", "company_id"])
    op.create_unique_constraint(
        "uq_subcategories_id_company_category",
        "sub_categories",
        ["id_sub_category", "company_id", "id_category"],
    )

    op.create_index("ix_categories_company_active_name", "categories", ["company_id", "is_active", "name"])
    op.create_index(
        "ix_subcategories_company_category_active",
        "sub_categories",
        ["company_id", "id_category", "is_active"],
    )
    op.create_index("ix_products_company_active_name", "products", ["company_id", "is_active", "name"])
    op.create_index("ix_suppliers_company_active_name", "suppliers", ["company_id", "is_active", "name"])


def downgrade() -> None:
    op.drop_index("ix_suppliers_company_active_name", table_name="suppliers")
    op.drop_index("ix_products_company_active_name", table_name="products")
    op.drop_index("ix_subcategories_company_category_active", table_name="sub_categories")
    op.drop_index("ix_categories_company_active_name", table_name="categories")
    op.drop_constraint("uq_subcategories_id_company_category", "sub_categories", type_="unique")
    op.drop_constraint("uq_categories_id_company", "categories", type_="unique")
    op.drop_constraint("uq_suppliers_company_code", "suppliers", type_="unique")
    op.drop_constraint("uq_products_company_sku", "products", type_="unique")
    op.drop_constraint("uq_subcategories_company_category_name", "sub_categories", type_="unique")
    op.drop_constraint("uq_categories_company_name", "categories", type_="unique")
    op.create_unique_constraint("categories_name_key", "categories", ["name"])
    op.create_unique_constraint("products_sku_key", "products", ["sku"])
    op.create_unique_constraint("suppliers_code_key", "suppliers", ["code"])
    for table in reversed(TENANT_TABLES):
        op.drop_index(f"ix_{table}_company_id", table_name=table)
        op.drop_constraint(f"fk_{table}_company_id_companies", table, type_="foreignkey")
        op.drop_column(table, "company_id")
