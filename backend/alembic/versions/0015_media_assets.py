"""Add centralized media asset metadata.

Revision ID: 0015
Revises: 0014
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE")),
        sa.Column("provider", sa.String(32), nullable=False, server_default="cloudinary"),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("public_id", sa.String(500), nullable=False),
        sa.Column("secure_url", sa.Text, nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("bytes", sa.BigInteger, nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="staged"),
        sa.Column("owner_type", sa.String(32)),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True)),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "public_id", name="uq_media_provider_public_id"),
    )
    for column in ("company_id", "purpose", "owner_type", "owner_id", "uploaded_by"):
        op.create_index(f"ix_media_assets_{column}", "media_assets", [column])


def downgrade() -> None:
    op.drop_table("media_assets")
