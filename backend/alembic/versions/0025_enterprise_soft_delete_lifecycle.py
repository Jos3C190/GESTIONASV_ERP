"""Enterprise soft-delete lifecycle for user-managed master data.

Revision ID: 0025
Revises: 0024
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


LIFECYCLE_TABLES = (
    "users",
    "employees",
    "departments",
    "companies",
    "branches",
    "warehouse_categories",
    "warehouses",
    "locations",
    "roles",
    "permissions",
    "categories",
    "sub_categories",
    "units",
    "products",
    "suppliers",
    "supplier_contacts",
)

EXISTING_SOFT_DELETE_TABLES = {"users", "employees"}

LIFECYCLE_PERMISSIONS = (
    ("users:delete", "Eliminar usuarios lógicamente", "users"),
    ("users:restore", "Restaurar usuarios eliminados", "users"),
    ("employees:restore", "Restaurar empleados eliminados", "employees"),
    ("departments:delete", "Eliminar departamentos lógicamente", "employees"),
    ("departments:restore", "Restaurar departamentos eliminados", "employees"),
    ("products:delete", "Eliminar productos lógicamente", "products"),
    ("products:restore", "Restaurar productos eliminados", "products"),
    ("product_categories:delete", "Eliminar categorías de productos", "products"),
    ("product_categories:restore", "Restaurar categorías de productos", "products"),
    ("units:delete", "Eliminar unidades personalizadas", "units"),
    ("units:restore", "Restaurar unidades personalizadas", "units"),
    ("suppliers:delete", "Eliminar proveedores y contactos", "suppliers"),
    ("suppliers:restore", "Restaurar proveedores y contactos", "suppliers"),
    ("roles:restore", "Restaurar roles eliminados", "roles"),
    ("permissions:delete", "Eliminar permisos personalizados", "roles"),
    ("permissions:restore", "Restaurar permisos personalizados", "roles"),
    ("lifecycle:read", "Consultar la papelera administrativa", "administration"),
    *(
        (f"{resource}.{action}", f"{action} {resource}", resource)
        for resource in ("companies", "branches", "warehouse_categories", "warehouses", "locations")
        for action in ("delete", "restore")
    ),
)


def upgrade() -> None:
    for table in LIFECYCLE_TABLES:
        if table not in EXISTING_SOFT_DELETE_TABLES:
            op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
            op.create_index(f"ix_{table}_deleted_at", table, ["deleted_at"])
        op.add_column(table, sa.Column("deleted_by", UUID(as_uuid=True), nullable=True))
        op.add_column(table, sa.Column("deletion_reason", sa.Text(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_deleted_by_users",
            table,
            "users",
            ["deleted_by"],
            ["id"],
            ondelete="SET NULL",
        )

    # A deleted record must not reserve a business identifier forever.  The
    # replacement indexes preserve uniqueness only among visible records.
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.execute(
        "CREATE UNIQUE INDEX uq_users_username_visible ON users (lower(username)) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_users_email_visible ON users (lower(email)) WHERE deleted_at IS NULL"
    )

    replacements = (
        (
            "departments",
            "uq_departments_company_name",
            "uq_departments_company_name_visible",
            "company_id, lower(name)",
        ),
        (
            "employees",
            "uq_employees_company_code",
            "uq_employees_company_code_visible",
            "company_id, lower(employee_code)",
        ),
        ("companies", "uq_companies_nit", "uq_companies_nit_visible", "lower(nit)"),
        ("companies", "uq_companies_nrc", "uq_companies_nrc_visible", "lower(nrc)"),
        (
            "branches",
            "uq_branches_company_name",
            "uq_branches_company_name_visible",
            "company_id, lower(name)",
        ),
        (
            "branches",
            "uq_branches_company_code",
            "uq_branches_company_code_visible",
            "company_id, lower(code)",
        ),
        (
            "warehouse_categories",
            "uq_warehouse_categories_company_name",
            "uq_warehouse_categories_company_name_visible",
            "company_id, lower(name)",
        ),
        (
            "warehouses",
            "uq_warehouses_branch_name",
            "uq_warehouses_branch_name_visible",
            "branch_id, lower(name)",
        ),
        (
            "warehouses",
            "uq_warehouses_branch_code",
            "uq_warehouses_branch_code_visible",
            "branch_id, lower(code)",
        ),
        (
            "locations",
            "uq_locations_warehouse_code",
            "uq_locations_warehouse_code_visible",
            "warehouse_id, lower(code)",
        ),
        (
            "roles",
            "uq_roles_company_name",
            "uq_roles_company_name_visible",
            "company_id, lower(name)",
        ),
        (
            "categories",
            "uq_categories_company_name",
            "uq_categories_company_name_visible",
            "company_id, lower(name)",
        ),
        (
            "sub_categories",
            "uq_subcategories_company_category_name",
            "uq_subcategories_company_category_name_visible",
            "company_id, id_category, lower(name)",
        ),
        (
            "products",
            "uq_products_company_sku",
            "uq_products_company_sku_visible",
            "company_id, lower(sku)",
        ),
        (
            "suppliers",
            "uq_suppliers_company_code",
            "uq_suppliers_company_code_visible",
            "company_id, lower(code)",
        ),
    )
    for table, constraint, index, columns in replacements:
        op.drop_constraint(constraint, table, type_="unique")
        op.execute(f"CREATE UNIQUE INDEX {index} ON {table} ({columns}) WHERE deleted_at IS NULL")

    op.drop_constraint("uq_permissions_code", "permissions", type_="unique")
    op.drop_index("ix_permissions_code", table_name="permissions")
    op.execute(
        "CREATE UNIQUE INDEX uq_permissions_code_visible ON permissions (lower(code)) WHERE deleted_at IS NULL"
    )

    # Existing redundant unique indexes predate company scoping.
    op.execute("DROP INDEX IF EXISTS ix_employees_employee_code")
    op.execute("DROP INDEX IF EXISTS ix_employees_user_id")
    op.execute(
        "CREATE UNIQUE INDEX uq_employees_user_visible ON employees (user_id) WHERE user_id IS NOT NULL AND deleted_at IS NULL"
    )

    op.execute("DROP INDEX IF EXISTS uq_roles_global_name")
    op.execute(
        "CREATE UNIQUE INDEX uq_roles_global_name_visible ON roles (lower(name)) WHERE company_id IS NULL AND deleted_at IS NULL"
    )

    op.execute("DROP INDEX IF EXISTS uq_units_global_code")
    op.execute("DROP INDEX IF EXISTS uq_units_company_code")
    op.execute(
        "CREATE UNIQUE INDEX uq_units_global_code_visible ON units (lower(code)) WHERE owner_company_id IS NULL AND deleted_at IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_units_company_code_visible ON units (owner_company_id, lower(code)) WHERE owner_company_id IS NOT NULL AND deleted_at IS NULL"
    )

    connection = op.get_bind()
    for code, description, module in LIFECYCLE_PERMISSIONS:
        connection.execute(
            sa.text(
                "INSERT INTO permissions (id, code, description, module, created_at) "
                "VALUES (gen_random_uuid(), :code, :description, :module, now()) "
                "ON CONFLICT DO NOTHING"
            ),
            {"code": code, "description": description, "module": module},
        )
    connection.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id, created_at) "
            "SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p "
            "WHERE r.name IN ('SUPER_ADMIN', 'ADMINISTRADOR') "
            "AND r.deleted_at IS NULL AND p.deleted_at IS NULL "
            "AND p.code = ANY(:codes) ON CONFLICT DO NOTHING"
        ),
        {"codes": [code for code, _, _ in LIFECYCLE_PERMISSIONS]},
    )
    connection.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id, created_at) "
            "SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p "
            "WHERE r.name = 'RECURSOS_HUMANOS' "
            "AND r.deleted_at IS NULL AND p.deleted_at IS NULL "
            "AND p.code = ANY(:codes) ON CONFLICT DO NOTHING"
        ),
        {"codes": ["departments:delete"]},
    )


def downgrade() -> None:
    # Permission rows are application catalogue data and several lifecycle
    # codes may already have existed before this revision.  Removing by code
    # would destroy legitimate RBAC configuration on downgrade, so they and
    # their assignments are intentionally retained as backward-compatible
    # inert catalogue entries.
    op.execute("DROP INDEX IF EXISTS uq_units_company_code_visible")
    op.execute("DROP INDEX IF EXISTS uq_units_global_code_visible")
    op.execute(
        "CREATE UNIQUE INDEX uq_units_global_code ON units (lower(code)) WHERE owner_company_id IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_units_company_code ON units (owner_company_id, lower(code)) WHERE owner_company_id IS NOT NULL"
    )

    op.execute("DROP INDEX IF EXISTS uq_roles_global_name_visible")
    op.create_index(
        "uq_roles_global_name",
        "roles",
        ["name"],
        unique=True,
        postgresql_where=sa.text("company_id IS NULL"),
    )
    op.execute("DROP INDEX IF EXISTS uq_employees_user_visible")
    op.create_index("ix_employees_user_id", "employees", ["user_id"], unique=True)
    op.create_index("ix_employees_employee_code", "employees", ["employee_code"], unique=True)

    op.execute("DROP INDEX IF EXISTS uq_permissions_code_visible")
    op.create_unique_constraint("uq_permissions_code", "permissions", ["code"])
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=True)

    replacements = (
        (
            "departments",
            "uq_departments_company_name",
            ["company_id", "name"],
            "uq_departments_company_name_visible",
        ),
        (
            "employees",
            "uq_employees_company_code",
            ["company_id", "employee_code"],
            "uq_employees_company_code_visible",
        ),
        ("companies", "uq_companies_nit", ["nit"], "uq_companies_nit_visible"),
        ("companies", "uq_companies_nrc", ["nrc"], "uq_companies_nrc_visible"),
        (
            "branches",
            "uq_branches_company_name",
            ["company_id", "name"],
            "uq_branches_company_name_visible",
        ),
        (
            "branches",
            "uq_branches_company_code",
            ["company_id", "code"],
            "uq_branches_company_code_visible",
        ),
        (
            "warehouse_categories",
            "uq_warehouse_categories_company_name",
            ["company_id", "name"],
            "uq_warehouse_categories_company_name_visible",
        ),
        (
            "warehouses",
            "uq_warehouses_branch_name",
            ["branch_id", "name"],
            "uq_warehouses_branch_name_visible",
        ),
        (
            "warehouses",
            "uq_warehouses_branch_code",
            ["branch_id", "code"],
            "uq_warehouses_branch_code_visible",
        ),
        (
            "locations",
            "uq_locations_warehouse_code",
            ["warehouse_id", "code"],
            "uq_locations_warehouse_code_visible",
        ),
        ("roles", "uq_roles_company_name", ["company_id", "name"], "uq_roles_company_name_visible"),
        (
            "categories",
            "uq_categories_company_name",
            ["company_id", "name"],
            "uq_categories_company_name_visible",
        ),
        (
            "sub_categories",
            "uq_subcategories_company_category_name",
            ["company_id", "id_category", "name"],
            "uq_subcategories_company_category_name_visible",
        ),
        (
            "products",
            "uq_products_company_sku",
            ["company_id", "sku"],
            "uq_products_company_sku_visible",
        ),
        (
            "suppliers",
            "uq_suppliers_company_code",
            ["company_id", "code"],
            "uq_suppliers_company_code_visible",
        ),
    )
    for table, constraint, columns, index in reversed(replacements):
        op.execute(f"DROP INDEX IF EXISTS {index}")
        op.create_unique_constraint(constraint, table, columns)

    op.execute("DROP INDEX IF EXISTS uq_users_email_visible")
    op.execute("DROP INDEX IF EXISTS uq_users_username_visible")
    op.create_unique_constraint("uq_users_username", "users", ["username"])
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    for table in reversed(LIFECYCLE_TABLES):
        op.drop_constraint(f"fk_{table}_deleted_by_users", table, type_="foreignkey")
        op.drop_column(table, "deletion_reason")
        op.drop_column(table, "deleted_by")
        if table not in EXISTING_SOFT_DELETE_TABLES:
            op.drop_index(f"ix_{table}_deleted_at", table_name=table)
            op.drop_column(table, "deleted_at")
