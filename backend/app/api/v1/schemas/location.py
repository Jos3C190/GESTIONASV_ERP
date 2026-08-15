"""Pydantic v2 contracts for professional warehouse-location management."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.v1.schemas.common import PageMeta

LocationType = Literal[
    "standard",
    "bulk",
    "receiving",
    "reserve",
    "picking",
    "staging",
    "quality",
    "packing",
    "shipping",
    "returns",
    "virtual",
]
LocationLifecycleStatus = Literal[
    "draft", "active", "blocked", "blocked_in", "blocked_out", "maintenance", "retired"
]


class LocationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    area: str | None = Field(None, max_length=64)
    aisle: str = Field(min_length=1, max_length=64)
    rack: str = Field(min_length=1, max_length=64)
    level: str = Field(min_length=1, max_length=64)
    position: str = Field(min_length=1, max_length=64)
    capacity: int = Field(default=1, gt=0)
    notes: str | None = Field(None, max_length=4000)
    location_type: LocationType = "standard"
    lifecycle_status: LocationLifecycleStatus = "active"
    barcode: str | None = Field(None, max_length=120)
    verification_code: str | None = Field(None, max_length=120)
    pick_sequence: int | None = Field(None, ge=0)
    putaway_sequence: int | None = Field(None, ge=0)
    external_id: str | None = Field(None, max_length=120)
    scheme_version: int | None = Field(None, ge=1)
    expected_updated_at: datetime | None = None


class LocationCodePreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    area: str | None = Field(None, max_length=64)
    aisle: str = Field(min_length=1, max_length=64)
    rack: str = Field(min_length=1, max_length=64)
    level: str = Field(min_length=1, max_length=64)
    position: str = Field(min_length=1, max_length=64)
    scheme_version: int | None = Field(None, ge=1)
    exclude_location_id: uuid.UUID | None = None


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    warehouse_id: uuid.UUID
    code: str
    area: str | None
    aisle: str
    rack: str
    level: str
    position: str
    capacity: int
    notes: str | None
    location_type: str
    lifecycle_status: str
    barcode: str | None
    verification_code: str | None
    pick_sequence: int | None
    putaway_sequence: int | None
    external_id: str | None
    scheme_id: uuid.UUID | None
    scheme_version: int | None
    code_source: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LocationPage(BaseModel):
    items: list[LocationOut]
    meta: PageMeta


class LocationSummaryOut(BaseModel):
    total: int
    total_capacity: int
    active: int
    inactive: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    areas: dict[str, int]


class LocationCodePreviewOut(BaseModel):
    code: str
    normalized_components: dict[str, str]
    scheme_id: uuid.UUID
    scheme_version: int
    code_exists: bool
    coordinates_exist: bool


class LocationCodeSegmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    key: Literal["area", "aisle", "rack", "level", "position"]
    label: str = Field(min_length=1, max_length=64)
    prefix: str = Field(default="", max_length=8)
    width: int = Field(default=0, ge=0, le=32)
    pad_char: str = Field(default="0", min_length=1, max_length=1)
    required: bool = True


class LocationCodeSchemeIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=120)
    separator: str = Field(default="-", min_length=1, max_length=3)
    segments: list[LocationCodeSegmentIn] = Field(min_length=1, max_length=5)


class LocationCodeSegmentOut(LocationCodeSegmentIn):
    # Schemes are represented in the domain with immutable CodeSegment
    # dataclasses. Enable attribute parsing for the response DTO so routers
    # can serialize those domain values without involving ORM models.
    model_config = ConfigDict(from_attributes=True)


class LocationCodeSchemeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    warehouse_id: uuid.UUID
    name: str
    version: int
    separator: str
    segments: list[LocationCodeSegmentOut]
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None


class GeneratorAxis(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    key: Literal["area", "aisle", "rack", "level", "position"]
    values: list[str] | None = Field(None, min_length=1, max_length=10_000)
    start: str | None = Field(None, max_length=64)
    end: str | None = Field(None, max_length=64)
    step: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_source(self) -> GeneratorAxis:
        if bool(self.values) == bool(self.start and self.end):
            raise ValueError("Indique values o un rango start/end, pero no ambos.")
        return self


class BatchDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    area: str | None = Field(None, max_length=64)
    aisle: str | None = Field(None, max_length=64)
    rack: str | None = Field(None, max_length=64)
    level: str | None = Field(None, max_length=64)
    position: str | None = Field(None, max_length=64)
    capacity: int = Field(default=1, gt=0)
    notes: str | None = Field(None, max_length=4000)
    location_type: LocationType = "standard"
    lifecycle_status: LocationLifecycleStatus = "active"
    barcode: str | None = Field(None, max_length=120)
    verification_code: str | None = Field(None, max_length=120)
    pick_sequence: int | None = Field(None, ge=0)
    putaway_sequence: int | None = Field(None, ge=0)
    external_id: str | None = Field(None, max_length=120)


class GeneratorPreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    idempotency_key: str = Field(min_length=8, max_length=120)
    scheme_version: int | None = Field(None, ge=1)
    axes: list[GeneratorAxis] = Field(min_length=1, max_length=5)
    defaults: BatchDefaults = Field(default_factory=BatchDefaults)


class BatchRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    row_number: int
    operation: str
    code: str | None
    normalized_data: dict[str, Any]
    diff: dict[str, Any]
    errors: list[str]
    published_location_id: uuid.UUID | None


class LocationBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    warehouse_id: uuid.UUID
    kind: str
    status: str
    idempotency_key: str
    input_checksum: str
    scheme_id: uuid.UUID
    scheme_version: int
    total_rows: int
    create_count: int
    update_count: int
    unchanged_count: int
    conflict_count: int
    error_count: int
    summary: dict[str, Any]
    created_by: uuid.UUID
    published_by: uuid.UUID | None
    created_at: datetime
    published_at: datetime | None
    rows: list[BatchRowOut]
    required_permissions: list[str]
    rows_meta: PageMeta
