"""ORM models: SupplierModel, SupplierContactModel."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.models.catalog import CountryModel
    from app.infrastructure.models.supplier_image import (
        SupplierContactImageModel,
        SupplierImageModel,
    )
    from app.infrastructure.models.supplier_master_data import (
        PaymentTermsModel,
        SupplierAddressModel,
        SupplierBankAccountModel,
        SupplierGroupModel,
        SupplierTaxIdentifierModel,
    )


class SupplierModel(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "suppliers"

    id_supplier: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    country_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("countries.id_country", ondelete="RESTRICT"), nullable=False, index=True
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True, default=None)
    website: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    legal_name: Mapped[str | None] = mapped_column(String(240), nullable=True, default=None)
    supplier_group_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    supplier_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="approved")
    hold_reason: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
    hold_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    hold_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    default_currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True, default=None)
    payment_terms_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    default_payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)
    external_reference: Mapped[str | None] = mapped_column(String(120), nullable=True, default=None)
    __table_args__ = (
        Index(
            "uq_suppliers_company_code_visible",
            "company_id",
            func.lower(code),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_suppliers_company_active_name", "company_id", "is_active", "name"),
        Index("ix_suppliers_company_deleted_at", "company_id", "deleted_at"),
        ForeignKeyConstraint(
            ["supplier_group_id", "company_id"],
            ["supplier_groups.id", "supplier_groups.company_id"],
            name="fk_suppliers_supplier_group_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["payment_terms_id", "company_id"],
            ["payment_terms.id", "payment_terms.company_id"],
            name="fk_suppliers_payment_terms_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "supplier_status IN ('pending_review', 'approved', 'on_hold', 'suspended', 'rejected', 'retired')",
            name="ck_suppliers_status",
        ),
        CheckConstraint(
            "hold_until IS NULL OR hold_from IS NULL OR hold_until >= hold_from",
            name="ck_suppliers_hold_range",
        ),
    )

    country: Mapped[CountryModel] = relationship("CountryModel", back_populates="suppliers")
    image: Mapped[SupplierImageModel | None] = relationship(
        "SupplierImageModel",
        back_populates="supplier",
        uselist=False,
        cascade="all, delete-orphan",
    )
    contacts: Mapped[list[SupplierContactModel]] = relationship(
        "SupplierContactModel", back_populates="supplier", cascade="all, delete-orphan"
    )
    supplier_group: Mapped[SupplierGroupModel | None] = relationship(
        "SupplierGroupModel", back_populates="suppliers", foreign_keys=[supplier_group_id]
    )
    payment_terms: Mapped[PaymentTermsModel | None] = relationship(
        "PaymentTermsModel", back_populates="suppliers", foreign_keys=[payment_terms_id]
    )
    tax_identifiers: Mapped[list[SupplierTaxIdentifierModel]] = relationship(
        "SupplierTaxIdentifierModel", back_populates="supplier", cascade="all, delete-orphan"
    )
    addresses: Mapped[list[SupplierAddressModel]] = relationship(
        "SupplierAddressModel", back_populates="supplier", cascade="all, delete-orphan"
    )
    bank_accounts: Mapped[list[SupplierBankAccountModel]] = relationship(
        "SupplierBankAccountModel", back_populates="supplier", cascade="all, delete-orphan"
    )


class SupplierContactModel(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "supplier_contacts"
    __table_args__ = (
        Index("ix_supplier_contacts_supplier_deleted_at", "id_supplier", "deleted_at"),
    )

    id_supplier_contact: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, unique=True, index=True, server_default=text("gen_random_uuid()")
    )
    id_supplier: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id_supplier", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    supplier: Mapped[SupplierModel] = relationship("SupplierModel", back_populates="contacts")
    image: Mapped[SupplierContactImageModel | None] = relationship(
        "SupplierContactImageModel",
        back_populates="supplier_contact",
        uselist=False,
        cascade="all, delete-orphan",
    )
