"""Create the purchase-request aggregate."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_requests",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "request_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("required_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_purchase_requests_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_purchase_requests_branch_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_purchase_requests_warehouse_id_warehouses",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"],
            ["users.id"],
            name="fk_purchase_requests_requested_by_id_users",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "company_id", name="uq_purchase_requests_id_company_id"),
        sa.UniqueConstraint("company_id", "code", name="uq_purchase_requests_company_code"),
        sa.CheckConstraint(
            "status IN "
            "('draft','submitted','approved','rejected','partially_quoted',"
            "'quoted','partially_ordered','completed','cancelled')",
            name="ck_purchase_requests_status",
        ),
    )
    op.create_index(
        "ix_purchase_requests_company_status_date",
        "purchase_requests",
        ["company_id", "status", "request_date"],
    )
    op.create_index(
        "ix_purchase_requests_branch_status",
        "purchase_requests",
        ["branch_id", "status"],
    )
    op.create_index(
        "ix_purchase_requests_warehouse_status",
        "purchase_requests",
        ["warehouse_id", "status"],
    )
    op.create_index(
        "ix_purchase_requests_requested_by",
        "purchase_requests",
        ["requested_by_id"],
    )

    op.create_table(
        "purchase_request_details",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("purchase_request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["purchase_request_id", "company_id"],
            ["purchase_requests.id", "purchase_requests.company_id"],
            name="fk_purchase_request_details_request_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            name="fk_purchase_request_details_product_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            name="fk_purchase_request_details_unit_company",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_purchase_request_details_quantity_positive",
        ),
    )
    op.create_index(
        "ix_purchase_request_details_request",
        "purchase_request_details",
        ["purchase_request_id", "created_at"],
    )
    op.create_index(
        "ix_purchase_request_details_company_product",
        "purchase_request_details",
        ["company_id", "product_id"],
    )


def downgrade() -> None:
    op.drop_table("purchase_request_details")
    op.drop_table("purchase_requests")
