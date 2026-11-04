from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.fleet import FleetVehicleOut
from app.api.v1.schemas.license_capture import CaptureSideOut, LicenseIssueOut


class CirculationFieldsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=160)

    plate: str | None = None
    expires: str | None = None
    issued: str | None = None
    year: str | None = None
    brand: str | None = None
    model: str | None = None
    color: str | None = None
    chassis: str | None = None
    engine: str | None = None
    vin: str | None = None


class CirculationCaptureOut(BaseModel):
    id: uuid.UUID
    status: str
    failure_code: str | None
    extraction_available: bool
    front: CaptureSideOut
    back: CaptureSideOut
    values: CirculationFieldsPayload
    issues: list[LicenseIssueOut]
    fills: list[str]


class CirculationCheckOut(BaseModel):
    issues: list[LicenseIssueOut]
    fills: list[str]


class CirculationConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: CirculationFieldsPayload
    acknowledged_warnings: list[str] = Field(default_factory=list, max_length=20)


class CirculationConfirmOut(BaseModel):
    vehicle: FleetVehicleOut
    filled_fields: list[str]
    skipped_fields: list[str]
