"""Persist recursive General-folder import sessions and item progress."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "document_general_imports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("parent_id", UUID(as_uuid=True), nullable=True),
        sa.Column("root_entry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="preparing"),
        sa.Column("metadata_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_folders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_entries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("completed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_id"], ["document_general_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["root_entry_id"], ["document_general_entries.id"], ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('preparing','ready','running','completed','partial','cancelled','expired')", name="ck_document_general_imports_status"),
    )
    op.create_index("ix_document_general_imports_company_status", "document_general_imports", ["company_id", "status"])
    op.create_table(
        "document_general_import_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("import_id", UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("source_path", sa.String(2000), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("resolved_path", sa.String(2000), nullable=False),
        sa.Column("resolved_name", sa.String(200), nullable=False),
        sa.Column("parent_folder_id", UUID(as_uuid=True), nullable=True),
        sa.Column("entry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("content_type", sa.String(160), nullable=True),
        sa.Column("extension", sa.String(16), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="ready"),
        sa.Column("failure_code", sa.String(80), nullable=True),
        sa.Column("failure_message", sa.String(500), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["import_id"], ["document_general_imports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_folder_id"], ["document_general_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["entry_id"], ["document_general_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["document_records.id"], ondelete="SET NULL"),
        sa.CheckConstraint("kind IN ('folder','file')", name="ck_document_general_import_items_kind"),
        sa.CheckConstraint("status IN ('ready','authorized','completed','skipped','failed_retryable','failed_permanent','cancelled')", name="ck_document_general_import_items_status"),
    )
    op.create_index("ix_document_general_import_items_import_status", "document_general_import_items", ["import_id", "status"])
    op.create_index("ix_document_general_import_items_document", "document_general_import_items", ["document_id"])

def downgrade() -> None:
    op.drop_table("document_general_import_items")
    op.drop_index("ix_document_general_imports_company_status", table_name="document_general_imports")
    op.drop_table("document_general_imports")
