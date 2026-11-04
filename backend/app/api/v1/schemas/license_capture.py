from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CaptureSideName = Literal["front", "back"]
CAPTURE_IMAGE_TYPES = Literal["image/jpeg", "image/png", "image/webp"]


class LicenseCaptureCapabilitiesOut(BaseModel):
    enabled: bool
    extraction_available: bool


class CaptureUploadIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_type: CAPTURE_IMAGE_TYPES
    size_bytes: int = Field(gt=0)
    checksum_sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")


class LicenseFieldsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=160)

    license_class: str | None = None
    expires: str | None = None
    number: str | None = None
    surnames: str | None = None
    given_names: str | None = None
    dui: str | None = None
    issued: str | None = None
    birth: str | None = None
    control_number: str | None = None


class LicenseIssueOut(BaseModel):
    code: str
    severity: Literal["error", "mismatch", "warning"]
    field: str
    message: str


class CaptureSideOut(BaseModel):
    document_id: uuid.UUID | None
    status: str | None
    extracted: bool


class LicenseCaptureOut(BaseModel):
    id: uuid.UUID
    status: str
    failure_code: str | None
    extraction_available: bool
    front: CaptureSideOut
    back: CaptureSideOut
    values: LicenseFieldsPayload
    issues: list[LicenseIssueOut]


class LicenseConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: LicenseFieldsPayload
    acknowledged_warnings: list[str] = Field(default_factory=list, max_length=20)
    override_reason: str | None = Field(default=None, max_length=500)
