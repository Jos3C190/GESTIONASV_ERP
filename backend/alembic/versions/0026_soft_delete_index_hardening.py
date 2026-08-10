"""Harden partial uniqueness and tenant trash indexes.

Revision ID: 0026
Revises: 0025
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


TENANT_TRASH_INDEXES = (
    ("departments", "ix_departments_company_deleted_at", ("company_id", "deleted_at")),
    ("employees", "ix_employees_company_deleted_at", ("company_id", "deleted_at")),
    ("branches", "ix_branches_company_deleted_at", ("company_id", "deleted_at")),
    (
        "warehouse_categories",
        "ix_warehouse_categories_company_deleted_at",
        ("company_id", "deleted_at"),
    ),
    ("warehouses", "ix_warehouses_branch_deleted_at", ("branch_id", "deleted_at")),
    ("locations", "ix_locations_warehouse_deleted_at", ("warehouse_id", "deleted_at")),
    ("roles", "ix_roles_company_deleted_at", ("company_id", "deleted_at")),
    ("categories", "ix_categories_company_deleted_at", ("company_id", "deleted_at")),
    (
        "sub_categories",
        "ix_sub_categories_company_deleted_at",
        ("company_id", "deleted_at"),
    ),
    ("units", "ix_units_owner_company_deleted_at", ("owner_company_id", "deleted_at")),
    ("products", "ix_products_company_deleted_at", ("company_id", "deleted_at")),
    ("suppliers", "ix_suppliers_company_deleted_at", ("company_id", "deleted_at")),
    (
        "supplier_contacts",
        "ix_supplier_contacts_supplier_deleted_at",
        ("id_supplier", "deleted_at"),
    ),
)


def upgrade() -> None:
    # This legacy unique index survived company scoping and prevented equal
    # department names in different companies.
    op.drop_index("ix_departments_name", table_name="departments")
    op.create_index("ix_departments_name", "departments", ["name"], unique=False)

    # Physical coordinates and unit names may be reused after an erroneous
    # record is sent to the trash, while remaining unique among visible rows.
    op.drop_constraint("uq_locations_warehouse_coordinates", "locations", type_="unique")
    op.create_index(
        "uq_locations_warehouse_coordinates_visible",
        "locations",
        ["warehouse_id", "aisle", "rack", "level", "position"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.drop_constraint("units_name_key", "units", type_="unique")
    op.create_index(
        "uq_units_global_name_visible",
        "units",
        [sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("owner_company_id IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_units_company_name_visible",
        "units",
        ["owner_company_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("owner_company_id IS NOT NULL AND deleted_at IS NULL"),
    )

    for table, name, columns in TENANT_TRASH_INDEXES:
        op.create_index(name, table, list(columns), unique=False)


def downgrade() -> None:
    for table, name, _columns in reversed(TENANT_TRASH_INDEXES):
        op.drop_index(name, table_name=table)

    op.drop_index("uq_units_company_name_visible", table_name="units")
    op.drop_index("uq_units_global_name_visible", table_name="units")
    op.create_unique_constraint("units_name_key", "units", ["name"])

    op.drop_index("uq_locations_warehouse_coordinates_visible", table_name="locations")
    op.create_unique_constraint(
        "uq_locations_warehouse_coordinates",
        "locations",
        ["warehouse_id", "aisle", "rack", "level", "position"],
    )

    op.drop_index("ix_departments_name", table_name="departments")
    op.create_index("ix_departments_name", "departments", ["name"], unique=True)
