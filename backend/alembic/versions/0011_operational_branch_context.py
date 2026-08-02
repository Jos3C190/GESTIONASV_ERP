"""Operational company/branch access scope and audit context.

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_companies",
        sa.Column(
            "access_all_branches",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "user_companies",
        sa.Column("last_branch_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_user_companies_last_branch",
        "user_companies",
        "branches",
        ["last_branch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_user_companies_last_branch_id", "user_companies", ["last_branch_id"]
    )

    # Preserve the company-wide behaviour that existed before branch scoping.
    op.execute("UPDATE user_companies SET access_all_branches = true")

    op.create_table(
        "user_branches",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "assigned_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            name="fk_user_branches_membership",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_user_branches_company_id", "user_branches", ["company_id"])
    op.create_index("ix_user_branches_branch_id", "user_branches", ["branch_id"])
    op.create_index(
        "uq_user_branches_default_active",
        "user_branches",
        ["user_id", "company_id"],
        unique=True,
        postgresql_where=sa.text("is_active AND is_default"),
    )

    op.add_column(
        "audit_logs", sa.Column("company_id", UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "audit_logs", sa.Column("branch_id", UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_audit_logs_company",
        "audit_logs",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_audit_logs_branch",
        "audit_logs",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_audit_logs_company_id", "audit_logs", ["company_id"])
    op.create_index("ix_audit_logs_branch_id", "audit_logs", ["branch_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_branch_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_company_id", table_name="audit_logs")
    op.drop_constraint("fk_audit_logs_branch", "audit_logs", type_="foreignkey")
    op.drop_constraint("fk_audit_logs_company", "audit_logs", type_="foreignkey")
    op.drop_column("audit_logs", "branch_id")
    op.drop_column("audit_logs", "company_id")
    op.drop_table("user_branches")
    op.drop_index("ix_user_companies_last_branch_id", table_name="user_companies")
    op.drop_constraint(
        "fk_user_companies_last_branch", "user_companies", type_="foreignkey"
    )
    op.drop_column("user_companies", "last_branch_id")
    op.drop_column("user_companies", "access_all_branches")
