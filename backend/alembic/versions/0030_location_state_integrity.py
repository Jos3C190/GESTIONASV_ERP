"""Enforce complete scheme references and coherent location state."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    has_partial_scheme_reference = bool(
        connection.scalar(
            sa.text(
                "SELECT EXISTS ("
                "SELECT 1 FROM locations "
                "WHERE (code_scheme_id IS NULL) <> (scheme_version IS NULL) "
                "UNION ALL "
                "SELECT 1 FROM location_code_aliases "
                "WHERE (code_scheme_id IS NULL) <> (scheme_version IS NULL)"
                ")"
            )
        )
    )
    if has_partial_scheme_reference:
        raise RuntimeError(
            "No se puede aplicar 0030: existen referencias parciales a esquemas "
            "de ubicación."
        )

    has_inconsistent_lifecycle = bool(
        connection.scalar(
            sa.text(
                "SELECT EXISTS ("
                "SELECT 1 FROM locations "
                "WHERE (lifecycle_status = 'retired') <> (is_active = false)"
                ")"
            )
        )
    )
    if has_inconsistent_lifecycle:
        raise RuntimeError(
            "No se puede aplicar 0030: existen ubicaciones cuyo estado de ciclo "
            "de vida no coincide con is_active."
        )

    op.create_check_constraint(
        "ck_locations_scheme_reference_complete",
        "locations",
        "(code_scheme_id IS NULL) = (scheme_version IS NULL)",
    )
    op.create_check_constraint(
        "ck_location_code_aliases_scheme_reference_complete",
        "location_code_aliases",
        "(code_scheme_id IS NULL) = (scheme_version IS NULL)",
    )
    op.create_check_constraint(
        "ck_locations_lifecycle_active_consistent",
        "locations",
        "(lifecycle_status = 'retired') = (is_active = false)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_locations_lifecycle_active_consistent",
        "locations",
        type_="check",
    )
    op.drop_constraint(
        "ck_location_code_aliases_scheme_reference_complete",
        "location_code_aliases",
        type_="check",
    )
    op.drop_constraint(
        "ck_locations_scheme_reference_complete",
        "locations",
        type_="check",
    )
