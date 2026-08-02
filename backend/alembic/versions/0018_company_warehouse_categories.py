"""Scope warehouse categories by company.

Revision ID: 0018
Revises: 0017
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "warehouse_categories",
        sa.Column("company_id", UUID(as_uuid=True), nullable=True),
    )
    op.drop_constraint(
        "uq_warehouse_categories_name", "warehouse_categories", type_="unique"
    )

    connection = op.get_bind()
    categories = connection.execute(
        sa.text(
            "SELECT id, name, description, is_active, created_at, updated_at "
            "FROM warehouse_categories ORDER BY id"
        )
    ).mappings()
    for category in categories:
        company_ids = list(
            connection.execute(
                sa.text(
                    "SELECT DISTINCT b.company_id "
                    "FROM warehouses w JOIN branches b ON b.id = w.branch_id "
                    "WHERE w.warehouse_category_id = :category_id ORDER BY b.company_id"
                ),
                {"category_id": category["id"]},
            ).scalars()
        )
        if not company_ids:
            connection.execute(
                sa.text("DELETE FROM warehouse_categories WHERE id = :category_id"),
                {"category_id": category["id"]},
            )
            continue

        connection.execute(
            sa.text(
                "UPDATE warehouse_categories SET company_id = :company_id "
                "WHERE id = :category_id"
            ),
            {"company_id": company_ids[0], "category_id": category["id"]},
        )
        for company_id in company_ids[1:]:
            clone_id = uuid.uuid4()
            connection.execute(
                sa.text(
                    "INSERT INTO warehouse_categories "
                    "(id, company_id, name, description, is_active, created_at, updated_at) "
                    "VALUES (:id, :company_id, :name, :description, :is_active, "
                    ":created_at, :updated_at)"
                ),
                {
                    "id": clone_id,
                    "company_id": company_id,
                    "name": category["name"],
                    "description": category["description"],
                    "is_active": category["is_active"],
                    "created_at": category["created_at"],
                    "updated_at": category["updated_at"],
                },
            )
            connection.execute(
                sa.text(
                    "UPDATE warehouses SET warehouse_category_id = :clone_id "
                    "WHERE warehouse_category_id = :category_id "
                    "AND branch_id IN (SELECT id FROM branches WHERE company_id = :company_id)"
                ),
                {
                    "clone_id": clone_id,
                    "category_id": category["id"],
                    "company_id": company_id,
                },
            )

    op.alter_column("warehouse_categories", "company_id", nullable=False)
    op.create_foreign_key(
        "fk_warehouse_categories_company_id_companies",
        "warehouse_categories",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_warehouse_categories_company_id", "warehouse_categories", ["company_id"]
    )
    op.create_unique_constraint(
        "uq_warehouse_categories_company_name",
        "warehouse_categories",
        ["company_id", "name"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    duplicate_names = connection.execute(
        sa.text(
            "SELECT name FROM warehouse_categories GROUP BY name HAVING count(*) > 1"
        )
    ).scalars()
    for name in duplicate_names:
        ids = list(
            connection.execute(
                sa.text(
                    "SELECT id FROM warehouse_categories WHERE name = :name "
                    "ORDER BY created_at, id"
                ),
                {"name": name},
            ).scalars()
        )
        canonical_id = ids[0]
        for duplicate_id in ids[1:]:
            connection.execute(
                sa.text(
                    "UPDATE warehouses SET warehouse_category_id = :canonical_id "
                    "WHERE warehouse_category_id = :duplicate_id"
                ),
                {"canonical_id": canonical_id, "duplicate_id": duplicate_id},
            )
            connection.execute(
                sa.text("DELETE FROM warehouse_categories WHERE id = :duplicate_id"),
                {"duplicate_id": duplicate_id},
            )

    op.drop_constraint(
        "uq_warehouse_categories_company_name", "warehouse_categories", type_="unique"
    )
    op.drop_index("ix_warehouse_categories_company_id", table_name="warehouse_categories")
    op.drop_constraint(
        "fk_warehouse_categories_company_id_companies",
        "warehouse_categories",
        type_="foreignkey",
    )
    op.drop_column("warehouse_categories", "company_id")
    op.create_unique_constraint(
        "uq_warehouse_categories_name", "warehouse_categories", ["name"]
    )
