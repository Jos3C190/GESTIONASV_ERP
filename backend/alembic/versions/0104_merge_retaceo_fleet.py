"""Merge develop's retaceo changes with the fleet/tracking migration branch.

The canonical develop revision 0098 remains unchanged. The parallel fleet
revision is named 0098_fleet to avoid assigning two schemas the same ID.
Databases already at tracking revision 0103 only need the retaceo branch;
databases at develop revision 0098 only need the fleet/tracking branch.

An older feature-only database stopped at 0098 must be identified by its
schema before upgrading: that legacy ID is ambiguous with develop's 0098.
"""

revision = "0104"
down_revision = ("0103", "0098")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
