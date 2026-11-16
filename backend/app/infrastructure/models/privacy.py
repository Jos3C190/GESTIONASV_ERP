"""ORM models for personal data protection (migration 0121)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPKMixin

CHANNELS = "('in_person','phone','email','web','written')"


def _user_fk() -> ForeignKey:
    return ForeignKey("users.id", ondelete="SET NULL")


def _now_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PrivacyNoticeModel(UUIDPKMixin, Base):
    __tablename__ = "company_privacy_notices"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    covered_elements: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False)
    published_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    published_at: Mapped[datetime] = _now_column()

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_company_privacy_notices_company_id"),
        UniqueConstraint("company_id", "version", name="uq_company_privacy_notices_version"),
        CheckConstraint("version >= 1", name="ck_company_privacy_notices_version"),
        CheckConstraint("char_length(btrim(body)) >= 200", name="ck_company_privacy_notices_body"),
    )


class CustomerConsentModel(UUIDPKMixin, Base):
    __tablename__ = "customer_consents"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    notice_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    granted_at: Mapped[datetime] = _now_column()
    granted_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    revocation_channel: Mapped[str | None] = mapped_column(String(16))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "customer_id"],
            ["sales_customers.company_id", "sales_customers.id"],
            name="fk_customer_consents_customer",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "notice_id"],
            ["company_privacy_notices.company_id", "company_privacy_notices.id"],
            name="fk_customer_consents_notice",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "purpose IN ('marketing','profiling','third_party_sharing')",
            name="ck_customer_consents_purpose",
        ),
        CheckConstraint(f"channel IN {CHANNELS}", name="ck_customer_consents_channel"),
        CheckConstraint(
            "(revoked_at IS NULL) = (revocation_channel IS NULL) "
            f"AND (revocation_channel IS NULL OR revocation_channel IN {CHANNELS}) "
            "AND (revoked_at IS NULL OR revoked_at >= granted_at)",
            name="ck_customer_consents_revocation",
        ),
        Index(
            "uq_customer_consents_active",
            "company_id",
            "customer_id",
            "purpose",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class DataSubjectRequestModel(UUIDPKMixin, Base):
    __tablename__ = "data_subject_requests"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    requester_name: Mapped[str] = mapped_column(String(200), nullable=False)
    requester_document: Mapped[str | None] = mapped_column(String(30))
    response_channel: Mapped[str] = mapped_column(String(200), nullable=False)
    right_type: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    received_on: Mapped[date] = mapped_column(Date, nullable=False)
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    correction_due_on: Mapped[date | None] = mapped_column(Date)
    extended_due_on: Mapped[date | None] = mapped_column(Date)
    extension_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="received")
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    resolution: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    created_at: Mapped[datetime] = _now_column()
    updated_at: Mapped[datetime] = _now_column()

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_data_subject_requests_code"),
        ForeignKeyConstraint(
            ["company_id", "customer_id"],
            ["sales_customers.company_id", "sales_customers.id"],
            name="fk_data_subject_requests_customer",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "right_type IN ('access','rectification','cancellation','opposition',"
            "'portability','erasure','restriction')",
            name="ck_data_subject_requests_right",
        ),
        CheckConstraint(
            "status IN ('received','in_progress','awaiting_correction','extended','resolved',"
            "'denied','returned','archived')",
            name="ck_data_subject_requests_status",
        ),
        CheckConstraint("due_on >= received_on", name="ck_data_subject_requests_due"),
        CheckConstraint(
            "(extended_due_on IS NULL) = (extension_reason IS NULL) "
            "AND (extended_due_on IS NULL OR extended_due_on > due_on)",
            name="ck_data_subject_requests_extension",
        ),
        CheckConstraint(
            "(status IN ('resolved','denied','returned','archived')) "
            "= (closed_at IS NOT NULL AND resolution IS NOT NULL)",
            name="ck_data_subject_requests_closed",
        ),
        CheckConstraint(
            "char_length(btrim(requester_name)) >= 3 AND char_length(btrim(description)) >= 5",
            name="ck_data_subject_requests_text",
        ),
        Index("ix_data_subject_requests_open", "company_id", "status", "due_on"),
    )


class PersonalDataIncidentModel(UUIDPKMixin, Base):
    __tablename__ = "personal_data_incidents"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    data_categories: Mapped[str] = mapped_column(Text, nullable=False)
    affected_count: Mapped[int | None] = mapped_column(Integer)
    measures: Mapped[str | None] = mapped_column(Text)
    notified_ace_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ace_reference: Mapped[str | None] = mapped_column(String(200))
    notified_prosecutor_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prosecutor_reference: Mapped[str | None] = mapped_column(String(200))
    notified_subjects_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    subjects_reference: Mapped[str | None] = mapped_column(String(200))
    subjects_not_required_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    created_at: Mapped[datetime] = _now_column()
    updated_at: Mapped[datetime] = _now_column()

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_personal_data_incidents_code"),
        CheckConstraint("status IN ('open','closed')", name="ck_personal_data_incidents_status"),
        CheckConstraint(
            "affected_count IS NULL OR affected_count >= 0",
            name="ck_personal_data_incidents_affected",
        ),
        CheckConstraint(
            "occurred_at IS NULL OR occurred_at <= discovered_at",
            name="ck_personal_data_incidents_occurred",
        ),
        CheckConstraint(
            "(status = 'closed') = (closed_at IS NOT NULL) "
            "AND (status <> 'closed' OR (notified_ace_at IS NOT NULL "
            "AND notified_prosecutor_at IS NOT NULL "
            "AND (notified_subjects_at IS NOT NULL OR subjects_not_required_reason IS NOT NULL)))",
            name="ck_personal_data_incidents_closed",
        ),
    )
