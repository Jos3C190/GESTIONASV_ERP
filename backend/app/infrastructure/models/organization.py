"""ORM models for companies, branches, warehouses and physical locations."""

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.entities.warehouse_capacity import CapacityStatus, capacity_status_for
from app.infrastructure.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


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


class Company(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "companies"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    commercial_name: Mapped[str] = mapped_column(String(200), nullable=False)
    nit: Mapped[str] = mapped_column(String(32), nullable=False)
    nrc: Mapped[str] = mapped_column(String(32), nullable=False)
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
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    __table_args__ = (
        Index(
            "uq_companies_nit_visible",
            func.lower(nit),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_companies_nrc_visible",
            func.lower(nrc),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )


class Branch(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "branches"
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32))
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
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    operational_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    manager_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("employees.id", ondelete="SET NULL")
    )
    opened_at: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    schedule: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    zone: Mapped[str | None] = mapped_column(String(120))
    services: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    facilities: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    images: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    area: Mapped[float | None] = mapped_column(Numeric(12, 2))
    area_built: Mapped[float | None] = mapped_column(Numeric(12, 2))
    area_unbuilt: Mapped[float | None] = mapped_column(Numeric(12, 2))
    floors: Mapped[int | None] = mapped_column(Integer)
    parking: Mapped[int | None] = mapped_column(Integer)
    people_capacity: Mapped[int | None] = mapped_column(Integer)
    property_type: Mapped[str | None] = mapped_column(String(24))
    offices: Mapped[int | None] = mapped_column(Integer)
    meeting_rooms: Mapped[int | None] = mapped_column(Integer)
    bathrooms: Mapped[int | None] = mapped_column(Integer)
    accesses: Mapped[int | None] = mapped_column(Integer)
    emergency_exits: Mapped[int | None] = mapped_column(Integer)
    accessibility: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    construction_type: Mapped[str | None] = mapped_column(String(32))
    construction_year: Mapped[int | None] = mapped_column(Integer)
    building_condition: Mapped[str | None] = mapped_column(String(20))
    cadastral_code: Mapped[str | None] = mapped_column(String(80))
    permit_expiry: Mapped[date | None] = mapped_column(Date)
    lease_expiry: Mapped[date | None] = mapped_column(Date)
    landlord: Mapped[str | None] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(2048))
    cctv_cameras: Mapped[int | None] = mapped_column(Integer)
    access_control: Mapped[str | None] = mapped_column(String(32))
    has_alarm: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    fire_system: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    has_backup_generator: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    has_ups: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    appraised_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    monthly_maintenance: Mapped[float | None] = mapped_column(Numeric(12, 2))
    last_renovation: Mapped[date | None] = mapped_column(Date)
    electrical_capacity_kva: Mapped[float | None] = mapped_column(Numeric(10, 2))
    internet_provider: Mapped[str | None] = mapped_column(String(120))
    internet_type: Mapped[str | None] = mapped_column(String(24))
    water_source: Mapped[str | None] = mapped_column(String(24))
    ac_system: Mapped[str | None] = mapped_column(String(24))
    lighting: Mapped[str | None] = mapped_column(String(24))
    exterior_material: Mapped[str | None] = mapped_column(String(24))
    floor_material: Mapped[str | None] = mapped_column(String(24))
    roof_capacity_kg_m2: Mapped[float | None] = mapped_column(Numeric(10, 2))
    cleaning_provider: Mapped[str | None] = mapped_column(String(200))
    last_inspection: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    __table_args__ = (
        UniqueConstraint("id", "company_id", name="uq_branches_id_company_id"),
        Index(
            "uq_branches_company_name_visible",
            "company_id",
            func.lower(name),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_branches_company_code_visible",
            "company_id",
            func.lower(code),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_branches_company_deleted_at", "company_id", "deleted_at"),
    )


class WarehouseCategory(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "warehouse_categories"
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    __table_args__ = (
        Index(
            "uq_warehouse_categories_company_name_visible",
            "company_id",
            func.lower(name),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_warehouse_categories_company_id", "company_id"),
        Index("ix_warehouse_categories_company_deleted_at", "company_id", "deleted_at"),
    )


class Warehouse(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
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
    code: Mapped[str | None] = mapped_column(String(32))
    warehouse_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="general"
    )
    operational_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    physical_location: Mapped[str | None] = mapped_column(String(200))
    manager_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("employees.id", ondelete="SET NULL")
    )
    area: Mapped[float | None] = mapped_column(Numeric(12, 2))
    height: Mapped[float | None] = mapped_column(Numeric(12, 2))
    length: Mapped[float | None] = mapped_column(Numeric(12, 2))
    width: Mapped[float | None] = mapped_column(Numeric(12, 2))
    shelves_total: Mapped[int | None] = mapped_column(Integer)
    certified_max_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    operational_max_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    certified_usable_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    operational_usable_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    capacity_profile: Mapped[str] = mapped_column(
        String(32), nullable=False, default="general_mixed", server_default="general_mixed"
    )
    capacity_enforcement_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="disabled", server_default="disabled"
    )
    storage_eligible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    usable_length_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    usable_width_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    usable_height_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    shifts: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    cameras: Mapped[int | None] = mapped_column(Integer)
    access_control: Mapped[str | None] = mapped_column(String(32))
    has_alarm: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    fire_system: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    last_security_audit: Mapped[date | None] = mapped_column(Date)
    temperature_range: Mapped[str | None] = mapped_column(String(64))
    humidity_range: Mapped[str | None] = mapped_column(String(64))
    cooling: Mapped[str | None] = mapped_column(String(32))
    has_ventilation: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    last_maintenance: Mapped[date | None] = mapped_column(Date)
    next_maintenance: Mapped[date | None] = mapped_column(Date)
    maintenance_notes: Mapped[str | None] = mapped_column(Text)
    sanitary_permit: Mapped[str | None] = mapped_column(String(120))
    sanitary_permit_expiry: Mapped[date | None] = mapped_column(Date)
    last_inspection: Mapped[date | None] = mapped_column(Date)
    certifications: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    description: Mapped[str | None] = mapped_column(Text)
    images: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")

    @property
    def capacity_status(self) -> CapacityStatus:
        return capacity_status_for(self)

    __table_args__ = (
        CheckConstraint(
            "operational_status IN ('active','inactive','maintenance')",
            name="ck_warehouses_operational_status",
        ),
        CheckConstraint(
            "capacity_profile IN ('general_mixed','rack','bulk_floor','cold','oversize_manual','transit')",
            name="ck_warehouses_capacity_profile",
        ),
        CheckConstraint(
            "capacity_enforcement_mode IN ('disabled','observe','enforce')",
            name="ck_warehouses_capacity_enforcement_mode",
        ),
        CheckConstraint(
            "certified_max_weight_kg IS NULL OR certified_max_weight_kg > 0",
            name="ck_warehouses_certified_max_weight_kg_positive",
        ),
        CheckConstraint(
            "operational_max_weight_kg IS NULL OR operational_max_weight_kg > 0",
            name="ck_warehouses_operational_max_weight_kg_positive",
        ),
        CheckConstraint(
            "certified_usable_volume_m3 IS NULL OR certified_usable_volume_m3 > 0",
            name="ck_warehouses_certified_usable_volume_m3_positive",
        ),
        CheckConstraint(
            "operational_usable_volume_m3 IS NULL OR operational_usable_volume_m3 > 0",
            name="ck_warehouses_operational_usable_volume_m3_positive",
        ),
        CheckConstraint(
            "operational_max_weight_kg IS NULL OR "
            "(certified_max_weight_kg IS NOT NULL AND "
            "operational_max_weight_kg <= certified_max_weight_kg)",
            name="ck_warehouses_operational_weight_within_certified",
        ),
        CheckConstraint(
            "operational_usable_volume_m3 IS NULL OR "
            "(certified_usable_volume_m3 IS NOT NULL AND "
            "operational_usable_volume_m3 <= certified_usable_volume_m3)",
            name="ck_warehouses_operational_volume_within_certified",
        ),
        CheckConstraint(
            "(usable_length_m IS NULL AND usable_width_m IS NULL AND usable_height_m IS NULL) "
            "OR (usable_length_m IS NOT NULL AND usable_width_m IS NOT NULL "
            "AND usable_height_m IS NOT NULL)",
            name="ck_warehouses_usable_dimensions_complete",
        ),
        CheckConstraint(
            "usable_length_m IS NULL OR usable_length_m > 0",
            name="ck_warehouses_usable_length_m_positive",
        ),
        CheckConstraint(
            "usable_width_m IS NULL OR usable_width_m > 0",
            name="ck_warehouses_usable_width_m_positive",
        ),
        CheckConstraint(
            "usable_height_m IS NULL OR usable_height_m > 0",
            name="ck_warehouses_usable_height_m_positive",
        ),
        CheckConstraint(
            "storage_eligible OR capacity_enforcement_mode = 'disabled'",
            name="ck_warehouses_nonstorage_capacity_disabled",
        ),
        CheckConstraint(
            "capacity_enforcement_mode <> 'enforce' OR "
            "(storage_eligible AND certified_max_weight_kg IS NOT NULL "
            "AND operational_max_weight_kg IS NOT NULL "
            "AND certified_usable_volume_m3 IS NOT NULL "
            "AND operational_usable_volume_m3 IS NOT NULL)",
            name="ck_warehouses_enforce_capacity_complete",
        ),
        Index(
            "uq_warehouses_branch_name_visible",
            "branch_id",
            func.lower(name),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_warehouses_branch_code_visible",
            "branch_id",
            func.lower(code),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_warehouses_branch_deleted_at", "branch_id", "deleted_at"),
    )


class UserCompany(Base):
    __tablename__ = "user_companies"
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    access_all_branches: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    last_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(nullable=False, server_default="now()")
    __table_args__ = (
        ForeignKeyConstraint(
            ["last_branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_user_companies_last_branch_company",
            ondelete="RESTRICT",
        ),
    )


class UserBranch(Base):
    """Explicit administrative access to a branch.

    This authorization is intentionally independent from an employee's labor
    assignment to a branch.
    """

    __tablename__ = "user_branches"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "company_id"],
            ["user_companies.user_id", "user_companies.company_id"],
            name="fk_user_branches_membership",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_user_branches_branch_company",
            ondelete="CASCADE",
        ),
        Index(
            "uq_user_branches_default_active",
            "user_id",
            "company_id",
            unique=True,
            postgresql_where=text("is_active AND is_default"),
        ),
    )


