"""Replace pallet capacity with certified weight and usable-volume limits."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

_PROFILES = "'general_mixed','rack','bulk_floor','cold','oversize_manual','transit'"
_ENFORCEMENT_MODES = "'disabled','observe','enforce'"
_METRICS = (
    "certified_max_weight_kg",
    "operational_max_weight_kg",
    "certified_usable_volume_m3",
    "operational_usable_volume_m3",
)
_DIMENSIONS = ("usable_length_m", "usable_width_m", "usable_height_m")


def _add_capacity_columns(table: str) -> None:
    for column in _METRICS:
        op.add_column(table, sa.Column(column, sa.Numeric(18, 6), nullable=True))
    op.add_column(
        table,
        sa.Column(
            "capacity_profile",
            sa.String(32),
            nullable=False,
            server_default="general_mixed",
        ),
    )
    op.add_column(
        table,
        sa.Column(
            "capacity_enforcement_mode",
            sa.String(16),
            nullable=False,
            server_default="disabled",
        ),
    )
    op.add_column(
        table,
        sa.Column("storage_eligible", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    for column in _DIMENSIONS:
        op.add_column(table, sa.Column(column, sa.Numeric(18, 6), nullable=True))


def _add_capacity_constraints(table: str) -> None:
    # PostgreSQL limits identifiers to 63 bytes.  The physical table name for
    # groups is intentionally longer, so keep its constraint prefix compact.
    prefix = "capacity_groups" if table == "warehouse_capacity_groups" else table
    for column in (*_METRICS, *_DIMENSIONS):
        op.create_check_constraint(
            f"ck_{prefix}_{column}_positive",
            table,
            f"{column} IS NULL OR {column} > 0",
        )
    op.create_check_constraint(
        f"ck_{prefix}_operational_weight_within_certified",
        table,
        "operational_max_weight_kg IS NULL OR "
        "(certified_max_weight_kg IS NOT NULL AND "
        "operational_max_weight_kg <= certified_max_weight_kg)",
    )
    op.create_check_constraint(
        f"ck_{prefix}_operational_volume_within_certified",
        table,
        "operational_usable_volume_m3 IS NULL OR "
        "(certified_usable_volume_m3 IS NOT NULL AND "
        "operational_usable_volume_m3 <= certified_usable_volume_m3)",
    )
    op.create_check_constraint(
        f"ck_{prefix}_capacity_profile",
        table,
        f"capacity_profile IN ({_PROFILES})",
    )
    op.create_check_constraint(
        f"ck_{prefix}_capacity_enforcement_mode",
        table,
        f"capacity_enforcement_mode IN ({_ENFORCEMENT_MODES})",
    )
    op.create_check_constraint(
        f"ck_{prefix}_usable_dimensions_complete",
        table,
        "(usable_length_m IS NULL AND usable_width_m IS NULL AND usable_height_m IS NULL) "
        "OR (usable_length_m IS NOT NULL AND usable_width_m IS NOT NULL "
        "AND usable_height_m IS NOT NULL)",
    )
    op.create_check_constraint(
        f"ck_{prefix}_nonstorage_capacity_disabled",
        table,
        "storage_eligible OR capacity_enforcement_mode = 'disabled'",
    )
    op.create_check_constraint(
        f"ck_{prefix}_enforce_capacity_complete",
        table,
        "capacity_enforcement_mode <> 'enforce' OR "
        "(storage_eligible AND certified_max_weight_kg IS NOT NULL "
        "AND operational_max_weight_kg IS NOT NULL "
        "AND certified_usable_volume_m3 IS NOT NULL "
        "AND operational_usable_volume_m3 IS NOT NULL)",
    )


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE warehouses SET operational_status = 'active' WHERE operational_status = 'full'"
        )
    )
    op.drop_constraint("ck_warehouses_operational_status", "warehouses", type_="check")
    op.create_check_constraint(
        "ck_warehouses_operational_status",
        "warehouses",
        "operational_status IN ('active','inactive','maintenance')",
    )
    for table in ("warehouses", "locations"):
        _add_capacity_columns(table)

    bind.execute(
        sa.text(
            "UPDATE warehouses SET "
            "certified_max_weight_kg = max_weight_kg, "
            "operational_max_weight_kg = max_weight_kg, "
            "certified_usable_volume_m3 = max_volume_m3, "
            "operational_usable_volume_m3 = max_volume_m3, "
            "capacity_profile = CASE "
            "WHEN warehouse_type = 'cold_storage' THEN 'cold' "
            "WHEN warehouse_type = 'transit' THEN 'transit' "
            "ELSE 'general_mixed' END, "
            "capacity_enforcement_mode = CASE "
            "WHEN max_weight_kg IS NOT NULL AND max_volume_m3 IS NOT NULL "
            "THEN 'observe' ELSE 'disabled' END"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE locations SET "
            "certified_max_weight_kg = max_weight_kg, "
            "operational_max_weight_kg = max_weight_kg, "
            "certified_usable_volume_m3 = max_volume_m3, "
            "operational_usable_volume_m3 = max_volume_m3, "
            "capacity_profile = CASE "
            "WHEN location_type = 'bulk' THEN 'bulk_floor' "
            "WHEN location_type IN ('receiving','staging','packing','shipping') "
            "THEN 'transit' ELSE 'general_mixed' END, "
            "storage_eligible = CASE "
            "WHEN location_type IN ('receiving','quality','packing','shipping','virtual') "
            "THEN false ELSE true END, "
            "capacity_enforcement_mode = CASE "
            "WHEN location_type IN ('receiving','quality','packing','shipping','virtual') "
            "THEN 'disabled' "
            "WHEN max_weight_kg IS NOT NULL AND max_volume_m3 IS NOT NULL "
            "THEN 'observe' ELSE 'disabled' END"
        )
    )

    op.drop_constraint(
        "ck_locations_capacity_configured_when_operational", "locations", type_="check"
    )
    for table in ("warehouses", "locations"):
        op.drop_constraint(f"ck_{table}_capacity_check_mode", table, type_="check")
        op.drop_constraint(f"ck_{table}_max_volume_positive", table, type_="check")
        op.drop_constraint(f"ck_{table}_max_weight_positive", table, type_="check")
        op.drop_constraint(f"ck_{table}_pallet_positions_nonnegative", table, type_="check")
        op.drop_column(table, "capacity_check_mode")
        op.drop_column(table, "max_volume_m3")
        op.drop_column(table, "max_weight_kg")
        op.drop_column(table, "max_pallet_positions")
        _add_capacity_constraints(table)

    op.create_table(
        "warehouse_capacity_groups",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "warehouse_id",
            UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("parent_id", UUID(as_uuid=True), nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("group_type", sa.String(24), nullable=False, server_default="structural"),
        sa.Column("certified_max_weight_kg", sa.Numeric(18, 6), nullable=True),
        sa.Column("operational_max_weight_kg", sa.Numeric(18, 6), nullable=True),
        sa.Column("certified_usable_volume_m3", sa.Numeric(18, 6), nullable=True),
        sa.Column("operational_usable_volume_m3", sa.Numeric(18, 6), nullable=True),
        sa.Column(
            "capacity_profile",
            sa.String(32),
            nullable=False,
            server_default="general_mixed",
        ),
        sa.Column(
            "capacity_enforcement_mode",
            sa.String(16),
            nullable=False,
            server_default="disabled",
        ),
        sa.Column("storage_eligible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("usable_length_m", sa.Numeric(18, 6), nullable=True),
        sa.Column("usable_width_m", sa.Numeric(18, 6), nullable=True),
        sa.Column("usable_height_m", sa.Numeric(18, 6), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "deleted_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("deletion_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_id", "warehouse_id"],
            ["warehouse_capacity_groups.id", "warehouse_capacity_groups.warehouse_id"],
            name="fk_capacity_groups_parent_warehouse",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "warehouse_id", name="uq_capacity_groups_identity_warehouse"),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_capacity_groups_not_self_parent",
        ),
        sa.CheckConstraint(
            "group_type IN ('structural','rack','bay','level','floor_zone','cold_chamber','transit_zone')",
            name="ck_capacity_groups_type",
        ),
    )
    _add_capacity_constraints("warehouse_capacity_groups")
    op.create_index(
        "uq_capacity_groups_warehouse_code_visible",
        "warehouse_capacity_groups",
        ["warehouse_id", sa.text("lower(code)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_capacity_groups_warehouse_parent",
        "warehouse_capacity_groups",
        ["warehouse_id", "parent_id"],
    )
    op.create_index(
        "ix_warehouse_capacity_groups_deleted_at",
        "warehouse_capacity_groups",
        ["deleted_at"],
    )
    op.add_column("locations", sa.Column("capacity_group_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_locations_capacity_group_warehouse",
        "locations",
        "warehouse_capacity_groups",
        ["capacity_group_id", "warehouse_id"],
        ["id", "warehouse_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_locations_warehouse_capacity_group",
        "locations",
        ["warehouse_id", "capacity_group_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_locations_warehouse_capacity_group", table_name="locations")
    op.drop_constraint("fk_locations_capacity_group_warehouse", "locations", type_="foreignkey")
    op.drop_column("locations", "capacity_group_id")
    op.drop_table("warehouse_capacity_groups")
    for table in ("warehouses", "locations"):
        for constraint in (
            "enforce_capacity_complete",
            "nonstorage_capacity_disabled",
            "usable_dimensions_complete",
            "capacity_enforcement_mode",
            "capacity_profile",
            "operational_volume_within_certified",
            "operational_weight_within_certified",
        ):
            op.drop_constraint(f"ck_{table}_{constraint}", table, type_="check")
        for column in (*_METRICS, *_DIMENSIONS):
            op.drop_constraint(f"ck_{table}_{column}_positive", table, type_="check")

        op.add_column(table, sa.Column("max_pallet_positions", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("max_weight_kg", sa.Numeric(14, 3), nullable=True))
        op.add_column(table, sa.Column("max_volume_m3", sa.Numeric(14, 3), nullable=True))
        op.add_column(
            table,
            sa.Column(
                "capacity_check_mode",
                sa.String(24),
                nullable=False,
                server_default="not_configured",
            ),
        )

    bind.execute(
        sa.text(
            "UPDATE warehouses SET "
            "max_weight_kg = certified_max_weight_kg, "
            "max_volume_m3 = certified_usable_volume_m3, "
            "capacity_check_mode = CASE "
            "WHEN certified_max_weight_kg IS NOT NULL "
            "AND certified_usable_volume_m3 IS NOT NULL THEN 'combined' "
            "WHEN certified_max_weight_kg IS NOT NULL THEN 'weight' "
            "WHEN certified_usable_volume_m3 IS NOT NULL THEN 'volume' "
            "ELSE 'not_configured' END"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE locations SET max_pallet_positions = 1, "
            "max_weight_kg = certified_max_weight_kg, "
            "max_volume_m3 = certified_usable_volume_m3, "
            "capacity_check_mode = CASE "
            "WHEN certified_max_weight_kg IS NOT NULL "
            "AND certified_usable_volume_m3 IS NOT NULL THEN 'combined' "
            "WHEN certified_max_weight_kg IS NOT NULL THEN 'weight' "
            "WHEN certified_usable_volume_m3 IS NOT NULL THEN 'volume' "
            "ELSE 'pallet_positions' END"
        )
    )
    op.alter_column("locations", "max_pallet_positions", nullable=False)

    for table in ("warehouses", "locations"):
        for column in (
            *_DIMENSIONS,
            "storage_eligible",
            "capacity_enforcement_mode",
            "capacity_profile",
        ):
            op.drop_column(table, column)
        for column in reversed(_METRICS):
            op.drop_column(table, column)
        op.create_check_constraint(
            f"ck_{table}_pallet_positions_nonnegative",
            table,
            "max_pallet_positions IS NULL OR max_pallet_positions >= 0",
        )
        op.create_check_constraint(
            f"ck_{table}_max_weight_positive",
            table,
            "max_weight_kg IS NULL OR max_weight_kg > 0",
        )
        op.create_check_constraint(
            f"ck_{table}_max_volume_positive",
            table,
            "max_volume_m3 IS NULL OR max_volume_m3 > 0",
        )
        op.create_check_constraint(
            f"ck_{table}_capacity_check_mode",
            table,
            "capacity_check_mode IN "
            "('pallet_positions','weight','volume','combined','not_configured')",
        )
        op.alter_column(table, "capacity_check_mode", server_default=None)

    op.create_check_constraint(
        "ck_locations_capacity_configured_when_operational",
        "locations",
        "NOT is_active OR max_pallet_positions IS NOT NULL "
        "OR max_weight_kg IS NOT NULL OR max_volume_m3 IS NOT NULL",
    )
    op.drop_constraint("ck_warehouses_operational_status", "warehouses", type_="check")
    op.create_check_constraint(
        "ck_warehouses_operational_status",
        "warehouses",
        "operational_status IN ('active','inactive','maintenance','full')",
    )
