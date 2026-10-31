"""Track receipt-line origin and explicit physical label placement.

Revision ID: 0083
Revises: 0082
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0083"
down_revision = "0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_lots",
        sa.Column(
            "label_confirmation_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    # Existing lots remain grandfathered. New lots require the explicit label
    # placement confirmation unless a caller deliberately marks them otherwise.
    op.alter_column(
        "inventory_lots",
        "label_confirmation_required",
        server_default=sa.text("true"),
    )
    op.add_column(
        "inventory_handling_units",
        sa.Column("inventory_lot_detail_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "inventory_handling_units",
        sa.Column("label_revision", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_foreign_key(
        "fk_inventory_handling_units_lot_detail_company",
        "inventory_handling_units",
        "inventory_lot_details",
        ["company_id", "inventory_lot_detail_id"],
        ["company_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_inventory_handling_units_lot_detail",
        "inventory_handling_units",
        ["company_id", "inventory_lot_detail_id"],
    )
    op.create_table(
        "inventory_label_confirmations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handling_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label_print_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handling_unit_code", sa.String(length=120), nullable=False),
        sa.Column("label_revision", sa.Integer(), nullable=False),
        sa.Column("quantity_base", sa.Numeric(18, 6), nullable=False),
        sa.Column("label_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("confirmed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "handling_unit_id"],
            ["inventory_handling_units.company_id", "inventory_handling_units.id"],
            ondelete="RESTRICT",
            name="fk_inventory_label_confirmations_unit_company",
        ),
        sa.ForeignKeyConstraint(
            ["label_print_id"],
            ["inventory_label_prints.id"],
            ondelete="RESTRICT",
            name="fk_inventory_label_confirmations_print",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by"],
            ["users.id"],
            ondelete="RESTRICT",
            name="fk_inventory_label_confirmations_actor",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "idempotency_key", name="uq_inventory_label_confirmations_key"
        ),
        sa.UniqueConstraint(
            "company_id",
            "handling_unit_id",
            "label_revision",
            name="uq_inventory_label_confirmations_unit_revision",
        ),
    )


def downgrade() -> None:
    op.drop_table("inventory_label_confirmations")
    op.drop_index("ix_inventory_handling_units_lot_detail", table_name="inventory_handling_units")
    op.drop_constraint(
        "fk_inventory_handling_units_lot_detail_company",
        "inventory_handling_units",
        type_="foreignkey",
    )
    op.drop_column("inventory_handling_units", "label_revision")
    op.drop_column("inventory_handling_units", "inventory_lot_detail_id")
    op.drop_column("inventory_lots", "label_confirmation_required")
