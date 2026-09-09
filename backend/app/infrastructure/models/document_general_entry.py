from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class DocumentGeneralDeletionBatchModel(UUIDPKMixin, Base):
    __tablename__ = "document_general_deletion_batches"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (Index("ix_document_general_deletion_batches_company", "company_id"),)


class DocumentGeneralEntryModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "document_general_entries"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_general_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("document_records.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_general_deletion_batches.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("kind IN ('folder','file')", name="ck_document_general_entries_kind"),
        CheckConstraint(
            "(kind = 'folder' AND document_id IS NULL) OR "
            "(kind = 'file' AND document_id IS NOT NULL)",
            name="ck_document_general_entries_document",
        ),
        Index(
            "uq_document_general_entries_sibling_name",
            "company_id",
            text("coalesce(parent_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "normalized_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_document_general_entries_company_parent", "company_id", "parent_id"),
        Index("ix_document_general_entries_company_document", "company_id", "document_id"),
        Index("ix_document_general_entries_deletion_batch", "deletion_batch_id"),
    )


__all__ = ["DocumentGeneralDeletionBatchModel", "DocumentGeneralEntryModel"]
