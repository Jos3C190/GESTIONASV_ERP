"""Normalized supplier master data and protected banking records."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class CurrencyModel(TimestampMixin, Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    symbol: Mapped[str] = mapped_column(String(8), nullable=False)
    decimal_places: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="2")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        CheckConstraint("code = upper(code) AND char_length(code) = 3", name="ck_currencies_iso_code"),
        CheckConstraint("decimal_places BETWEEN 0 AND 6", name="ck_currencies_decimal_places"),
        Index("ix_currencies_active_code", "is_active", "code"),
    )


class SupplierGroupModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "supplier_groups"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_supplier_groups_company_id"),
        UniqueConstraint("company_id", "code", name="uq_supplier_groups_company_code"),
        Index("ix_supplier_groups_company_active", "company_id", "is_active"),
    )
    suppliers = relationship("SupplierModel", back_populates="supplier_group", overlaps="payment_terms,suppliers")


class PaymentTermsModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "payment_terms"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    net_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    discount_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_payment_terms_company_id"),
        UniqueConstraint("company_id", "code", name="uq_payment_terms_company_code"),
        CheckConstraint("net_days >= 0", name="ck_payment_terms_net_days"),
        CheckConstraint("discount_days BETWEEN 0 AND net_days", name="ck_payment_terms_discount_days"),
        CheckConstraint("discount_percent BETWEEN 0 AND 100", name="ck_payment_terms_discount_percent"),
        Index("ix_payment_terms_company_active", "company_id", "is_active"),
    )
    suppliers = relationship("SupplierModel", back_populates="payment_terms", overlaps="supplier_group,suppliers")


class SupplierTaxIdentifierModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "supplier_tax_identifiers"

    supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id_supplier", ondelete="CASCADE"), nullable=False, index=True
    )
    country_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("countries.id_country", ondelete="RESTRICT"), nullable=False
    )
    identifier_type: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(200), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "supplier_id", "country_id", "identifier_type", "normalized_value",
            name="uq_supplier_tax_identifier_value",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from",
            name="ck_supplier_tax_identifier_dates",
        ),
        Index("uq_supplier_tax_identifiers_primary_country", "supplier_id", "country_id", unique=True, postgresql_where=text("is_primary = true")),
    )
    supplier = relationship("SupplierModel", back_populates="tax_identifiers")
    country = relationship("CountryModel")


class SupplierAddressModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "supplier_addresses"

    supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id_supplier", ondelete="CASCADE"), nullable=False, index=True
    )
    address_type: Mapped[str] = mapped_column(String(24), nullable=False, server_default="other")
    line1: Mapped[str] = mapped_column(String(240), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(240), nullable=True)
    country_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("countries.id_country", ondelete="RESTRICT"), nullable=True
    )
    state_region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    __table_args__ = (
        CheckConstraint(
            "address_type IN ('fiscal', 'billing', 'delivery', 'return', 'office', 'other')",
            name="ck_supplier_addresses_type",
        ),
        Index("uq_supplier_addresses_primary_type", "supplier_id", "address_type", unique=True, postgresql_where=text("is_primary = true")),
    )
    supplier = relationship("SupplierModel", back_populates="addresses")
    country = relationship("CountryModel")


class SupplierBankAccountModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "supplier_bank_accounts"

    supplier_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id_supplier", ondelete="CASCADE"), nullable=False, index=True
    )
    bank_name: Mapped[str] = mapped_column(String(160), nullable=False)
    account_holder: Mapped[str] = mapped_column(String(200), nullable=False)
    country_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("countries.id_country", ondelete="RESTRICT"), nullable=True
    )
    currency_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=True
    )
    account_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    account_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    iban_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    encryption_key_version: Mapped[str] = mapped_column(String(32), nullable=False, server_default="v1")
    last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        CheckConstraint("char_length(last_four) = 4", name="ck_supplier_bank_last_four"),
        CheckConstraint("status IN ('active', 'blocked', 'closed')", name="ck_supplier_bank_status"),
        Index("uq_supplier_bank_accounts_primary", "supplier_id", unique=True, postgresql_where=text("is_primary = true")),
    )
    supplier = relationship("SupplierModel", back_populates="bank_accounts")
    country = relationship("CountryModel")
    currency = relationship("CurrencyModel")