class WarehouseCapacityGroup(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Warehouse-scoped structural capacity shared by descendant locations."""

    __tablename__ = "warehouse_capacity_groups"

    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    group_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="structural", server_default="structural"
    )
    certified_max_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    operational_max_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    certified_usable_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    operational_usable_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    capacity_profile: Mapped[str] = mapped_column(
        String(32), nullable=False, default="general_mixed", server_default="general_mixed"
    )
    capacity_enforcement_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="disabled", server_default="disabled"
    )
    storage_eligible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    usable_length_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    usable_width_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    usable_height_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    @property
    def capacity_status(self) -> CapacityStatus:
        return capacity_status_for(self)

    __table_args__ = (
        UniqueConstraint(
            "id", "warehouse_id", name="uq_capacity_groups_identity_warehouse"
        ),
        ForeignKeyConstraint(
            ["parent_id", "warehouse_id"],
            ["warehouse_capacity_groups.id", "warehouse_capacity_groups.warehouse_id"],
            name="fk_capacity_groups_parent_warehouse",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_capacity_groups_not_self_parent",
        ),
        CheckConstraint(
            "group_type IN ('structural','rack','bay','level','floor_zone','cold_chamber','transit_zone')",
            name="ck_capacity_groups_type",
        ),
        CheckConstraint(
            "capacity_profile IN ('general_mixed','rack','bulk_floor','cold','oversize_manual','transit')",
            name="ck_capacity_groups_capacity_profile",
        ),
        CheckConstraint(
            "capacity_enforcement_mode IN ('disabled','observe','enforce')",
            name="ck_capacity_groups_capacity_enforcement_mode",
        ),
        CheckConstraint(
            "certified_max_weight_kg IS NULL OR certified_max_weight_kg > 0",
            name="ck_capacity_groups_certified_max_weight_kg_positive",
        ),
        CheckConstraint(
            "operational_max_weight_kg IS NULL OR operational_max_weight_kg > 0",
            name="ck_capacity_groups_operational_max_weight_kg_positive",
        ),
        CheckConstraint(
            "certified_usable_volume_m3 IS NULL OR certified_usable_volume_m3 > 0",
            name="ck_capacity_groups_certified_usable_volume_m3_positive",
        ),
        CheckConstraint(
            "operational_usable_volume_m3 IS NULL OR operational_usable_volume_m3 > 0",
            name="ck_capacity_groups_operational_usable_volume_m3_positive",
        ),
        CheckConstraint(
            "operational_max_weight_kg IS NULL OR "
            "(certified_max_weight_kg IS NOT NULL AND "
            "operational_max_weight_kg <= certified_max_weight_kg)",
            name="ck_capacity_groups_operational_weight_within_certified",
        ),
        CheckConstraint(
            "operational_usable_volume_m3 IS NULL OR "
            "(certified_usable_volume_m3 IS NOT NULL AND "
            "operational_usable_volume_m3 <= certified_usable_volume_m3)",
            name="ck_capacity_groups_operational_volume_within_certified",
        ),
        CheckConstraint(
            "(usable_length_m IS NULL AND usable_width_m IS NULL AND usable_height_m IS NULL) "
            "OR (usable_length_m IS NOT NULL AND usable_width_m IS NOT NULL "
            "AND usable_height_m IS NOT NULL)",
            name="ck_capacity_groups_usable_dimensions_complete",
        ),
        CheckConstraint(
            "usable_length_m IS NULL OR usable_length_m > 0",
            name="ck_capacity_groups_usable_length_m_positive",
        ),
        CheckConstraint(
            "usable_width_m IS NULL OR usable_width_m > 0",
            name="ck_capacity_groups_usable_width_m_positive",
        ),
        CheckConstraint(
            "usable_height_m IS NULL OR usable_height_m > 0",
            name="ck_capacity_groups_usable_height_m_positive",
        ),
        CheckConstraint(
            "storage_eligible OR capacity_enforcement_mode = 'disabled'",
            name="ck_capacity_groups_nonstorage_capacity_disabled",
        ),
        CheckConstraint(
            "capacity_enforcement_mode <> 'enforce' OR "
            "(storage_eligible AND certified_max_weight_kg IS NOT NULL "
            "AND operational_max_weight_kg IS NOT NULL "
            "AND certified_usable_volume_m3 IS NOT NULL "
            "AND operational_usable_volume_m3 IS NOT NULL)",
            name="ck_capacity_groups_enforce_capacity_complete",
        ),
        Index(
            "uq_capacity_groups_warehouse_code_visible",
            "warehouse_id",
            func.lower(code),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_capacity_groups_warehouse_parent", "warehouse_id", "parent_id"),
    )


class Location(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "locations"
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    capacity_group_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    area: Mapped[str | None] = mapped_column(String(64))
    aisle: Mapped[str] = mapped_column(String(64), nullable=False)
    rack: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[str] = mapped_column(String(64), nullable=False)
    certified_max_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    operational_max_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    certified_usable_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    operational_usable_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    capacity_profile: Mapped[str] = mapped_column(
        String(32), nullable=False, default="general_mixed", server_default="general_mixed"
    )
    capacity_enforcement_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="disabled", server_default="disabled"
    )
    storage_eligible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    usable_length_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    usable_width_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    usable_height_m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    location_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="standard"
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="active"
    )
    barcode: Mapped[str | None] = mapped_column(String(120))
    verification_code: Mapped[str | None] = mapped_column(String(120))
    pick_sequence: Mapped[int | None] = mapped_column(Integer)
    putaway_sequence: Mapped[int | None] = mapped_column(Integer)
    external_id: Mapped[str | None] = mapped_column(String(120))
    code_scheme_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True)
    )
    scheme_version: Mapped[int | None] = mapped_column(Integer)
    code_source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="legacy")
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")

    @property
    def capacity_status(self) -> CapacityStatus:
        return capacity_status_for(self)

    __table_args__ = (
        UniqueConstraint("id", "warehouse_id", name="uq_locations_identity_warehouse"),
        ForeignKeyConstraint(
            ["code_scheme_id", "warehouse_id", "scheme_version"],
            [
                "location_code_schemes.id",
                "location_code_schemes.warehouse_id",
                "location_code_schemes.version",
            ],
            name="fk_locations_scheme_scope_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["capacity_group_id", "warehouse_id"],
            ["warehouse_capacity_groups.id", "warehouse_capacity_groups.warehouse_id"],
            name="fk_locations_capacity_group_warehouse",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(code_scheme_id IS NULL) = (scheme_version IS NULL)",
            name="ck_locations_scheme_reference_complete",
        ),
        CheckConstraint(
            "(lifecycle_status = 'retired') = (is_active = false)",
            name="ck_locations_lifecycle_active_consistent",
        ),
        CheckConstraint(
            "capacity_profile IN ('general_mixed','rack','bulk_floor','cold','oversize_manual','transit')",
            name="ck_locations_capacity_profile",
        ),
        CheckConstraint(
            "capacity_enforcement_mode IN ('disabled','observe','enforce')",
            name="ck_locations_capacity_enforcement_mode",
        ),
        CheckConstraint(
            "certified_max_weight_kg IS NULL OR certified_max_weight_kg > 0",
            name="ck_locations_certified_max_weight_kg_positive",
        ),
        CheckConstraint(
            "operational_max_weight_kg IS NULL OR operational_max_weight_kg > 0",
            name="ck_locations_operational_max_weight_kg_positive",
        ),
        CheckConstraint(
            "certified_usable_volume_m3 IS NULL OR certified_usable_volume_m3 > 0",
            name="ck_locations_certified_usable_volume_m3_positive",
        ),
        CheckConstraint(
            "operational_usable_volume_m3 IS NULL OR operational_usable_volume_m3 > 0",
            name="ck_locations_operational_usable_volume_m3_positive",
        ),
        CheckConstraint(
            "operational_max_weight_kg IS NULL OR "
            "(certified_max_weight_kg IS NOT NULL AND "
            "operational_max_weight_kg <= certified_max_weight_kg)",
            name="ck_locations_operational_weight_within_certified",
        ),
        CheckConstraint(
            "operational_usable_volume_m3 IS NULL OR "
            "(certified_usable_volume_m3 IS NOT NULL AND "
            "operational_usable_volume_m3 <= certified_usable_volume_m3)",
            name="ck_locations_operational_volume_within_certified",
        ),
        CheckConstraint(
            "(usable_length_m IS NULL AND usable_width_m IS NULL AND usable_height_m IS NULL) "
            "OR (usable_length_m IS NOT NULL AND usable_width_m IS NOT NULL "
            "AND usable_height_m IS NOT NULL)",
            name="ck_locations_usable_dimensions_complete",
        ),
        CheckConstraint(
            "usable_length_m IS NULL OR usable_length_m > 0",
            name="ck_locations_usable_length_m_positive",
        ),
        CheckConstraint(
            "usable_width_m IS NULL OR usable_width_m > 0",
            name="ck_locations_usable_width_m_positive",
        ),
        CheckConstraint(
            "usable_height_m IS NULL OR usable_height_m > 0",
            name="ck_locations_usable_height_m_positive",
        ),
        CheckConstraint(
            "storage_eligible OR capacity_enforcement_mode = 'disabled'",
            name="ck_locations_nonstorage_capacity_disabled",
        ),
        CheckConstraint(
            "capacity_enforcement_mode <> 'enforce' OR "
            "(storage_eligible AND certified_max_weight_kg IS NOT NULL "
            "AND operational_max_weight_kg IS NOT NULL "
            "AND certified_usable_volume_m3 IS NOT NULL "
            "AND operational_usable_volume_m3 IS NOT NULL)",
            name="ck_locations_enforce_capacity_complete",
        ),
        CheckConstraint(
            "pick_sequence IS NULL OR pick_sequence >= 0",
            name="ck_locations_pick_sequence_nonnegative",
        ),
        CheckConstraint(
            "putaway_sequence IS NULL OR putaway_sequence >= 0",
            name="ck_locations_putaway_sequence_nonnegative",
        ),
        CheckConstraint(
            "lifecycle_status IN ('draft','active','blocked','blocked_in','blocked_out','maintenance','retired')",
            name="ck_locations_lifecycle_status",
        ),
        CheckConstraint(
            "location_type IN ('standard','bulk','receiving','reserve','picking','staging','quality','packing','shipping','returns','virtual')",
            name="ck_locations_type",
        ),
        CheckConstraint(
            "code_source IN ('legacy','generated','imported','recode')",
            name="ck_locations_code_source",
        ),
        Index(
            "uq_locations_warehouse_code_visible",
            "warehouse_id",
            func.lower(code),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_locations_warehouse_coordinates_visible",
            "warehouse_id",
            text("coalesce(area, '')"),
            "aisle",
            "rack",
            "level",
            "position",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_locations_warehouse_capacity_group",
            "warehouse_id",
            "capacity_group_id",
        ),
        Index(
            "uq_locations_warehouse_barcode_visible",
            "warehouse_id",
            func.lower(barcode),
            unique=True,
            postgresql_where=text("barcode IS NOT NULL AND deleted_at IS NULL"),
            sqlite_where=text("barcode IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_locations_warehouse_verification_visible",
            "warehouse_id",
            func.lower(verification_code),
            unique=True,
            postgresql_where=text("verification_code IS NOT NULL AND deleted_at IS NULL"),
            sqlite_where=text("verification_code IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_locations_warehouse_external_id_visible",
            "warehouse_id",
            func.lower(external_id),
            unique=True,
            postgresql_where=text("external_id IS NOT NULL AND deleted_at IS NULL"),
            sqlite_where=text("external_id IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "ix_locations_warehouse_status_code",
            "warehouse_id",
            "lifecycle_status",
            "code",
        ),
        Index("ix_locations_warehouse_deleted_at", "warehouse_id", "deleted_at"),
    )
