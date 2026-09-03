from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class DocumentCategoryModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "document_categories"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    module: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    group_name: Mapped[str] = mapped_column(String(120), nullable=False, default="General")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("module IN ('general','employees')", name="ck_document_categories_module"),
        UniqueConstraint(
            "company_id", "module", "code", name="uq_document_categories_company_module_code"
        ),
        Index(
            "uq_document_categories_company_module_name",
            "company_id",
            "module",
            func.lower(name),
            unique=True,
        ),
        Index("ix_document_categories_company_module_active", "company_id", "module", "is_active"),
    )


class DocumentRecordModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "document_records"

    # The UUID is deliberately the same value as document_assets.id.  It keeps
    # URLs and lifecycle/audit identifiers stable while giving the asset a
    # business-level projection.
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("document_assets.id", ondelete="CASCADE"), primary_key=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    module: Mapped[str] = mapped_column(String(32), nullable=False, default="general")
    owner_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    issuer: Mapped[str | None] = mapped_column(String(180), nullable=True)
    issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidentiality: Mapped[str] = mapped_column(String(16), nullable=False, default="restricted")
    tags: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list
    )
    version_group_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    replaces_document_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("document_records.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("module IN ('general','employees')", name="ck_document_records_module"),
        CheckConstraint(
            "(module = 'general' AND owner_type IS NULL AND owner_id IS NULL) OR "
            "(module = 'employees' AND owner_type = 'employee' AND owner_id IS NOT NULL)",
            name="ck_document_records_owner",
        ),
        CheckConstraint(
            "confidentiality IN ('internal','restricted')",
            name="ck_document_records_confidentiality",
        ),
        CheckConstraint("version_number > 0", name="ck_document_records_version_positive"),
        CheckConstraint(
            "expires_on IS NULL OR issued_on IS NULL OR expires_on >= issued_on",
            name="ck_document_records_dates",
        ),
        UniqueConstraint("version_group_id", "version_number", name="uq_document_records_version"),
        Index(
            "uq_document_records_current_version",
            "version_group_id",
            unique=True,
            postgresql_where=text("is_current IS TRUE"),
        ),
        Index(
            "ix_document_records_company_module_owner",
            "company_id",
            "module",
            "owner_type",
            "owner_id",
        ),
        Index("ix_document_records_company_category", "company_id", "category_id"),
        Index("ix_document_records_company_expiry", "company_id", "expires_on"),
        Index("ix_document_records_group_current", "version_group_id", "is_current"),
    )
