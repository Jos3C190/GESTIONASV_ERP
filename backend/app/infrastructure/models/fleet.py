"""Fleet, drivers and vehicle operations, scoped to a company and a home branch.

Every table carries ``company_id`` and references its parents through composite
``(company_id, id)`` keys so a row can never point at another tenant's data,
even if application code had a bug. Vehicles and drivers belong to exactly one
home branch; branch users only see their own branch (see ``fleet_scope``).
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
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, column_property, mapped_column

from app.infrastructure.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin
from app.infrastructure.models.employee import Employee

VEHICLE_KINDS = (
    "refrigerated",
    "cargo_van",
    "dry_box",
    "pickup",
    "flatbed",
    "compact_van",
    "curtain_side",
    "semi_trailer",
    "tanker",
)
VEHICLE_STATUSES = ("active", "maintenance", "out_of_service", "retired")
FUEL_TYPES = ("diesel", "gasoline", "lpg", "electric", "hybrid")
LICENSE_CLASSES = ("particular", "liviana", "pesada", "pesada_t", "motocicleta")
DRIVER_STATUSES = ("active", "suspended", "inactive")
ODOMETER_SOURCES = ("manual", "fuel", "maintenance", "gps")
MAINTENANCE_KINDS = ("preventive", "corrective")
MAINTENANCE_STATUSES = ("scheduled", "in_progress", "completed", "cancelled")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({','.join(repr(value) for value in values)})"


def _company_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )


def _user_fk(nullable: bool = True) -> Mapped[uuid.UUID | None]:
    return mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=nullable
    )


class FleetVehicleModel(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "fleet_vehicles"

    company_id: Mapped[uuid.UUID] = _company_fk()
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    plate: Mapped[str] = mapped_column(String(16), nullable=False)
    vin: Mapped[str | None] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    brand: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str | None] = mapped_column(String(40))
    capacity_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fuel_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="diesel")
    odometer_km: Mapped[Decimal] = mapped_column(Numeric(12, 1), nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    #: Status to go back to when the last order in progress ends.
    status_before_maintenance: Mapped[str | None] = mapped_column(String(16))
    gps_device_unique_id: Mapped[str | None] = mapped_column(String(64))
    traccar_device_id: Mapped[int | None] = mapped_column(Integer)
    inventory_vehicle_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = _user_fk()
    updated_by: Mapped[uuid.UUID | None] = _user_fk()

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_fleet_vehicles_company_id"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_fleet_vehicles_branch_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "inventory_vehicle_id"],
            ["inventory_vehicles.company_id", "inventory_vehicles.id"],
            name="fk_fleet_vehicles_inventory_vehicle_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("kind", VEHICLE_KINDS), name="ck_fleet_vehicles_kind"),
        CheckConstraint(_in("status", VEHICLE_STATUSES), name="ck_fleet_vehicles_status"),
        CheckConstraint(_in("fuel_type", FUEL_TYPES), name="ck_fleet_vehicles_fuel_type"),
        CheckConstraint("year BETWEEN 1950 AND 2100", name="ck_fleet_vehicles_year"),
        CheckConstraint("capacity_kg > 0", name="ck_fleet_vehicles_capacity"),
        CheckConstraint("odometer_km >= 0", name="ck_fleet_vehicles_odometer"),
        CheckConstraint(
            "(gps_device_unique_id IS NULL) = (traccar_device_id IS NULL)",
            name="ck_fleet_vehicles_gps_pair",
        ),
        Index(
            "uq_fleet_vehicles_company_code_visible",
            "company_id",
            func.lower(code),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_fleet_vehicles_company_plate_visible",
            "company_id",
            func.upper(plate),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_fleet_vehicles_company_vin_visible",
            "company_id",
            func.upper(vin),
            unique=True,
            postgresql_where=text("vin IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_fleet_vehicles_gps_device_visible",
            "gps_device_unique_id",
            unique=True,
            postgresql_where=text("gps_device_unique_id IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_fleet_vehicles_inventory_vehicle",
            "inventory_vehicle_id",
            unique=True,
            postgresql_where=text("inventory_vehicle_id IS NOT NULL"),
        ),
        Index("ix_fleet_vehicles_company_branch_status", "company_id", "branch_id", "status"),
        {"comment": "Fleet vehicles with a single home branch."},
    )


class FleetVehiclePhotoModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "fleet_vehicle_photos"

    company_id: Mapped[uuid.UUID] = _company_fk()
    vehicle_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    public_id: Mapped[str] = mapped_column(String(512), nullable=False)
    caption: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    uploaded_by: Mapped[uuid.UUID | None] = _user_fk()

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "vehicle_id"],
            ["fleet_vehicles.company_id", "fleet_vehicles.id"],
            name="fk_fleet_vehicle_photos_vehicle_company",
            ondelete="CASCADE",
        ),
        Index("ix_fleet_vehicle_photos_vehicle", "vehicle_id", "position"),
    )


class DriverModel(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "drivers"

    company_id: Mapped[uuid.UUID] = _company_fk()
    employee_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    license_class: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    status_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = _user_fk()
    updated_by: Mapped[uuid.UUID | None] = _user_fk()
    #: Employee's full name, for listings such as the trash.
    display_name: Mapped[str] = column_property(
        select(func.concat(Employee.first_name, " ", Employee.last_name))
        .where(Employee.id == employee_id)
        .correlate_except(Employee)
        .scalar_subquery()
    )

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_drivers_company_id"),
        ForeignKeyConstraint(
            ["company_id", "employee_id"],
            ["employees.company_id", "employees.id"],
            name="fk_drivers_employee_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_drivers_branch_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("license_class", LICENSE_CLASSES), name="ck_drivers_license_class"),
        CheckConstraint(_in("status", DRIVER_STATUSES), name="ck_drivers_status"),
        Index(
            "uq_drivers_company_employee_visible",
            "company_id",
            "employee_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_drivers_company_branch_status", "company_id", "branch_id", "status"),
        {"comment": "Driver profiles; every driver is an employee of the same company."},
    )


class VehicleDriverAssignmentModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "vehicle_driver_assignments"

    company_id: Mapped[uuid.UUID] = _company_fk()
    vehicle_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    driver_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[uuid.UUID | None] = _user_fk()
    ended_by: Mapped[uuid.UUID | None] = _user_fk()
    end_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "vehicle_id"],
            ["fleet_vehicles.company_id", "fleet_vehicles.id"],
            name="fk_vehicle_driver_assignments_vehicle_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "driver_id"],
            ["drivers.company_id", "drivers.id"],
            name="fk_vehicle_driver_assignments_driver_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "ends_at IS NULL OR ends_at >= starts_at", name="ck_vehicle_driver_assignments_dates"
        ),
        Index(
            "uq_vehicle_driver_assignments_open_vehicle",
            "vehicle_id",
            unique=True,
            postgresql_where=text("ends_at IS NULL"),
        ),
        Index(
            "uq_vehicle_driver_assignments_open_driver",
            "driver_id",
            unique=True,
            postgresql_where=text("ends_at IS NULL"),
        ),
        Index("ix_vehicle_driver_assignments_driver", "driver_id", "starts_at"),
    )


class OdometerReadingModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "fleet_odometer_readings"

    company_id: Mapped[uuid.UUID] = _company_fk()
    vehicle_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    reading_km: Mapped[Decimal] = mapped_column(Numeric(12, 1), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[uuid.UUID | None] = _user_fk()

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "vehicle_id"],
            ["fleet_vehicles.company_id", "fleet_vehicles.id"],
            name="fk_fleet_odometer_readings_vehicle_company",
            ondelete="CASCADE",
        ),
        CheckConstraint("reading_km >= 0", name="ck_fleet_odometer_readings_positive"),
        CheckConstraint(_in("source", ODOMETER_SOURCES), name="ck_fleet_odometer_readings_source"),
        Index("ix_fleet_odometer_readings_vehicle_time", "vehicle_id", "read_at"),
    )


class MaintenancePlanModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "fleet_maintenance_plans"

    company_id: Mapped[uuid.UUID] = _company_fk()
    vehicle_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    interval_km: Mapped[int | None] = mapped_column(Integer)
    interval_days: Mapped[int | None] = mapped_column(Integer)
    last_service_km: Mapped[Decimal | None] = mapped_column(Numeric(12, 1))
    last_service_on: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[uuid.UUID | None] = _user_fk()

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_fleet_maintenance_plans_company_id"),
        ForeignKeyConstraint(
            ["company_id", "vehicle_id"],
            ["fleet_vehicles.company_id", "fleet_vehicles.id"],
            name="fk_fleet_maintenance_plans_vehicle_company",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "interval_km IS NOT NULL OR interval_days IS NOT NULL",
            name="ck_fleet_maintenance_plans_interval",
        ),
        CheckConstraint(
            "(interval_km IS NULL OR interval_km > 0) AND (interval_days IS NULL OR interval_days > 0)",
            name="ck_fleet_maintenance_plans_positive",
        ),
        Index(
            "uq_fleet_maintenance_plans_vehicle_name",
            "vehicle_id",
            func.lower(name),
            unique=True,
            postgresql_where=text("is_active IS TRUE"),
        ),
    )


class MaintenanceOrderModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "fleet_maintenance_orders"

    company_id: Mapped[uuid.UUID] = _company_fk()
    vehicle_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="scheduled")
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    workshop: Mapped[str | None] = mapped_column(String(160))
    scheduled_on: Mapped[date | None] = mapped_column(Date)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    odometer_km: Mapped[Decimal | None] = mapped_column(Numeric(12, 1))
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = _user_fk()
    closed_by: Mapped[uuid.UUID | None] = _user_fk()

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "vehicle_id"],
            ["fleet_vehicles.company_id", "fleet_vehicles.id"],
            name="fk_fleet_maintenance_orders_vehicle_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "plan_id"],
            ["fleet_maintenance_plans.company_id", "fleet_maintenance_plans.id"],
            name="fk_fleet_maintenance_orders_plan_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint(_in("kind", MAINTENANCE_KINDS), name="ck_fleet_maintenance_orders_kind"),
        CheckConstraint(
            _in("status", MAINTENANCE_STATUSES), name="ck_fleet_maintenance_orders_status"
        ),
        CheckConstraint("cost IS NULL OR cost >= 0", name="ck_fleet_maintenance_orders_cost"),
        CheckConstraint(
            "status <> 'completed' OR (completed_at IS NOT NULL AND odometer_km IS NOT NULL)",
            name="ck_fleet_maintenance_orders_completion",
        ),
        Index("ix_fleet_maintenance_orders_vehicle_status", "vehicle_id", "status"),
    )


class FuelLogModel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "fleet_fuel_logs"

    company_id: Mapped[uuid.UUID] = _company_fk()
    vehicle_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    driver_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    liters: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    odometer_km: Mapped[Decimal] = mapped_column(Numeric(12, 1), nullable=False)
    full_tank: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    station: Mapped[str | None] = mapped_column(String(160))
    receipt_document_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("document_records.id", ondelete="SET NULL")
    )
    recorded_by: Mapped[uuid.UUID | None] = _user_fk()

    __table_args__ = (
        ForeignKeyConstraint(
            ["company_id", "vehicle_id"],
            ["fleet_vehicles.company_id", "fleet_vehicles.id"],
            name="fk_fleet_fuel_logs_vehicle_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id", "driver_id"],
            ["drivers.company_id", "drivers.id"],
            name="fk_fleet_fuel_logs_driver_company",
            ondelete="RESTRICT",
        ),
        CheckConstraint("liters > 0", name="ck_fleet_fuel_logs_liters"),
        CheckConstraint("total_amount >= 0", name="ck_fleet_fuel_logs_amount"),
        CheckConstraint("odometer_km >= 0", name="ck_fleet_fuel_logs_odometer"),
        Index("ix_fleet_fuel_logs_vehicle_time", "vehicle_id", "filled_at"),
    )
