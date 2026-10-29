"""Group accepted inventory quantities by supplier receipt.

Revision ID: 0080
Revises: 0079
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0080"
down_revision = "0079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_lots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_inventory_lots_company_id"),
        sa.UniqueConstraint("company_id", "purchase_id", name="uq_inventory_lots_purchase"),
        sa.UniqueConstraint("company_id", "code", name="uq_inventory_lots_code"),
        sa.ForeignKeyConstraint(
            ["purchase_id", "company_id"],
            ["purchases.id", "purchases.company_id"],
            name="fk_inventory_lots_purchase_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name="fk_inventory_lots_created_by",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("char_length(code) BETWEEN 3 AND 80", name="ck_inventory_lots_code"),
    )
    op.create_index(
        "ix_inventory_lots_company_received", "inventory_lots", ["company_id", "received_at"]
    )

    op.create_table(
        "inventory_lot_details",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_lot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_detail_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("base_unit_id", sa.Integer(), nullable=False),
        sa.Column("quantity_received", sa.Numeric(18, 6), nullable=False),
        sa.Column("quantity_accepted", sa.Numeric(18, 6), nullable=False),
        sa.Column("accepted_quantity_base", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "id", name="uq_inventory_lot_details_company_id"),
        sa.UniqueConstraint(
            "company_id",
            "inventory_lot_id",
            "purchase_detail_id",
            name="uq_inventory_lot_details_purchase_line",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_lot_id"],
            ["inventory_lots.company_id", "inventory_lots.id"],
            name="fk_inventory_lot_details_lot_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_detail_id", "company_id"],
            ["purchase_details.id", "purchase_details.company_id"],
            name="fk_inventory_lot_details_purchase_detail_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "inventory_item_id"],
            ["inventory_items.company_id", "inventory_items.id"],
            name="fk_inventory_lot_details_item_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            name="fk_inventory_lot_details_product_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "base_unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            name="fk_inventory_lot_details_unit_company",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "quantity_received > 0 AND quantity_accepted > 0 AND "
            "quantity_accepted <= quantity_received AND accepted_quantity_base > 0",
            name="ck_inventory_lot_details_quantities",
        ),
    )
    op.create_index(
        "ix_inventory_lot_details_item",
        "inventory_lot_details",
        ["company_id", "inventory_lot_id", "inventory_item_id"],
    )

    op.add_column(
        "inventory_handling_units",
        sa.Column("inventory_lot_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_inventory_handling_units_inventory_lot_company",
        "inventory_handling_units",
        "inventory_lots",
        ["company_id", "inventory_lot_id"],
        ["company_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_inventory_handling_units_receipt_lot",
        "inventory_handling_units",
        ["company_id", "inventory_lot_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_handling_units_receipt_lot", table_name="inventory_handling_units")
    op.drop_constraint(
        "fk_inventory_handling_units_inventory_lot_company",
        "inventory_handling_units",
        type_="foreignkey",
    )
    op.drop_column("inventory_handling_units", "inventory_lot_id")
    op.drop_index("ix_inventory_lot_details_item", table_name="inventory_lot_details")
    op.drop_table("inventory_lot_details")
    op.drop_index("ix_inventory_lots_company_received", table_name="inventory_lots")
    op.drop_table("inventory_lots")
