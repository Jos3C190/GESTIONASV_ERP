"""ORM models for the fiscal issuer base (migration 0118).

Hacienda catalogs are global; everything else belongs to one company, which is the
isolation unit of a DTE issuer.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin

DOCUMENT_TYPES = ("01", "03", "04", "05", "06", "07", "08", "09", "11", "14", "15", "17", "18")
_DOCUMENT_TYPES_SQL = ",".join(f"'{code}'" for code in DOCUMENT_TYPES)


def _user_fk() -> ForeignKey:
    return ForeignKey("users.id", ondelete="SET NULL")


class HaciendaCatalogItemModel(Base):
    __tablename__ = "hacienda_catalog_items"

    catalog_code: Mapped[str] = mapped_column(String(7), primary_key=True)
    group_code: Mapped[str] = mapped_column(String(16), primary_key=True, server_default="")
    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(8), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        CheckConstraint(
            "catalog_code ~ '^CAT-[0-9]{3}$'", name="ck_hacienda_catalog_items_catalog"
        ),
        CheckConstraint("char_length(btrim(name)) > 0", name="ck_hacienda_catalog_items_name"),
    )


class CompanyFiscalProfileModel(Base):
    __tablename__ = "company_fiscal_profiles"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    taxpayer_category: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="other"
    )
    person_type: Mapped[str] = mapped_column(String(1), nullable=False, server_default="2")
    operating_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="simulated"
    )
    dte_email: Mapped[str | None] = mapped_column(String(100))
    dte_phone: Mapped[str | None] = mapped_column(String(30))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "taxpayer_category IN ('large','medium','other')",
            name="ck_company_fiscal_profiles_category",
        ),
        CheckConstraint("person_type IN ('1','2')", name="ck_company_fiscal_profiles_person_type"),
        CheckConstraint(
            "operating_mode IN ('simulated','test','production')",
            name="ck_company_fiscal_profiles_mode",
        ),
        CheckConstraint(
            "dte_email IS NULL OR char_length(dte_email) >= 6",
            name="ck_company_fiscal_profiles_email",
        ),
        CheckConstraint(
            "dte_phone IS NULL OR char_length(dte_phone) >= 8",
            name="ck_company_fiscal_profiles_phone",
        ),
    )


class CompanyEconomicActivityModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "company_economic_activities"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    activity_code: Mapped[str] = mapped_column(String(6), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_company_economic_activities_company_id"),
        UniqueConstraint("company_id", "activity_code", name="uq_company_economic_activities_code"),
        CheckConstraint(
            "activity_code ~ '^[0-9]{5,6}$'", name="ck_company_economic_activities_code"
        ),
        Index(
            "uq_company_economic_activities_primary",
            "company_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )


class FiscalEstablishmentModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "fiscal_establishments"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    establishment_type: Mapped[str] = mapped_column(String(2), nullable=False)
    code: Mapped[str] = mapped_column(String(4), nullable=False)
    activity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_fiscal_establishments_company_id"),
        UniqueConstraint("company_id", "code", name="uq_fiscal_establishments_code"),
        UniqueConstraint("company_id", "branch_id", name="uq_fiscal_establishments_branch"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_fiscal_establishments_branch_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "activity_id"],
            ["company_economic_activities.company_id", "company_economic_activities.id"],
            name="fk_fiscal_establishments_activity",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "establishment_type IN ('01','02','04','07')", name="ck_fiscal_establishments_type"
        ),
        CheckConstraint("code ~ '^[MSBP][0-9]{3}$'", name="ck_fiscal_establishments_code"),
        CheckConstraint(
            "(establishment_type = '02' AND left(code, 1) = 'M') "
            "OR (establishment_type = '01' AND left(code, 1) = 'S') "
            "OR (establishment_type = '04' AND left(code, 1) = 'B') "
            "OR (establishment_type = '07' AND left(code, 1) = 'P')",
            name="ck_fiscal_establishments_code_matches_type",
        ),
    )


class FiscalPointOfSaleModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "fiscal_points_of_sale"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    establishment_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(4), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_fiscal_points_of_sale_company_id"),
        UniqueConstraint("establishment_id", "code", name="uq_fiscal_points_of_sale_code"),
        ForeignKeyConstraint(
            ["company_id", "establishment_id"],
            ["fiscal_establishments.company_id", "fiscal_establishments.id"],
            name="fk_fiscal_points_of_sale_establishment",
            ondelete="RESTRICT",
        ),
        CheckConstraint("code ~ '^P[0-9]{3}$'", name="ck_fiscal_points_of_sale_code"),
        CheckConstraint("char_length(btrim(name)) >= 2", name="ck_fiscal_points_of_sale_name"),
    )


class CompanyDteDocumentTypeModel(Base):
    __tablename__ = "company_dte_document_types"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    document_type: Mapped[str] = mapped_column(String(2), primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    certification_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="pending"
    )
    certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            f"document_type IN ({_DOCUMENT_TYPES_SQL})", name="ck_company_dte_document_types_type"
        ),
        CheckConstraint(
            "certification_status IN ('pending','in_progress','approved')",
            name="ck_company_dte_document_types_status",
        ),
        CheckConstraint(
            "(certification_status = 'approved') = (certified_at IS NOT NULL)",
            name="ck_company_dte_document_types_certified",
        ),
    )


class CompanyEmailSettingsModel(Base):
    """SMTP propio de la empresa para enviar documentos (revisión 0128, bloque V3c)."""

    __tablename__ = "company_email_settings"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    security: Mapped[str] = mapped_column(String(8), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    password_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    from_address: Mapped[str] = mapped_column(String(254), nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(150))
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_test_error: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("port BETWEEN 1 AND 65535", name="ck_company_email_settings_port"),
        CheckConstraint(
            "security IN ('none','starttls','ssl')", name="ck_company_email_settings_security"
        ),
        CheckConstraint("length(btrim(host)) > 0", name="ck_company_email_settings_host"),
        CheckConstraint("from_address LIKE '%_@_%._%'", name="ck_company_email_settings_from"),
        CheckConstraint(
            "password_encrypted IS NULL OR username IS NOT NULL",
            name="ck_company_email_settings_password",
        ),
        CheckConstraint(
            "(last_test_at IS NULL) = (last_test_ok IS NULL) "
            "AND (last_test_ok IS NOT FALSE OR last_test_error IS NOT NULL)",
            name="ck_company_email_settings_test",
        ),
    )
