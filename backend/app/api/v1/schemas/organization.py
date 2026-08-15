"""Validated DTOs for companies, branches, warehouses and physical locations."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.api.v1.schemas.common import PageMeta


class AddressIn(BaseModel):
    address: str = Field(min_length=3, max_length=1000)
    department_id: uuid.UUID
    municipality_id: uuid.UUID
    district_id: uuid.UUID


class CompanyIn(AddressIn):
    name: str = Field(min_length=2, max_length=200)
    commercial_name: str = Field(min_length=2, max_length=200)
    nit: str = Field(min_length=3, max_length=32)
    nrc: str = Field(min_length=3, max_length=32)
    commercial_line_1: str | None = Field(None, max_length=200)
    commercial_line_2: str | None = Field(None, max_length=200)
    commercial_line_3: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=32)
    email: EmailStr | None = None
    web_site: str | None = Field(None, max_length=2048)
    logo: str | None = Field(None, max_length=2048)
    description: str | None = Field(None, max_length=4000)


class BranchIn(AddressIn):
    company_id: uuid.UUID
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(None, max_length=32)
    email: EmailStr | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    operational_status: str = Field(default="active", pattern="^(active|inactive|maintenance)$")
    manager_employee_id: uuid.UUID | None = None
    opened_at: date | None = None
    description: str | None = Field(None, max_length=4000)
    schedule: list[dict[str, str | None]] = Field(default_factory=list, max_length=7)
    zone: str | None = Field(None, max_length=120)
    services: list[str] = Field(default_factory=list, max_length=50)
    facilities: list[str] = Field(default_factory=list, max_length=50)
    images: list[dict[str, str]] = Field(default_factory=list, max_length=20)
    area: float | None = Field(None, ge=0)
    area_built: float | None = Field(None, ge=0)
    area_unbuilt: float | None = Field(None, ge=0)
    floors: int | None = Field(None, ge=0)
    parking: int | None = Field(None, ge=0)
    people_capacity: int | None = Field(None, ge=0)
    property_type: str | None = Field(None, max_length=24)
    offices: int | None = Field(None, ge=0)
    meeting_rooms: int | None = Field(None, ge=0)
    bathrooms: int | None = Field(None, ge=0)
    accesses: int | None = Field(None, ge=0)
    emergency_exits: int | None = Field(None, ge=0)
    accessibility: list[str] = Field(default_factory=list, max_length=30)
    construction_type: str | None = Field(None, max_length=32)
    construction_year: int | None = Field(None, ge=1800, le=2200)
    building_condition: str | None = Field(None, max_length=20)
    cadastral_code: str | None = Field(None, max_length=80)
    permit_expiry: date | None = None
    lease_expiry: date | None = None
    landlord: str | None = Field(None, max_length=200)
    website: str | None = Field(None, max_length=2048)
    cctv_cameras: int | None = Field(None, ge=0)
    access_control: str | None = Field(None, max_length=32)
    has_alarm: bool = False
    fire_system: list[str] = Field(default_factory=list, max_length=30)
    has_backup_generator: bool = False
    has_ups: bool = False
    appraised_value: float | None = Field(None, ge=0)
    monthly_maintenance: float | None = Field(None, ge=0)
    last_renovation: date | None = None
    electrical_capacity_kva: float | None = Field(None, ge=0)
    internet_provider: str | None = Field(None, max_length=120)
    internet_type: str | None = Field(None, max_length=24)
    water_source: str | None = Field(None, max_length=24)
    ac_system: str | None = Field(None, max_length=24)
    lighting: str | None = Field(None, max_length=24)
    exterior_material: str | None = Field(None, max_length=24)
    floor_material: str | None = Field(None, max_length=24)
    roof_capacity_kg_m2: float | None = Field(None, ge=0)
    cleaning_provider: str | None = Field(None, max_length=200)
    last_inspection: date | None = None

    @model_validator(mode="after")
    def validate_areas(self) -> BranchIn:
        if self.area is not None and self.area_built is not None and self.area_built > self.area:
            raise ValueError("El área construida no puede superar el área total.")
        if (
            self.area is not None
            and self.area_built is not None
            and self.area_unbuilt is not None
            and self.area_built + self.area_unbuilt > self.area
        ):
            raise ValueError("La suma de áreas construida y libre no puede superar el área total.")
        days = [str(item.get("day", "")).strip() for item in self.schedule]
        if len(days) != len(set(days)):
            raise ValueError("No puede repetir días en el horario.")
        for item in self.schedule:
            opening, closing = item.get("open"), item.get("close")
            if bool(opening) != bool(closing):
                raise ValueError("Cada horario debe incluir apertura y cierre.")
            if opening and closing and opening >= closing:
                raise ValueError("La hora de apertura debe ser anterior al cierre.")
        return self


class WarehouseCategoryIn(BaseModel):
    company_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(None, max_length=2000)


class WarehouseListSummary(BaseModel):
    total_capacity: int = 0
    total_used: int = 0
    total_products: int = 0
    active: int = 0
    full: int = 0
    maintenance: int = 0
    inactive: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    branches: list[dict[str, str]] = Field(default_factory=list)


class WarehousePage(BaseModel):
    items: list[dict[str, Any]]
    meta: PageMeta
    summary: WarehouseListSummary


class WarehouseIn(BaseModel):
    branch_id: uuid.UUID
    warehouse_category_id: uuid.UUID
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(None, max_length=4000)
    warehouse_type: str = Field(
        default="general",
        pattern="^(general|cold_storage|hazmat|transit|bonded|automated)$",
    )
    operational_status: str = Field(
        default="active", pattern="^(active|inactive|maintenance|full)$"
    )
    physical_location: str | None = Field(None, max_length=200)
    manager_employee_id: uuid.UUID | None = None
    area: float | None = Field(None, ge=0)
    height: float | None = Field(None, ge=0)
    length: float | None = Field(None, ge=0)
    width: float | None = Field(None, ge=0)
    shelves_total: int | None = Field(None, ge=0)
    capacity: int | None = Field(None, gt=0)
    shifts: list[str] = Field(default_factory=list, max_length=3)
    cameras: int | None = Field(None, ge=0)
    access_control: str | None = Field(
        None, pattern="^(biometrico|tarjetas|teclado|doble_llave|sin_control)$"
    )
    has_alarm: bool = False
    fire_system: list[str] = Field(default_factory=list, max_length=30)
    last_security_audit: date | None = None
    temperature_range: str | None = Field(None, max_length=64)
    humidity_range: str | None = Field(None, max_length=64)
    cooling: str | None = Field(
        None,
        pattern="^(industrial_ac|refrigeracion|ventilacion_natural|mixto|sin_climatizacion)$",
    )
    has_ventilation: bool = False
    last_maintenance: date | None = None
    next_maintenance: date | None = None
    maintenance_notes: str | None = Field(None, max_length=4000)
    sanitary_permit: str | None = Field(None, max_length=120)
    sanitary_permit_expiry: date | None = None
    last_inspection: date | None = None
    certifications: list[str] = Field(default_factory=list, max_length=30)
    images: list[dict[str, str]] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_operational_data(self) -> WarehouseIn:
        allowed_shifts = {"mañana", "tarde", "noche"}
        if len(set(self.shifts)) != len(self.shifts):
            raise ValueError("Los turnos del almacén no pueden repetirse.")
        if any(shift not in allowed_shifts for shift in self.shifts):
            raise ValueError("Uno o más turnos del almacén no son válidos.")
        if (
            self.last_maintenance
            and self.next_maintenance
            and self.next_maintenance < self.last_maintenance
        ):
            raise ValueError(
                "El próximo mantenimiento no puede ser anterior al último mantenimiento."
            )
        if self.sanitary_permit_expiry and not self.sanitary_permit:
            raise ValueError("Debe indicar el permiso sanitario antes de registrar su vencimiento.")
        return self


class LocationIn(BaseModel):
    warehouse_id: uuid.UUID
    # Kept only so older clients do not fail validation during rollout.  The
    # server ignores it and always projects the code from physical coordinates.
    code: str | None = Field(None, min_length=1, max_length=120, deprecated=True)
    aisle: str = Field(min_length=1, max_length=64)
    rack: str = Field(min_length=1, max_length=64)
    level: str = Field(min_length=1, max_length=64)
    position: str = Field(min_length=1, max_length=64)
    capacity: int = Field(gt=0)
    notes: str | None = Field(None, max_length=4000)


class GeographicDepartmentIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class MunicipalityIn(BaseModel):
    department_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)


class DistrictIn(BaseModel):
    municipality_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)
