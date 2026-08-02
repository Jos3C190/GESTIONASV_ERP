"""Enforce that authorized branches belong to the membership company.

Revision ID: 0012
Revises: 0011
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_branches_id_company_id", "branches", ["id", "company_id"]
    )
    op.drop_constraint(
        "fk_user_companies_last_branch", "user_companies", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_user_companies_last_branch_company",
        "user_companies",
        "branches",
        ["last_branch_id", "company_id"],
        ["id", "company_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_user_branches_branch_company",
        "user_branches",
        "branches",
        ["branch_id", "company_id"],
        ["id", "company_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_user_branches_branch_company", "user_branches", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_user_companies_last_branch_company",
        "user_companies",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_user_companies_last_branch",
        "user_companies",
        "branches",
        ["last_branch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint(
        "uq_branches_id_company_id", "branches", type_="unique"
    )
