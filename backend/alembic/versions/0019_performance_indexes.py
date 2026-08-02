"""Add composite indexes for tenant-scoped operational queries.

Revision ID: 0019
Revises: 0018
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_audit_logs_company_cursor",
        "audit_logs",
        ["company_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_audit_logs_company_branch_cursor",
        "audit_logs",
        ["company_id", "branch_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_employees_company_active_status_created",
        "employees",
        ["company_id", "status", sa.text("created_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_employee_branch_active_branch_employee",
        "employee_branch_assignments",
        ["branch_id", "employee_id"],
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_branches_company_active_name",
        "branches",
        ["company_id", "name"],
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_warehouses_branch_active_name",
        "warehouses",
        ["branch_id", "name"],
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("ix_warehouses_branch_active_name", table_name="warehouses")
    op.drop_index("ix_branches_company_active_name", table_name="branches")
    op.drop_index(
        "ix_employee_branch_active_branch_employee",
        table_name="employee_branch_assignments",
    )
    op.drop_index("ix_employees_company_active_status_created", table_name="employees")
    op.drop_index("ix_audit_logs_company_branch_cursor", table_name="audit_logs")
    op.drop_index("ix_audit_logs_company_cursor", table_name="audit_logs")
