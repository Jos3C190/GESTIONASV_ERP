"""Redis-backed OCR processing and private document derivatives."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None

PERMISSION = ("documents:process", "Procesar documentos y reintentar OCR", "documents")


def upgrade() -> None:
    code, description, module = PERMISSION
    op.execute(
        "INSERT INTO permissions (id, code, description, module, created_at) "
        f"VALUES (gen_random_uuid(), '{code}', '{description}', '{module}', now()) "
        "ON CONFLICT DO NOTHING"
    )
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id, created_at) "
        "SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p "
        "WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE "
        "AND r.company_id IS NULL AND r.deleted_at IS NULL "
        f"AND p.deleted_at IS NULL AND p.code = '{code}' "
        "ON CONFLICT DO NOTHING"
    )

    op.create_table(
        "document_derivatives",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("bucket", sa.String(63), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("content_type", sa.String(160), nullable=False, server_default="application/pdf"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("etag", sa.String(128), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_code", sa.String(80), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("object_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["document_assets.id"], ondelete="CASCADE"),
        sa.CheckConstraint("kind IN ('ocr_pdf')", name="ck_document_derivatives_kind"),
        sa.CheckConstraint(
            "status IN ('pending','processing','ready','failed','skipped')",
            name="ck_document_derivatives_status",
        ),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes > 0",
            name="ck_document_derivatives_positive_size",
        ),
        sa.UniqueConstraint("document_id", "kind", name="uq_document_derivatives_document_kind"),
        sa.UniqueConstraint("bucket", "object_key", name="uq_document_derivatives_bucket_key"),
    )
    op.create_index(
        "ix_document_derivatives_company_status_created",
        "document_derivatives",
        ["company_id", "status", "created_at"],
    )
    op.create_index(
        "ix_document_derivatives_status_started",
        "document_derivatives",
        ["status", "started_at"],
    )
    op.create_index("ix_document_derivatives_document_id", "document_derivatives", ["document_id"])


def downgrade() -> None:
    code, _description, _module = PERMISSION
    op.drop_table("document_derivatives")
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        f"(SELECT id FROM permissions WHERE code = '{code}')"
    )
    op.execute(f"DELETE FROM permissions WHERE code = '{code}'")
