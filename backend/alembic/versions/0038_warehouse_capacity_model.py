"""Model physical warehouse capacity explicitly.

The former ``capacity`` integer represented an ambiguous mock-up value.  It is
renamed to pallet positions and complemented by optional weight and volume
limits.  Inventory is not present yet, therefore no occupancy facts are
created by this migration.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None

_MODES = "'pallet_positions','weight','volume','combined','not_configured'"


def upgrade() -> None:
    bind = op.get_bind()

    # Preserve the existing mock-up values, but give them an unambiguous
    # meaning.  The ORM exposes ``capacity`` only as a deprecated synonym.
    op.alter_column(
        "warehouses",
        "capacity",
        new_column_name="max_pallet_positions",
        existing_type=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "locations",
        "capacity",
        new_column_name="max_pallet_positions",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )

    for table in ("warehouses", "locations"):
        op.add_column(
            table,
            sa.Column("max_weight_kg", sa.Numeric(14, 3), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("max_volume_m3", sa.Numeric(14, 3), nullable=True),
        )
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
            "UPDATE warehouses SET capacity_check_mode = "
            "CASE WHEN max_pallet_positions IS NULL THEN 'not_configured' "
            "ELSE 'pallet_positions' END"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE locations SET capacity_check_mode = 'pallet_positions' "
            "WHERE max_pallet_positions IS NOT NULL"
        )
    )

    # 0028's check retained its old name after the column rename.  Replace it
    # with checks that describe the new physical model.
    op.drop_constraint("ck_warehouses_capacity", "warehouses", type_="check")
    op.drop_constraint("ck_locations_capacity_positive", "locations", type_="check")
    op.create_check_constraint(
        "ck_warehouses_pallet_positions_nonnegative",
        "warehouses",
        "max_pallet_positions IS NULL OR max_pallet_positions >= 0",
    )
    op.create_check_constraint(
        "ck_locations_pallet_positions_nonnegative",
        "locations",
        "max_pallet_positions IS NULL OR max_pallet_positions >= 0",
    )
    for table, prefix in (("warehouses", "warehouses"), ("locations", "locations")):
        op.create_check_constraint(
            f"ck_{prefix}_max_weight_positive",
            table,
            "max_weight_kg IS NULL OR max_weight_kg > 0",
        )
        op.create_check_constraint(
            f"ck_{prefix}_max_volume_positive",
            table,
            "max_volume_m3 IS NULL OR max_volume_m3 > 0",
        )
        op.create_check_constraint(
            f"ck_{prefix}_capacity_check_mode",
            table,
            f"capacity_check_mode IN ({_MODES})",
        )

    # An operational location must describe at least one physical limit.  A
    # draft/retired row may remain unconfigured while it is being prepared.
    op.create_check_constraint(
        "ck_locations_capacity_configured_when_operational",
        "locations",
        "NOT is_active OR max_pallet_positions IS NOT NULL "
        "OR max_weight_kg IS NOT NULL OR max_volume_m3 IS NOT NULL",
    )

    # Do not leave a migration default attached to future inserts: application
    # validation decides the policy and can distinguish an omitted value.
    op.alter_column("warehouses", "capacity_check_mode", server_default=None)
    op.alter_column("locations", "capacity_check_mode", server_default=None)


def downgrade() -> None:
    # Keep the data-loss guard executable by PostgreSQL itself.  Reading a
    # DBAPI result here makes ``alembic downgrade --sql`` fail because offline
    # migration connections only emit SQL and cannot return rows.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM warehouses
                WHERE max_weight_kg IS NOT NULL OR max_volume_m3 IS NOT NULL
            ) OR EXISTS (
                SELECT 1 FROM locations
                WHERE max_weight_kg IS NOT NULL OR max_volume_m3 IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    'No se puede degradar 0038: existen límites de peso o volumen que se perderían al volver al modelo legacy.';
            END IF;
        END;
        $$;
        """
    )

    op.drop_constraint(
        "ck_locations_capacity_configured_when_operational", "locations", type_="check"
    )
    for table, prefix in (("warehouses", "warehouses"), ("locations", "locations")):
        op.drop_constraint(f"ck_{prefix}_capacity_check_mode", table, type_="check")
        op.drop_constraint(f"ck_{prefix}_max_volume_positive", table, type_="check")
        op.drop_constraint(f"ck_{prefix}_max_weight_positive", table, type_="check")
    op.drop_constraint("ck_locations_pallet_positions_nonnegative", "locations", type_="check")
    op.drop_constraint("ck_warehouses_pallet_positions_nonnegative", "warehouses", type_="check")
    op.drop_column("warehouses", "capacity_check_mode")
    op.drop_column("warehouses", "max_volume_m3")
    op.drop_column("warehouses", "max_weight_kg")
    op.drop_column("locations", "capacity_check_mode")
    op.drop_column("locations", "max_volume_m3")
    op.drop_column("locations", "max_weight_kg")
    op.alter_column(
        "warehouses",
        "max_pallet_positions",
        new_column_name="capacity",
        existing_type=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "locations",
        "max_pallet_positions",
        new_column_name="capacity",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.create_check_constraint("ck_locations_capacity_positive", "locations", "capacity > 0")
    op.create_check_constraint(
        "ck_warehouses_capacity", "warehouses", "capacity IS NULL OR capacity > 0"
    )
