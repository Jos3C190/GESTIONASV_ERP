"""Persist manual demand levels for branch products."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "branch_product_demand_levels",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_branch_product_demand_levels_company_id_companies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_branch_product_demand_levels_branch_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            name="fk_branch_product_demand_levels_product_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name="fk_branch_product_demand_levels_updated_by_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_branch_product_demand_levels"),
        sa.UniqueConstraint(
            "company_id",
            "branch_id",
            "product_id",
            name="uq_branch_product_demand_levels_scope_product",
        ),
        sa.CheckConstraint(
            "level IN ('low','medium','high')", name="ck_branch_product_demand_level"
        ),
    )
    op.create_index(
        "ix_branch_product_demand_levels_branch_product",
        "branch_product_demand_levels",
        ["company_id", "branch_id", "product_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_branch_product_demand_levels_branch_product",
        table_name="branch_product_demand_levels",
    )
    op.drop_table("branch_product_demand_levels")
