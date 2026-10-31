"""Track handling-unit lineage and allow estimated physical measures after splits."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_handling_units",
        sa.Column("origin_handling_unit_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_inventory_handling_units_origin_company",
        "inventory_handling_units",
        "inventory_handling_units",
        ["company_id", "origin_handling_unit_id"],
        ["company_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_inventory_handling_units_origin",
        "inventory_handling_units",
        ["company_id", "origin_handling_unit_id"],
    )
    op.drop_constraint(
        "ck_inventory_handling_units_measurement_source",
        "inventory_handling_units",
        type_="check",
    )
    op.create_check_constraint(
        "ck_inventory_handling_units_measurement_source",
        "inventory_handling_units",
        "measurement_source IN ('master','receipt','manual','device','split_estimate')",
    )
    op.drop_constraint(
        "ck_inventory_handling_units_actual_measure_evidence",
        "inventory_handling_units",
        type_="check",
    )
    op.create_check_constraint(
        "ck_inventory_handling_units_actual_measure_evidence",
        "inventory_handling_units",
        "measurement_status = 'incomplete' OR measurement_source IN ('master','split_estimate') "
        "OR (actual_gross_weight_kg IS NOT NULL AND actual_volume_m3 IS NOT NULL)",
    )


def downgrade() -> None:
    bind = op.get_bind()
    has_split_units = bind.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM inventory_handling_units "
            "WHERE origin_handling_unit_id IS NOT NULL OR measurement_source = 'split_estimate')"
        )
    )
    if has_split_units:
        raise RuntimeError(
            "No se puede revertir 0075 mientras existan unidades fraccionadas: "
            "se perdería su trazabilidad de origen."
        )

    op.drop_constraint(
        "ck_inventory_handling_units_actual_measure_evidence",
        "inventory_handling_units",
        type_="check",
    )
    op.create_check_constraint(
        "ck_inventory_handling_units_actual_measure_evidence",
        "inventory_handling_units",
        "measurement_status = 'incomplete' OR measurement_source = 'master' "
        "OR (actual_gross_weight_kg IS NOT NULL AND actual_volume_m3 IS NOT NULL)",
    )
    op.drop_constraint(
        "ck_inventory_handling_units_measurement_source",
        "inventory_handling_units",
        type_="check",
    )
    op.create_check_constraint(
        "ck_inventory_handling_units_measurement_source",
        "inventory_handling_units",
        "measurement_source IN ('master','receipt','manual','device')",
    )
    op.drop_index("ix_inventory_handling_units_origin", table_name="inventory_handling_units")
    op.drop_constraint(
        "fk_inventory_handling_units_origin_company",
        "inventory_handling_units",
        type_="foreignkey",
    )
    op.drop_column("inventory_handling_units", "origin_handling_unit_id")
