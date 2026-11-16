"""ORM models for sales price lists (migration 0122).

The exclusion constraint ``ex_sales_price_list_items_overlap`` (no overlapping validity for
the same list, product, variant, unit and branch) lives only in the migration; the
repository also checks it under a lock to answer with a readable message.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, UUIDPKMixin


def _user_fk() -> ForeignKey:
    return ForeignKey("users.id", ondelete="SET NULL")


class SalesPriceListModel(UUIDPKMixin, Base):
    __tablename__ = "sales_price_lists"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    prices_include_vat: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_sales_price_lists_company_id"),
        UniqueConstraint("company_id", "code", name="uq_sales_price_lists_code"),
        CheckConstraint("code ~ '^[A-Z0-9][A-Z0-9-]{0,19}$'", name="ck_sales_price_lists_code"),
        CheckConstraint("char_length(btrim(name)) >= 2", name="ck_sales_price_lists_name"),
        CheckConstraint("NOT is_default OR is_active", name="ck_sales_price_lists_default_active"),
        Index(
            "uq_sales_price_lists_default",
            "company_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )


class SalesPriceListItemModel(UUIDPKMixin, Base):
    __tablename__ = "sales_price_list_items"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    price_list_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    price: Mapped[Decimal] = mapped_column(Numeric(19, 8), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), _user_fk())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "price_list_id"],
            ["sales_price_lists.company_id", "sales_price_lists.id"],
            ondelete="RESTRICT",
            name="fk_sales_price_list_items_list",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id"],
            ["products.company_id", "products.id_product"],
            ondelete="RESTRICT",
            name="fk_sales_price_list_items_product",
        ),
        ForeignKeyConstraint(
            ["company_id", "product_id", "variant_id"],
            ["product_variants.company_id", "product_variants.product_id", "product_variants.id"],
            ondelete="RESTRICT",
            name="fk_sales_price_list_items_variant",
        ),
        ForeignKeyConstraint(
            ["company_id", "unit_id"],
            ["company_units.company_id", "company_units.unit_id"],
            ondelete="RESTRICT",
            name="fk_sales_price_list_items_unit",
        ),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
            name="fk_sales_price_list_items_branch",
        ),
        CheckConstraint("price >= 0", name="ck_sales_price_list_items_price"),
        CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from", name="ck_sales_price_list_items_validity"
        ),
        Index(
            "ix_sales_price_list_items_lookup",
            "company_id",
            "price_list_id",
            "product_id",
            "unit_id",
            "valid_from",
        ),
    )
