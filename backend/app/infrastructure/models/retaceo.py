"""ORM models for retaceo landed-cost allocations."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class RetaceoModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "retaceos"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    purchase_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("currencies.code", ondelete="RESTRICT"),
        nullable=False,
    )
    total_fob: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    total_freight: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    total_expenses: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    total_dai: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    import_vat: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    details: Mapped[list[RetaceoDetailModel]] = relationship(
        "RetaceoDetailModel",
        back_populates="retaceo",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="RetaceoDetailModel.created_at",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_id", "company_id"],
            ["purchases.id", "purchases.company_id"],
            name="fk_retaceos_purchase_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_retaceos_branch_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('draft','calculated','verified','cancelled','closed')",
            name="ck_retaceos_status",
        ),
        CheckConstraint(
            "char_length(currency) = 3 AND currency = upper(currency)",
            name="ck_retaceos_currency",
        ),
        CheckConstraint("total_fob > 0", name="ck_retaceos_fob_positive"),
        CheckConstraint(
            "total_freight >= 0 AND total_expenses >= 0 AND total_dai >= 0 "
            "AND import_vat >= 0 AND total_cost >= 0",
            name="ck_retaceos_amounts_nonnegative",
        ),
        CheckConstraint(
            "total_cost = total_fob + total_freight + total_expenses + total_dai",
            name="ck_retaceos_total_cost",
        ),
        Index("uq_retaceos_id_company", "id", "company_id", unique=True),
        Index("uq_retaceos_company_code", "company_id", "code", unique=True),
        Index("ix_retaceos_company_status_created", "company_id", "status", "created_at"),
        Index("ix_retaceos_purchase_created", "purchase_id", "created_at"),
        Index("ix_retaceos_branch_created", "branch_id", "created_at"),
    )


class RetaceoDetailModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "retaceo_details"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    retaceo_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchase_detail_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    cost_fob: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    freight: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    expenses: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    dai: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0"), server_default="0"
    )
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    retaceo: Mapped[RetaceoModel] = relationship("RetaceoModel", back_populates="details")

    __table_args__ = (
        ForeignKeyConstraint(
            ["retaceo_id", "company_id"],
            ["retaceos.id", "retaceos.company_id"],
            name="fk_retaceo_details_retaceo_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["purchase_detail_id", "company_id"],
            ["purchase_details.id", "purchase_details.company_id"],
            name="fk_retaceo_details_purchase_detail_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            name="fk_retaceo_details_product_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            name="fk_retaceo_details_unit_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantity > 0", name="ck_retaceo_details_quantity_positive"),
        CheckConstraint(
            "cost_fob >= 0 AND freight >= 0 AND expenses >= 0 AND dai >= 0 "
            "AND total_cost >= 0 AND unit_cost >= 0",
            name="ck_retaceo_details_amounts_nonnegative",
        ),
        CheckConstraint(
            "total_cost = cost_fob + freight + expenses + dai",
            name="ck_retaceo_details_total_cost",
        ),
        Index("uq_retaceo_details_id_company", "id", "company_id", unique=True),
        Index(
            "uq_retaceo_details_retaceo_purchase_detail",
            "retaceo_id",
            "purchase_detail_id",
            unique=True,
        ),
        Index("ix_retaceo_details_retaceo_created", "retaceo_id", "created_at"),
        Index(
            "ix_retaceo_details_company_purchase_detail",
            "company_id",
            "purchase_detail_id",
        ),
    )
