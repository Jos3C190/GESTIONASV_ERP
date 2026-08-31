"""Local S3-compatible document storage and audited lifecycle."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("documents:read", "Consultar documentos", "documents"),
    ("documents:upload", "Cargar documentos", "documents"),
    ("documents:download", "Descargar documentos", "documents"),
    ("documents:delete", "Enviar documentos a la papelera", "documents"),
    ("documents:restore", "Restaurar documentos", "documents"),
)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    for code, description, module in PERMISSIONS:
        op.execute(
            "INSERT INTO permissions (id, code, description, module, created_at) "
            f"VALUES (gen_random_uuid(), {_sql_literal(code)}, "
            f"{_sql_literal(description)}, {_sql_literal(module)}, now()) "
            "ON CONFLICT DO NOTHING"
        )

    permission_codes = ",".join(_sql_literal(code) for code, _description, _module in PERMISSIONS)
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id, created_at) "
        "SELECT r.id, p.id, now() FROM roles r CROSS JOIN permissions p "
        "WHERE r.name = 'SUPER_ADMIN' AND r.is_system IS TRUE "
        "AND r.company_id IS NULL AND r.deleted_at IS NULL "
        f"AND p.deleted_at IS NULL AND p.code IN ({permission_codes}) "
        "ON CONFLICT DO NOTHING"
    )

    op.create_table(
        "document_assets",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("extension", sa.String(16), nullable=False),
        sa.Column("declared_content_type", sa.String(160), nullable=False),
        sa.Column("detected_content_type", sa.String(160), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("bucket", sa.String(63), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("etag", sa.String(128), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_upload"),
        sa.Column("failure_code", sa.String(80), nullable=True),
        sa.Column("malware_name", sa.String(255), nullable=True),
        sa.Column("upload_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scan_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("object_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_by", UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", UUID(as_uuid=True), nullable=True),
        sa.Column("deletion_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("size_bytes > 0", name="ck_document_assets_positive_size"),
        sa.CheckConstraint(
            "status IN ('pending_upload','pending_scan','scanning','active','quarantined','rejected')",
            name="ck_document_assets_status",
        ),
        sa.UniqueConstraint("bucket", "object_key", name="uq_document_assets_bucket_key"),
    )
    op.create_index(
        "ix_document_assets_company_status_created",
        "document_assets",
        ["company_id", "status", "created_at"],
    )
    op.create_index("ix_document_assets_uploaded_by", "document_assets", ["uploaded_by"])
    op.create_index("ix_document_assets_deleted_at", "document_assets", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("document_assets")
    permission_codes = ",".join(_sql_literal(code) for code, _description, _module in PERMISSIONS)
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        f"(SELECT id FROM permissions WHERE code IN ({permission_codes}))"
    )
    op.execute(f"DELETE FROM permissions WHERE code IN ({permission_codes})")
