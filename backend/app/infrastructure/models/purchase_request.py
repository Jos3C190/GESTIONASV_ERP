"""ORM models for purchase requests and their lines."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class PurchaseRequestModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_requests"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    request_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    required_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    details: Mapped[list[PurchaseRequestDetailModel]] = relationship(
        "PurchaseRequestDetailModel",
        back_populates="purchase_request",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PurchaseRequestDetailModel.created_at",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_purchase_requests_branch_company",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "company_id", name="uq_purchase_requests_id_company_id"),
        UniqueConstraint("company_id", "code", name="uq_purchase_requests_company_code"),
        CheckConstraint(
            "status IN "
            "('draft','submitted','approved','rejected','partially_quoted',"
            "'quoted','partially_ordered','completed','cancelled')",
            name="ck_purchase_requests_status",
        ),
        Index(
            "ix_purchase_requests_company_status_date",
            "company_id",
            "status",
            "request_date",
        ),
        Index("ix_purchase_requests_branch_status", "branch_id", "status"),
        Index("ix_purchase_requests_warehouse_status", "warehouse_id", "status"),
        Index("ix_purchase_requests_requested_by", "requested_by_id"),
    )


class PurchaseRequestDetailModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_request_details"

    purchase_request_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    purchase_request: Mapped[PurchaseRequestModel] = relationship(
        "PurchaseRequestModel",
        back_populates="details",
    )

    __table_args__ = (
        UniqueConstraint(
            "id",
            "company_id",
            name="uq_purchase_request_details_id_company_id",
        ),
        ForeignKeyConstraint(
            ["purchase_request_id", "company_id"],
            ["purchase_requests.id", "purchase_requests.company_id"],
            name="fk_purchase_request_details_request_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            name="fk_purchase_request_details_product_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            name="fk_purchase_request_details_unit_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantity > 0", name="ck_purchase_request_details_quantity_positive"),
        Index(
            "ix_purchase_request_details_request",
            "purchase_request_id",
            "created_at",
        ),
        Index(
            "ix_purchase_request_details_company_product",
            "company_id",
            "product_id",
        ),
    )
