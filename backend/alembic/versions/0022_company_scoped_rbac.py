"""Scope custom roles and user-role assignments to a company.

Revision ID: 0022
Revises: 0021
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    op.add_column("roles", sa.Column("company_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_roles_company_id_companies", "roles", "companies", ["company_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_roles_company_id", "roles", ["company_id"])

    custom_roles = int(connection.execute(sa.text("SELECT count(*) FROM roles WHERE is_system=false")).scalar_one())
    company_ids = list(connection.execute(sa.text("SELECT id FROM companies ORDER BY created_at, id")).scalars())
    if custom_roles and len(company_ids) != 1:
        raise RuntimeError(
            "Custom roles cannot be mapped safely: the RBAC migration requires exactly one company."
        )
    if company_ids:
        connection.execute(
            sa.text("UPDATE roles SET company_id=:company_id WHERE is_system=false AND company_id IS NULL"),
            {"company_id": company_ids[0]},
        )

    # Revision 0003 created both a named unique constraint and a unique index.
    # Keep the explicit names here so this migration also works on databases
    # restored from a dump (where PostgreSQL does not invent ``roles_name_key``).
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_constraint("uq_roles_name", "roles", type_="unique")
    op.create_unique_constraint("uq_roles_company_name", "roles", ["company_id", "name"])
    op.create_index(
        "uq_roles_global_name",
        "roles",
        ["name"],
        unique=True,
        postgresql_where=sa.text("company_id IS NULL"),
    )

    op.add_column("user_roles", sa.Column("company_id", UUID(as_uuid=True), nullable=True))
    connection.execute(
        sa.text(
            "UPDATE user_roles ur SET company_id=("
            "SELECT uc.company_id FROM user_companies uc WHERE uc.user_id=ur.user_id "
            "ORDER BY uc.is_default DESC, uc.company_id LIMIT 1) WHERE ur.company_id IS NULL"
        )
    )
    missing = int(connection.execute(sa.text("SELECT count(*) FROM user_roles WHERE company_id IS NULL")).scalar_one())
    if missing:
        raise RuntimeError("Every user role must belong to an existing user-company membership.")

    op.drop_constraint("user_roles_pkey", "user_roles", type_="primary")
    op.create_primary_key("user_roles_pkey", "user_roles", ["user_id", "company_id", "role_id"])
    op.alter_column("user_roles", "company_id", nullable=False)
    op.create_index("ix_user_roles_company_id", "user_roles", ["company_id"])
    op.create_foreign_key(
        "fk_user_roles_user_company",
        "user_roles",
        "user_companies",
        ["user_id", "company_id"],
        ["user_id", "company_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_user_roles_user_company", "user_roles", type_="foreignkey")
    op.drop_index("ix_user_roles_company_id", table_name="user_roles")
    op.drop_constraint("user_roles_pkey", "user_roles", type_="primary")
    # A user may now have the same role in several companies; retain one assignment.
    op.execute(
        "DELETE FROM user_roles a USING user_roles b WHERE a.ctid < b.ctid "
        "AND a.user_id=b.user_id AND a.role_id=b.role_id"
    )
    op.create_primary_key("user_roles_pkey", "user_roles", ["user_id", "role_id"])
    op.drop_column("user_roles", "company_id")
    op.drop_index("uq_roles_global_name", table_name="roles")
    op.drop_constraint("uq_roles_company_name", "roles", type_="unique")
    op.create_unique_constraint("uq_roles_name", "roles", ["name"])
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)
    op.drop_index("ix_roles_company_id", table_name="roles")
    op.drop_constraint("fk_roles_company_id_companies", "roles", type_="foreignkey")
    op.drop_column("roles", "company_id")
