"""Add catalog, products, countries and suppliers tables.

Revision ID: 0020
Revises: 0019
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. countries
    op.create_table(
        "countries",
        sa.Column("id_country", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("iso_code_2", sa.String(length=2), nullable=False),
        sa.Column("iso_code_3", sa.String(length=3), nullable=False),
        sa.Column("phone_code", sa.String(length=10), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id_country"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("iso_code_2"),
        sa.UniqueConstraint("iso_code_3"),
    )
    op.create_index("ix_countries_name", "countries", ["name"])

    # 2. categories
    op.create_table(
        "categories",
        sa.Column("id_category", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id_category"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index("ix_categories_name", "categories", ["name"])
    op.create_index("ix_categories_uuid", "categories", ["uuid"])

    # 3. sub_categories
    op.create_table(
        "sub_categories",
        sa.Column("id_sub_category", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_category", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["id_category"], ["categories.id_category"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id_sub_category"),
    )
    op.create_index("ix_sub_categories_id_category", "sub_categories", ["id_category"])
    op.create_index("ix_sub_categories_name", "sub_categories", ["name"])

    # 4. units
    op.create_table(
        "units",
        sa.Column("id_unit", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id_unit"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_units_name", "units", ["name"])
    op.create_index("ix_units_type", "units", ["type"])

    # 5. products
    op.create_table(
        "products",
        sa.Column("id_product", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("id_category", sa.Integer(), nullable=False),
        sa.Column("id_sub_category", sa.Integer(), nullable=True),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("original_code", sa.String(length=100), nullable=True),
        sa.Column("internal_code", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("size", sa.String(length=50), nullable=True),
        sa.Column("dimensions", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("presentation", sa.String(length=100), nullable=True),
        sa.Column("purchase_unit", sa.Integer(), nullable=False),
        sa.Column("sale_unit", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["id_category"], ["categories.id_category"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["id_sub_category"], ["sub_categories.id_sub_category"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["purchase_unit"], ["units.id_unit"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sale_unit"], ["units.id_unit"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id_product"),
        sa.UniqueConstraint("sku"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index("ix_products_id_category", "products", ["id_category"])
    op.create_index("ix_products_id_sub_category", "products", ["id_sub_category"])
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_sku", "products", ["sku"])
    op.create_index("ix_products_uuid", "products", ["uuid"])

    # 6. suppliers
    op.create_table(
        "suppliers",
        sa.Column("id_supplier", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("country_id", sa.Integer(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("website", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id_country"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id_supplier"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index("ix_suppliers_code", "suppliers", ["code"])
    op.create_index("ix_suppliers_country_id", "suppliers", ["country_id"])
    op.create_index("ix_suppliers_name", "suppliers", ["name"])
    op.create_index("ix_suppliers_uuid", "suppliers", ["uuid"])

    # 7. supplier_contacts
    op.create_table(
        "supplier_contacts",
        sa.Column("id_supplier_contact", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_supplier", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["id_supplier"], ["suppliers.id_supplier"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_supplier_contact"),
    )
    op.create_index("ix_supplier_contacts_id_supplier", "supplier_contacts", ["id_supplier"])


def downgrade() -> None:
    op.drop_table("supplier_contacts")
    op.drop_table("suppliers")
    op.drop_table("products")
    op.drop_table("units")
    op.drop_table("sub_categories")
    op.drop_table("categories")
    op.drop_table("countries")
