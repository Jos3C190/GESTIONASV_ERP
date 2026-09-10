from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class DocumentGeneralImportModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "document_general_imports"
    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("document_general_entries.id", ondelete="SET NULL"))
    root_entry_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("document_general_entries.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="preparing")
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    total_files: Mapped[int] = mapped_column(nullable=False, default=0)
    total_folders: Mapped[int] = mapped_column(nullable=False, default=0)
    total_entries: Mapped[int] = mapped_column(nullable=False, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    completed_files: Mapped[int] = mapped_column(nullable=False, default=0)
    skipped_files: Mapped[int] = mapped_column(nullable=False, default=0)
    failed_files: Mapped[int] = mapped_column(nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_document_general_imports_company_status", "company_id", "status"),)

class DocumentGeneralImportItemModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "document_general_import_items"
    import_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("document_general_imports.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    resolved_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    resolved_name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_folder_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("document_general_entries.id", ondelete="SET NULL"))
    entry_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("document_general_entries.id", ondelete="SET NULL"))
    document_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("document_records.id", ondelete="SET NULL"))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    content_type: Mapped[str | None] = mapped_column(String(160))
    extension: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ready")
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    __table_args__ = (Index("ix_document_general_import_items_import_status", "import_id", "status"), Index("ix_document_general_import_items_document", "document_id"))

__all__ = ["DocumentGeneralImportItemModel", "DocumentGeneralImportModel"]
