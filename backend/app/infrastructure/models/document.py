from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class DocumentAssetModel(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "document_assets"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(16), nullable=False)
    declared_content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    detected_content_type: Mapped[str | None] = mapped_column(String(160))
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    bucket: Mapped[str] = mapped_column(String(63), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    etag: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_upload")
    failure_code: Mapped[str | None] = mapped_column(String(80))
    malware_name: Mapped[str | None] = mapped_column(String(255))
    upload_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scan_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    object_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_document_assets_positive_size"),
        CheckConstraint(
            "status IN ('pending_upload','pending_scan','scanning','active','quarantined','rejected')",
            name="ck_document_assets_status",
        ),
        UniqueConstraint("bucket", "object_key", name="uq_document_assets_bucket_key"),
    )
