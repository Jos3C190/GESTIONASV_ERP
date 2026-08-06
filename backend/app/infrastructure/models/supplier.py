"""ORM models: SupplierModel, SupplierContactModel."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.models.catalog import CountryModel


class SupplierModel(TimestampMixin, Base):
    __tablename__ = "suppliers"

    id_supplier: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    uuid: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
        server_default=text("gen_random_uuid()"),
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    country_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("countries.id_country", ondelete="RESTRICT"), nullable=False, index=True
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True, default=None)
    website: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    country: Mapped[CountryModel] = relationship("CountryModel", back_populates="suppliers")
    contacts: Mapped[list[SupplierContactModel]] = relationship(
        "SupplierContactModel", back_populates="supplier", cascade="all, delete-orphan"
    )


class SupplierContactModel(TimestampMixin, Base):
    __tablename__ = "supplier_contacts"

    id_supplier_contact: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    id_supplier: Mapped[int] = mapped_column(
        Integer, ForeignKey("suppliers.id_supplier", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    supplier: Mapped[SupplierModel] = relationship("SupplierModel", back_populates="contacts")
