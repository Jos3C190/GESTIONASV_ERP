"""ORM models for companies, branches, warehouses and physical locations."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDPKMixin


class GeographicDepartment(UUIDPKMixin, Base):
    __tablename__ = "geographic_departments"
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)


class Municipality(UUIDPKMixin, Base):
    __tablename__ = "municipalities"
    department_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("geographic_departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    __table_args__ = (
        UniqueConstraint("department_id", "name", name="uq_municipalities_department_name"),
    )


class District(UUIDPKMixin, Base):
    __tablename__ = "districts"
    municipality_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("municipalities.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    __table_args__ = (
        UniqueConstraint("municipality_id", "name", name="uq_districts_municipality_name"),
    )


class Company(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "companies"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    commercial_name: Mapped[str] = mapped_column(String(200), nullable=False)
    nit: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    nrc: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    commercial_line_1: Mapped[str | None] = mapped_column(String(200))
    commercial_line_2: Mapped[str | None] = mapped_column(String(200))
    commercial_line_3: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("geographic_departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    municipality_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("municipalities.id", ondelete="RESTRICT"), nullable=False
    )
    district_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("districts.id", ondelete="RESTRICT"), nullable=False
    )
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    web_site: Mapped[str | None] = mapped_column(String(2048))
    logo: Mapped[str | None] = mapped_column(String(2048))
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")


class Branch(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "branches"
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("geographic_departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    municipality_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("municipalities.id", ondelete="RESTRICT"), nullable=False
    )
    district_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("districts.id", ondelete="RESTRICT"), nullable=False
    )
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_branches_company_name"),)


class WarehouseCategory(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "warehouse_categories"
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")


class Warehouse(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "warehouses"
    branch_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("warehouse_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    __table_args__ = (UniqueConstraint("branch_id", "name", name="uq_warehouses_branch_name"),)


class Location(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "locations"
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    aisle: Mapped[str] = mapped_column(String(64), nullable=False)
    rack: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[str] = mapped_column(String(64), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_locations_capacity_positive"),
        UniqueConstraint("warehouse_id", "code", name="uq_locations_warehouse_code"),
        UniqueConstraint(
            "warehouse_id",
            "aisle",
            "rack",
            "level",
            "position",
            name="uq_locations_warehouse_coordinates",
        ),
    )
