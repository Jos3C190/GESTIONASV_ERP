"""Allow a company's mother warehouse to exist outside any branch."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("warehouses", sa.Column("company_id", UUID(as_uuid=True), nullable=True))
    op.execute(
        sa.text(
            "UPDATE warehouses AS warehouse "
            "SET company_id = branch.company_id "
            "FROM branches AS branch "
            "WHERE branch.id = warehouse.branch_id"
        )
    )
    op.alter_column("warehouses", "company_id", nullable=False)
    op.create_foreign_key(
        "fk_warehouses_company_id_companies",
        "warehouses",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    inspector = sa.inspect(op.get_bind())
    branch_fk = next(
        foreign_key
        for foreign_key in inspector.get_foreign_keys("warehouses")
        if foreign_key.get("referred_table") == "branches"
        and foreign_key.get("constrained_columns") == ["branch_id"]
    )
    op.drop_constraint(branch_fk["name"], "warehouses", type_="foreignkey")
    # Earlier versions allowed a branch warehouse to be marked as central.
    # Keep those warehouses assigned to their branch, but normalize the old flag
    # before enforcing the company-level mother warehouse invariant.
    op.execute(
        sa.text("UPDATE warehouses SET is_central = false WHERE branch_id IS NOT NULL AND is_central")
    )
    op.create_foreign_key(
        "fk_warehouses_branch_company",
        "warehouses",
        "branches",
        ["branch_id", "company_id"],
        ["id", "company_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_warehouses_unassigned_must_be_central",
        "warehouses",
        "branch_id IS NOT NULL OR is_central",
    )
    op.create_check_constraint(
        "ck_warehouses_central_must_be_unassigned",
        "warehouses",
        "NOT is_central OR branch_id IS NULL",
    )
    op.alter_column("warehouses", "branch_id", nullable=True)
    op.create_index(
        "ix_warehouses_company_deleted_at",
        "warehouses",
        ["company_id", "deleted_at"],
    )
    op.create_index(
        "uq_warehouses_company_name_unassigned_visible",
        "warehouses",
        ["company_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("branch_id IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_warehouses_company_code_unassigned_visible",
        "warehouses",
        ["company_id", sa.text("lower(code)")],
        unique=True,
        postgresql_where=sa.text("branch_id IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_warehouses_company_active_central_unassigned",
        "warehouses",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text(
            "branch_id IS NULL AND is_central AND is_active "
            "AND operational_status = 'active' AND deleted_at IS NULL"
        ),
    )

    op.drop_constraint("fk_purchase_orders_warehouse_branch", "purchase_orders", type_="foreignkey")
    op.create_foreign_key(
        "fk_purchase_orders_warehouse_id_warehouses",
        "purchase_orders",
        "warehouses",
        ["warehouse_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("fk_purchases_warehouse_branch", "purchases", type_="foreignkey")
    op.create_foreign_key(
        "fk_purchases_warehouse_id_warehouses",
        "purchases",
        "warehouses",
        ["warehouse_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("uq_warehouses_id_branch_id", "warehouses", type_="unique")


def downgrade() -> None:
    bind = op.get_bind()
    has_unassigned = bind.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM warehouses WHERE branch_id IS NULL)")
    )
    if has_unassigned:
        raise RuntimeError(
            "No se puede revertir 0073 mientras existan almacenes independientes de sucursal. "
            "Asigne primero esos almacenes a una sucursal."
        )

    op.drop_constraint("fk_purchases_warehouse_id_warehouses", "purchases", type_="foreignkey")
    op.create_unique_constraint(
        "uq_warehouses_id_branch_id", "warehouses", ["id", "branch_id"]
    )
    op.create_foreign_key(
        "fk_purchases_warehouse_branch",
        "purchases",
        "warehouses",
        ["warehouse_id", "branch_id"],
        ["id", "branch_id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "fk_purchase_orders_warehouse_id_warehouses", "purchase_orders", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_purchase_orders_warehouse_branch",
        "purchase_orders",
        "warehouses",
        ["warehouse_id", "branch_id"],
        ["id", "branch_id"],
        ondelete="RESTRICT",
    )
    op.drop_index("uq_warehouses_company_active_central_unassigned", table_name="warehouses")
    op.drop_index("uq_warehouses_company_code_unassigned_visible", table_name="warehouses")
    op.drop_index("uq_warehouses_company_name_unassigned_visible", table_name="warehouses")
    op.drop_index("ix_warehouses_company_deleted_at", table_name="warehouses")
    check_names = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_check_constraints("warehouses")
    }
    if "ck_warehouses_central_must_be_unassigned" in check_names:
        op.drop_constraint(
            "ck_warehouses_central_must_be_unassigned", "warehouses", type_="check"
        )
    op.drop_constraint("ck_warehouses_unassigned_must_be_central", "warehouses", type_="check")
    op.alter_column("warehouses", "branch_id", nullable=False)
    op.drop_constraint("fk_warehouses_company_id_companies", "warehouses", type_="foreignkey")
    op.drop_constraint("fk_warehouses_branch_company", "warehouses", type_="foreignkey")
    op.create_foreign_key(
        "fk_warehouses_branch_id_branches",
        "warehouses",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_column("warehouses", "company_id")
