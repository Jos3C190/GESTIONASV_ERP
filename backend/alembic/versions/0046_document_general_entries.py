"""Mutable general-document entries and recursive deletion batches."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    op.create_table(
        "document_general_deletion_batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_document_general_deletion_batches_company",
        "document_general_deletion_batches",
        ["company_id"],
    )

    op.create_table(
        "document_general_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("normalized_name", sa.String(200), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletion_batch_id", UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["document_general_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["document_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["deletion_batch_id"], ["document_general_deletion_batches.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint("kind IN ('folder','file')", name="ck_document_general_entries_kind"),
        sa.CheckConstraint(
            "(kind = 'folder' AND document_id IS NULL) OR "
            "(kind = 'file' AND document_id IS NOT NULL)",
            name="ck_document_general_entries_document",
        ),
    )
    op.create_index(
        "uq_document_general_entries_sibling_name",
        "document_general_entries",
        [
            "company_id",
            sa.text("coalesce(parent_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "normalized_name",
        ],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_document_general_entries_company_parent",
        "document_general_entries",
        ["company_id", "parent_id"],
    )
    op.create_index(
        "ix_document_general_entries_company_document",
        "document_general_entries",
        ["company_id", "document_id"],
    )
    op.create_index(
        "ix_document_general_entries_deletion_batch",
        "document_general_entries",
        ["deletion_batch_id"],
    )

    # Only current general records are visible in the new mutable workspace.
    # The technical asset keeps the immutable original_filename untouched.
    op.execute(
        """
        INSERT INTO document_general_entries
          (id, company_id, parent_id, kind, document_id, name, normalized_name,
           created_by, updated_by, created_at, updated_at)
        SELECT gen_random_uuid(), r.company_id, NULL, 'file', r.id,
               left(r.title, 200),
               lower(regexp_replace(btrim(left(r.title, 200)), '\\s+', ' ', 'g')),
               r.created_by, r.updated_by, r.created_at, r.updated_at
        FROM document_records r
        JOIN document_assets a ON a.id = r.id
        WHERE r.module = 'general'
          AND r.is_current IS TRUE
          AND a.deleted_at IS NULL
        ON CONFLICT DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO permissions (id, code, description, module, created_at)
        VALUES (gen_random_uuid(), 'documents:manage_folders',
                'Gestionar carpetas del espacio general', 'documents', now())
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("document_general_entries")
    op.drop_table("document_general_deletion_batches")
    op.execute(
        "DELETE FROM permissions WHERE code = 'documents:manage_folders' "
        "AND id NOT IN (SELECT permission_id FROM role_permissions)"
    )
