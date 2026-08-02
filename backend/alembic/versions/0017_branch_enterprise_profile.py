"""Extend branch enterprise infrastructure profile.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

COLUMNS = (
    sa.Column("appraised_value", sa.Numeric(14, 2)),
    sa.Column("monthly_maintenance", sa.Numeric(12, 2)),
    sa.Column("last_renovation", sa.Date()),
    sa.Column("electrical_capacity_kva", sa.Numeric(10, 2)),
    sa.Column("internet_provider", sa.String(120)),
    sa.Column("internet_type", sa.String(24)),
    sa.Column("water_source", sa.String(24)),
    sa.Column("ac_system", sa.String(24)),
    sa.Column("lighting", sa.String(24)),
    sa.Column("exterior_material", sa.String(24)),
    sa.Column("floor_material", sa.String(24)),
    sa.Column("roof_capacity_kg_m2", sa.Numeric(10, 2)),
    sa.Column("cleaning_provider", sa.String(200)),
    sa.Column("last_inspection", sa.Date()),
)


def upgrade() -> None:
    for column in COLUMNS:
        op.add_column("branches", column)


def downgrade() -> None:
    for column in reversed(COLUMNS):
        op.drop_column("branches", column.name)
