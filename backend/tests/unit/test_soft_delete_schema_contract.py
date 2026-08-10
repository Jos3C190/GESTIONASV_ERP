"""Schema-level contract for the enterprise soft-delete lifecycle."""

from __future__ import annotations

from app.infrastructure import models as _models  # noqa: F401
from app.infrastructure.db.base import Base
from sqlalchemy import Index
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

LIFECYCLE_TABLES = {
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
}

CASE_INSENSITIVE_VISIBLE_INDEXES = {
    "uq_users_username_visible",
    "uq_users_email_visible",
    "uq_employees_company_code_visible",
    "uq_departments_company_name_visible",
    "uq_companies_nit_visible",
    "uq_companies_nrc_visible",
    "uq_branches_company_name_visible",
    "uq_branches_company_code_visible",
    "uq_warehouse_categories_company_name_visible",
    "uq_warehouses_branch_name_visible",
    "uq_warehouses_branch_code_visible",
    "uq_locations_warehouse_code_visible",
    "uq_roles_company_name_visible",
    "uq_roles_global_name_visible",
    "uq_permissions_code_visible",
    "uq_categories_company_name_visible",
    "uq_subcategories_company_category_name_visible",
    "uq_units_global_code_visible",
    "uq_units_company_code_visible",
    "uq_units_global_name_visible",
    "uq_units_company_name_visible",
    "uq_products_company_sku_visible",
    "uq_suppliers_company_code_visible",
}

TENANT_TRASH_INDEXES = {
    "ix_departments_company_deleted_at",
    "ix_employees_company_deleted_at",
    "ix_branches_company_deleted_at",
    "ix_warehouse_categories_company_deleted_at",
    "ix_warehouses_branch_deleted_at",
    "ix_locations_warehouse_deleted_at",
    "ix_roles_company_deleted_at",
    "ix_categories_company_deleted_at",
    "ix_sub_categories_company_deleted_at",
    "ix_units_owner_company_deleted_at",
    "ix_products_company_deleted_at",
    "ix_suppliers_company_deleted_at",
    "ix_supplier_contacts_supplier_deleted_at",
}


def _indexes_by_name() -> dict[str, Index]:
    return {
        index.name: index
        for table in Base.metadata.tables.values()
        for index in table.indexes
        if index.name is not None
    }


def test_app_meta_is_registered_as_managed_infrastructure_schema() -> None:
    table = Base.metadata.tables["app_meta"]
    assert set(table.c.keys()) == {"key", "value", "updated_at"}
    assert table.c.key.primary_key is True
    assert table.c.updated_at.server_default is not None
    assert "ix_app_meta_key" in {index.name for index in table.indexes}


def test_every_lifecycle_table_has_auditable_deletion_columns_and_actor_fk() -> None:
    for table_name in LIFECYCLE_TABLES:
        table = Base.metadata.tables[table_name]
        assert set(table.c.keys()).issuperset({"deleted_at", "deleted_by", "deletion_reason"})

        actor_fks = list(table.c.deleted_by.foreign_keys)
        assert len(actor_fks) == 1
        assert actor_fks[0].target_fullname == "users.id"
        assert actor_fks[0].ondelete == "SET NULL"


def test_business_identifiers_are_unique_case_insensitively_only_while_visible() -> None:
    indexes = _indexes_by_name()
    assert indexes.keys() >= CASE_INSENSITIVE_VISIBLE_INDEXES

    dialect = postgresql.dialect()
    for index_name in CASE_INSENSITIVE_VISIBLE_INDEXES:
        sql = str(CreateIndex(indexes[index_name]).compile(dialect=dialect)).lower()
        assert "create unique index" in sql
        assert "lower(" in sql
        assert "deleted_at is null" in sql


def test_tenant_trash_queries_have_composite_indexes() -> None:
    indexes = _indexes_by_name()
    assert indexes.keys() >= TENANT_TRASH_INDEXES
