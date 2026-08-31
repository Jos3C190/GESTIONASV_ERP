from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class DocumentDerivativeModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "document_derivatives"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("document_assets.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    bucket: Mapped[str] = mapped_column(String(63), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(160), nullable=False, default="application/pdf"
    )
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    etag: Mapped[str | None] = mapped_column(String(128))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    object_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("kind IN ('ocr_pdf')", name="ck_document_derivatives_kind"),
        CheckConstraint(
            "status IN ('pending','processing','ready','failed','skipped')",
            name="ck_document_derivatives_status",
        ),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes > 0",
            name="ck_document_derivatives_positive_size",
        ),
        UniqueConstraint("document_id", "kind", name="uq_document_derivatives_document_kind"),
        UniqueConstraint("bucket", "object_key", name="uq_document_derivatives_bucket_key"),
    )
