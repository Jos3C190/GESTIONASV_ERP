"""Fleet and driver DTOs."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

#: A code from the company's vehicle type catalogue; the routers check it exists.
VehicleKind = Annotated[str, Field(pattern=r"^[a-z0-9_]{2,24}$")]
VehicleStatus = Literal["active", "maintenance", "out_of_service", "retired"]
ManualVehicleStatus = Literal["active", "out_of_service", "retired"]
OperationalStatus = Literal["available", "in_route", "maintenance", "out_of_service", "retired"]
FuelType = Literal["diesel", "gasoline", "lpg", "electric", "hybrid", "none"]
MeterUnit = Literal["km", "hours"]
#: The silhouettes in the frontend's static images, calibrated to carry the logo.
BaseImage = Literal[
    "refrigerated",
    "cargo_van",
    "dry_box",
    "pickup",
    "flatbed",
    "compact_van",
    "curtain_side",
    "semi_trailer",
    "tanker",
]
LicenseClass = Literal["particular", "liviana", "pesada", "pesada_t", "motocicleta"]
DriverStatus = Literal["active", "suspended", "inactive"]
ComplianceStateLiteral = Literal["ok", "warning", "blocked"]

_PLATE = re.compile(r"^[A-Z0-9][A-Z0-9 -]{1,15}$")


def normalize_plate(value: str | None) -> str | None:
    """Blank means no plate; whether the vehicle may lack one depends on its type."""
    if value is None or not value.strip():
        return None
    normalized = re.sub(r"\s+", " ", value.strip().upper())
    if not _PLATE.match(normalized):
        raise ValueError("La placa solo admite letras, números, espacios y guiones.")
    return normalized


def normalize_vin(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().upper()
    if not re.fullmatch(r"[A-HJ-NPR-Z0-9]{11,17}", normalized):
        raise ValueError("El VIN debe tener entre 11 y 17 caracteres válidos.")
    return normalized


class ComplianceIssueOut(BaseModel):
    code: str
    severity: Literal["blocking", "warning"]
    message: str


class ComplianceOut(BaseModel):
    state: ComplianceStateLiteral
    issues: list[ComplianceIssueOut]


class VehicleDriverOut(BaseModel):
    assignment_id: uuid.UUID
    driver_id: uuid.UUID
    name: str
    initials: str
    photo_url: str | None = None
    license_class: LicenseClass
    status: DriverStatus
    since: datetime


class VehicleTripOut(BaseModel):
    id: uuid.UUID
    code: str
    status: str
    dispatched_at: datetime | None = None
    destination_branch: str


class VehicleTypeOut(BaseModel):
    code: str
    name: str
    plural: str
    license_classes: list[LicenseClass]
    base_image: BaseImage | None
    requires_plate: bool
    requires_capacity: bool
    meter_unit: MeterUnit
    fuel_applicable: bool
    can_tow: bool
    is_towable: bool
    is_system: bool
    is_active: bool


class VehicleTypeCatalogOut(VehicleTypeOut):
    id: uuid.UUID
    usage_count: int


class VehicleTypeIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    plural: str | None = Field(None, max_length=60)
    license_classes: list[LicenseClass] = Field(default_factory=list)
    base_image: BaseImage | None = None
    requires_plate: bool = True
    requires_capacity: bool = True
    meter_unit: MeterUnit = "km"
    fuel_applicable: bool = True
    can_tow: bool = False
    is_towable: bool = False

    @field_validator("name", "plural")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() or None if value else value

    @model_validator(mode="after")
    def _one_coupling_role(self) -> VehicleTypeIn:
        if self.can_tow and self.is_towable:
            raise ValueError("Un tipo no puede remolcar y ser remolcado a la vez.")
        return self


class VehicleTypeUpdate(VehicleTypeIn):
    is_active: bool = True


class VehicleCouplingOut(BaseModel):
    coupling_id: uuid.UUID
    role: Literal["tractor", "trailer"]
    vehicle_id: uuid.UUID
    code: str
    plate: str | None
    since: datetime


class VehicleCouplingIn(BaseModel):
    trailer_id: uuid.UUID


class FleetVehicleOut(BaseModel):
    id: uuid.UUID
    code: str
    plate: str | None
    vin: str | None
    kind: VehicleKind
    type: VehicleTypeOut
    coupling: VehicleCouplingOut | None
    brand: str
    model: str
    year: int
    color: str | None
    capacity_kg: Decimal | None
    fuel_type: FuelType
    odometer_km: Decimal
    status: VehicleStatus
    operational_status: OperationalStatus
    branch_id: uuid.UUID
    branch_name: str
    driver: VehicleDriverOut | None
    current_transfer: VehicleTripOut | None
    maintenance_in_progress: bool
    gps_linked: bool
    gps_device_unique_id: str | None
    inventory_vehicle_id: uuid.UUID | None
    notes: str | None
    compliance: ComplianceOut
    created_at: datetime
    updated_at: datetime


class FleetVehiclesPage(BaseModel):
    items: list[FleetVehicleOut]
    meta: dict[str, int]


class FleetSummaryOut(BaseModel):
    total: int
    available: int
    in_route: int
    maintenance: int
    out_of_service: int
    blocked: int
    with_warnings: int


class _VehicleFields(BaseModel):
    plate: str | None = Field(None, max_length=16)
    vin: str | None = Field(None, max_length=32)
    kind: VehicleKind
    brand: str = Field(min_length=1, max_length=60)
    model: str = Field(min_length=1, max_length=80)
    year: int = Field(ge=1950, le=2100)
    color: str | None = Field(None, max_length=40)
    capacity_kg: Decimal | None = Field(
        None, gt=0, le=Decimal("200000"), max_digits=10, decimal_places=2
    )
    fuel_type: FuelType = "diesel"
    notes: str | None = Field(None, max_length=2000)

    @field_validator("plate")
    @classmethod
    def _plate(cls, value: str | None) -> str | None:
        return normalize_plate(value)

    @field_validator("vin")
    @classmethod
    def _vin(cls, value: str | None) -> str | None:
        return normalize_vin(value)

    @field_validator("brand", "model", "color", "notes")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class FleetVehicleCreate(_VehicleFields):
    branch_id: uuid.UUID
    code: str = Field(min_length=1, max_length=32)
    odometer_km: Decimal = Field(Decimal("0"), ge=0, le=Decimal("9999999"), decimal_places=1)

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        normalized = re.sub(r"\s+", "-", value.strip().upper())
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,31}", normalized):
            raise ValueError("El código solo admite letras, números, guiones y guion bajo.")
        return normalized


class FleetVehicleUpdate(BaseModel):
    plate: str | None = Field(None, max_length=16)
    vin: str | None = Field(None, max_length=32)
    kind: VehicleKind | None = None
    brand: str | None = Field(None, min_length=1, max_length=60)
    model: str | None = Field(None, min_length=1, max_length=80)
    year: int | None = Field(None, ge=1950, le=2100)
    color: str | None = Field(None, max_length=40)
    capacity_kg: Decimal | None = Field(
        None, gt=0, le=Decimal("200000"), max_digits=10, decimal_places=2
    )
    fuel_type: FuelType | None = None
    notes: str | None = Field(None, max_length=2000)

    @field_validator("plate")
    @classmethod
    def _plate(cls, value: str | None) -> str | None:
        return normalize_plate(value)

    @field_validator("vin")
    @classmethod
    def _vin(cls, value: str | None) -> str | None:
        return normalize_vin(value)


class VehicleStatusIn(BaseModel):
    status: ManualVehicleStatus
    reason: str | None = Field(None, max_length=500)


class VehicleBranchIn(BaseModel):
    branch_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=500)


class VehiclePhotoIn(BaseModel):
    url: str = Field(min_length=10, max_length=2048)
    caption: str | None = Field(None, max_length=200)


class VehiclePhotoOut(BaseModel):
    id: uuid.UUID
    url: str
    caption: str | None
    position: int
    created_at: datetime


class OdometerReadingIn(BaseModel):
    reading_km: Decimal = Field(ge=0, le=Decimal("9999999"), decimal_places=1)
    read_at: AwareDatetime | None = None
    notes: str | None = Field(None, max_length=500)


class OdometerReadingOut(BaseModel):
    id: uuid.UUID
    reading_km: Decimal
    read_at: datetime
    source: str
    notes: str | None
    recorded_by_name: str | None


class MaintenancePlanIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    interval_km: int | None = Field(None, gt=0, le=1_000_000)
    interval_days: int | None = Field(None, gt=0, le=3650)
    last_service_km: Decimal | None = Field(None, ge=0, decimal_places=1)
    last_service_on: date | None = None


class MaintenancePlanOut(BaseModel):
    id: uuid.UUID
    name: str
    interval_km: int | None
    interval_days: int | None
    last_service_km: Decimal | None
    last_service_on: date | None
    due_km: Decimal | None
    due_on: date | None
    state: Literal["ok", "soon", "overdue", "unknown"]
    is_active: bool


class MaintenanceOrderIn(BaseModel):
    kind: Literal["preventive", "corrective"]
    title: str = Field(min_length=2, max_length=160)
    description: str | None = Field(None, max_length=4000)
    workshop: str | None = Field(None, max_length=160)
    scheduled_on: date | None = None
    plan_id: uuid.UUID | None = None


class MaintenanceCompleteIn(BaseModel):
    odometer_km: Decimal = Field(ge=0, le=Decimal("9999999"), decimal_places=1)
    cost: Decimal = Field(ge=0, le=Decimal("99999999"), decimal_places=2)
    workshop: str | None = Field(None, max_length=160)
    notes: str | None = Field(None, max_length=4000)


class MaintenanceCancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class MaintenanceOrderOut(BaseModel):
    id: uuid.UUID
    plan_id: uuid.UUID | None
    plan_name: str | None
    kind: str
    status: Literal["scheduled", "in_progress", "completed", "cancelled"]
    title: str
    description: str | None
    workshop: str | None
    scheduled_on: date | None
    started_at: datetime | None
    completed_at: datetime | None
    odometer_km: Decimal | None
    cost: Decimal | None
    cancel_reason: str | None
    created_at: datetime


class FuelLogIn(BaseModel):
    filled_at: AwareDatetime
    liters: Decimal = Field(gt=0, le=Decimal("5000"), decimal_places=3)
    total_amount: Decimal = Field(ge=0, le=Decimal("100000"), decimal_places=2)
    odometer_km: Decimal = Field(ge=0, le=Decimal("9999999"), decimal_places=1)
    full_tank: bool = True
    station: str | None = Field(None, max_length=160)
    driver_id: uuid.UUID | None = None


class FuelLogOut(BaseModel):
    id: uuid.UUID
    filled_at: datetime
    liters: Decimal
    total_amount: Decimal
    unit_price: Decimal
    odometer_km: Decimal
    full_tank: bool
    station: str | None
    driver_id: uuid.UUID | None
    driver_name: str | None
    km_per_liter: Decimal | None


class FuelStatsOut(BaseModel):
    liters: Decimal
    amount: Decimal
    average_km_per_liter: Decimal | None
    cost_per_km: Decimal | None


class FleetAlertOut(BaseModel):
    vehicle_id: uuid.UUID | None
    driver_id: uuid.UUID | None
    subject: str
    branch_name: str
    code: str
    severity: Literal["blocking", "warning"]
    message: str


# ------------------------------------------------------------------ drivers


class DriverEmployeeOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    initials: str
    document_id: str | None
    phone: str | None
    photo_url: str | None
    position: str | None
    status: str


class DriverVehicleOut(BaseModel):
    assignment_id: uuid.UUID
    vehicle_id: uuid.UUID
    code: str
    plate: str | None
    kind: VehicleKind
    kind_name: str
    base_image: BaseImage | None
    since: datetime


class DriverLicenseOut(BaseModel):
    license_class: LicenseClass
    number: str | None
    expires_on: date | None
    document_id: uuid.UUID | None


class DriverOut(BaseModel):
    id: uuid.UUID
    employee: DriverEmployeeOut
    branch_id: uuid.UUID
    branch_name: str
    license: DriverLicenseOut
    status: DriverStatus
    status_reason: str | None
    notes: str | None
    vehicle: DriverVehicleOut | None
    compliance: ComplianceOut
    created_at: datetime
    updated_at: datetime


class DriversPage(BaseModel):
    items: list[DriverOut]
    meta: dict[str, int]


class DriverCandidateOut(BaseModel):
    employee_id: uuid.UUID
    code: str
    name: str
    position: str | None
    photo_url: str | None


class DriverCreate(BaseModel):
    employee_id: uuid.UUID
    branch_id: uuid.UUID
    license_class: LicenseClass
    notes: str | None = Field(None, max_length=2000)


class DriverUpdate(BaseModel):
    license_class: LicenseClass | None = None
    notes: str | None = Field(None, max_length=2000)


class DriverStatusIn(BaseModel):
    status: DriverStatus
    reason: str | None = Field(None, max_length=500)


class DriverBranchIn(BaseModel):
    branch_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=500)


class AssignmentIn(BaseModel):
    driver_id: uuid.UUID
    override_reason: str | None = Field(None, min_length=5, max_length=500)


class AssignmentEndIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class AssignmentOut(BaseModel):
    id: uuid.UUID
    vehicle_id: uuid.UUID
    vehicle_code: str
    vehicle_plate: str
    driver_id: uuid.UUID
    driver_name: str
    starts_at: datetime
    ends_at: datetime | None
    end_reason: str | None


class DriverTripOut(BaseModel):
    transfer_id: uuid.UUID
    code: str
    status: str
    vehicle_code: str | None
    origin_branch: str
    destination_branch: str
    dispatched_at: datetime | None
    received_at: datetime | None
