"""Warehouse-specific operator grants, independent from job assignments."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0094"
down_revision = "0093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_companies",
        sa.Column("warehouse_restricted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "user_warehouse_access",
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "company_id", "warehouse_id"),
        sa.ForeignKeyConstraint(
            ["user_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id", "company_id"],
            ["warehouses.id", "warehouses.company_id"],
            ondelete="CASCADE",
        ),
    )
    op.execute(
        sa.text(
            "INSERT INTO permissions (id, code, description, module) "
            "SELECT gen_random_uuid(), 'inventory:warehouse_receipts', 'Operar el panel de bodega y verificar recepciones físicas', 'inventory' "
            "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'inventory:warehouse_receipts' AND deleted_at IS NULL)"
        )
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM user_companies WHERE warehouse_restricted")
    ):
        raise RuntimeError("Existen usuarios limitados por bodega; no retire su alcance de acceso.")
    op.drop_table("user_warehouse_access")
    op.drop_column("user_companies", "warehouse_restricted")
