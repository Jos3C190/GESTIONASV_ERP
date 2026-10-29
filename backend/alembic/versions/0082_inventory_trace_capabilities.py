"""Revocable bearer links for read-only handling-unit traceability.

Revision ID: 0082
Revises: 0081
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0082"
down_revision = "0081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_trace_capabilities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handling_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest", name="uq_inventory_trace_capabilities_token_digest"),
        sa.ForeignKeyConstraint(
            ["company_id", "handling_unit_id"],
            ["inventory_handling_units.company_id", "inventory_handling_units.id"],
            ondelete="CASCADE",
            name="fk_inventory_trace_capabilities_unit_company",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="RESTRICT",
            name="fk_inventory_trace_capabilities_created_by",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_inventory_trace_capabilities_revoked_by",
        ),
    )
    op.create_index(
        "ix_inventory_trace_capabilities_unit_active",
        "inventory_trace_capabilities",
        ["company_id", "handling_unit_id", "revoked_at"],
    )
    op.create_index(
        "ix_inventory_trace_capabilities_created_at",
        "inventory_trace_capabilities",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_trace_capabilities_created_at", table_name="inventory_trace_capabilities"
    )
    op.drop_index(
        "ix_inventory_trace_capabilities_unit_active", table_name="inventory_trace_capabilities"
    )
    op.drop_table("inventory_trace_capabilities")
