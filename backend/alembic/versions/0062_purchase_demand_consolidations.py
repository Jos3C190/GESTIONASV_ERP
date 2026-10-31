"""Persist editable purchase demand consolidations and source history."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_consolidations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("central_warehouse_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("period_end >= period_start", name="ck_purchase_consolidations_period"),
        sa.CheckConstraint(
            "status IN ('draft','frozen','cancelled')", name="ck_purchase_consolidations_status"
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["central_warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "company_id", name="uq_purchase_consolidations_id_company"),
        sa.UniqueConstraint("company_id", "code", name="uq_purchase_consolidations_company_code"),
    )
    op.create_index(
        "ix_purchase_consolidations_company_status_period",
        "purchase_consolidations",
        ["company_id", "status", "period_start"],
    )
    op.create_table(
        "purchase_consolidation_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consolidation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("central_quantity", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("central_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("central_quantity >= 0", name="ck_purchase_consolidation_central_nonnegative"),
        sa.CheckConstraint(
            "central_quantity = 0 OR length(trim(coalesce(central_reason, ''))) > 0",
            name="ck_purchase_consolidation_central_reason",
        ),
        sa.ForeignKeyConstraint(
            ["consolidation_id", "company_id"],
            ["purchase_consolidations.id", "purchase_consolidations.company_id"],
            ondelete="CASCADE",
            name="fk_purchase_consolidation_lines_header_company",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            ondelete="RESTRICT",
            name="fk_purchase_consolidation_lines_product_company",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_purchase_consolidation_lines_unit_company",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "company_id", name="uq_purchase_consolidation_lines_id_company"),
        sa.UniqueConstraint(
            "consolidation_id", "product_id", "unit_id", name="uq_purchase_consolidation_product_unit"
        ),
    )
    op.create_index(
        "ix_purchase_consolidation_lines_header",
        "purchase_consolidation_lines",
        ["company_id", "consolidation_id"],
    )
    op.create_table(
        "purchase_consolidation_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consolidation_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_request_detail_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("included_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint("requested_quantity > 0", name="ck_purchase_consolidation_source_requested_positive"),
        sa.CheckConstraint(
            "included_quantity >= 0 AND included_quantity <= requested_quantity",
            name="ck_purchase_consolidation_source_included_range",
        ),
        sa.CheckConstraint(
            "included_quantity = requested_quantity OR length(trim(coalesce(reason, ''))) > 0",
            name="ck_purchase_consolidation_source_reason",
        ),
        sa.ForeignKeyConstraint(
            ["consolidation_line_id", "company_id"],
            ["purchase_consolidation_lines.id", "purchase_consolidation_lines.company_id"],
            ondelete="CASCADE",
            name="fk_purchase_consolidation_sources_line_company",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_request_id", "company_id"],
            ["purchase_requests.id", "purchase_requests.company_id"],
            ondelete="RESTRICT",
            name="fk_purchase_consolidation_sources_request_company",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_request_detail_id", "company_id"],
            ["purchase_request_details.id", "purchase_request_details.company_id"],
            ondelete="RESTRICT",
            name="fk_purchase_consolidation_sources_request_detail_company",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "company_id", name="uq_purchase_consolidation_sources_id_company"
        ),
    )
    op.create_index(
        "ix_purchase_consolidation_sources_request",
        "purchase_consolidation_sources",
        ["company_id", "purchase_request_id"],
    )
    op.create_table(
        "purchase_consolidation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consolidation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["consolidation_id", "company_id"],
            ["purchase_consolidations.id", "purchase_consolidations.company_id"],
            ondelete="CASCADE",
            name="fk_purchase_consolidation_events_header_company",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_purchase_consolidation_events_history",
        "purchase_consolidation_events",
        ["company_id", "consolidation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_purchase_consolidation_events_history", table_name="purchase_consolidation_events")
    op.drop_table("purchase_consolidation_events")
    op.drop_index("ix_purchase_consolidation_sources_request", table_name="purchase_consolidation_sources")
    op.drop_table("purchase_consolidation_sources")
    op.drop_index("ix_purchase_consolidation_lines_header", table_name="purchase_consolidation_lines")
    op.drop_table("purchase_consolidation_lines")
    op.drop_index("ix_purchase_consolidations_company_status_period", table_name="purchase_consolidations")
    op.drop_table("purchase_consolidations")
