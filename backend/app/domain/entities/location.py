"""Warehouse-location domain objects and deterministic code formatting.

This module intentionally has no FastAPI, Pydantic or SQLAlchemy imports.  A
location code is a projection of a versioned scheme and normalized physical
coordinates; it is not a user-maintained identifier.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.core.exceptions import ValidationError
from app.domain.entities.warehouse_capacity import CapacityStatus, capacity_status_for

LOCATION_COMPONENT_KEYS = frozenset({"area", "aisle", "rack", "level", "position"})
LOCATION_LIFECYCLE_STATUSES = frozenset(
    {"draft", "active", "blocked", "blocked_in", "blocked_out", "maintenance", "retired"}
)
LOCATION_TYPES = frozenset(
    {
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
    }
)
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
MAX_SEGMENT_WIDTH = 32
MAX_SEGMENT_LABEL_LENGTH = 64
MAX_SEGMENT_PREFIX_LENGTH = 8
MAX_SEPARATOR_LENGTH = 3
MAX_LOCATION_CODE_LENGTH = 120


@dataclass(frozen=True, slots=True)
class CodeSegment:
    key: str
    label: str
    prefix: str = ""
    width: int = 0
    pad_char: str = "0"
    required: bool = True

    def __post_init__(self) -> None:
        if self.key not in LOCATION_COMPONENT_KEYS:
            raise ValidationError(
                f"El segmento '{self.key}' no corresponde a una coordenada soportada.",
                code="location_scheme_segment_invalid",
            )
        if not 0 <= self.width <= MAX_SEGMENT_WIDTH:
            raise ValidationError(
                "El ancho de cada segmento debe estar entre 0 y 32.",
                code="location_scheme_width_invalid",
            )
        normalized_label = unicodedata.normalize("NFKC", self.label).strip()
        if (
            not 1 <= len(normalized_label) <= MAX_SEGMENT_LABEL_LENGTH
            or _CONTROL_CHARACTERS.search(normalized_label)
        ):
            raise ValidationError(
                "La etiqueta del segmento no es válida.",
                code="location_scheme_label_invalid",
            )
        normalized_prefix = unicodedata.normalize("NFKC", self.prefix).strip().upper()
        if len(normalized_prefix) > MAX_SEGMENT_PREFIX_LENGTH or _CONTROL_CHARACTERS.search(
            normalized_prefix
        ):
            raise ValidationError(
                "El prefijo del segmento no es válido.",
                code="location_scheme_prefix_invalid",
            )
        normalized_pad = unicodedata.normalize("NFKC", self.pad_char)
        if len(normalized_pad) != 1 or _CONTROL_CHARACTERS.search(normalized_pad):
            raise ValidationError(
                "El carácter de relleno del segmento no es válido.",
                code="location_scheme_padding_invalid",
            )


@dataclass(frozen=True, slots=True)
class LocationCodeScheme:
    id: uuid.UUID
    warehouse_id: uuid.UUID
    name: str
    version: int
    separator: str
    segments: tuple[CodeSegment, ...]
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValidationError(
                "La versión del esquema debe ser positiva.",
                code="location_scheme_version_invalid",
            )
        if not self.segments:
            raise ValidationError(
                "El esquema debe incluir al menos un segmento.",
                code="location_scheme_empty",
            )
        keys = [segment.key for segment in self.segments]
        if len(keys) != len(set(keys)):
            raise ValidationError(
                "Un esquema no puede repetir coordenadas.",
                code="location_scheme_segment_repeated",
            )
        normalized_separator = unicodedata.normalize("NFKC", self.separator)
        if not 1 <= len(normalized_separator) <= MAX_SEPARATOR_LENGTH or _CONTROL_CHARACTERS.search(
            normalized_separator
        ):
            raise ValidationError(
                "El separador del esquema no es válido.",
                code="location_scheme_separator_invalid",
            )
        if any(
            normalized_separator
            in unicodedata.normalize("NFKC", segment.prefix).strip().upper()
            for segment in self.segments
        ):
            raise ValidationError(
                "Un prefijo no puede contener el separador del esquema.",
                code="location_scheme_prefix_separator_forbidden",
            )


@dataclass(frozen=True, slots=True)
class CodeProjection:
    code: str
    normalized_components: dict[str, str]
    scheme_id: uuid.UUID
    scheme_version: int


@dataclass(frozen=True, slots=True)
class LocationRecord:
    id: uuid.UUID
    warehouse_id: uuid.UUID
    code: str
    area: str | None
    aisle: str
    rack: str
    level: str
    position: str
    capacity_group_id: uuid.UUID | None
    certified_max_weight_kg: Decimal | None
    operational_max_weight_kg: Decimal | None
    certified_usable_volume_m3: Decimal | None
    operational_usable_volume_m3: Decimal | None
    capacity_profile: str
    capacity_enforcement_mode: str
    storage_eligible: bool
    usable_length_m: Decimal | None
    usable_width_m: Decimal | None
    usable_height_m: Decimal | None
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

    @property
    def capacity_status(self) -> CapacityStatus:
        return capacity_status_for(self)


@dataclass(frozen=True, slots=True)
class BatchRowRecord:
    id: uuid.UUID
    row_number: int
    operation: str
    code: str | None
    normalized_data: dict[str, Any]
    diff: dict[str, Any]
    errors: tuple[str, ...] = ()
    published_location_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class LocationBatchRecord:
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
    rows: tuple[BatchRowRecord, ...] = field(default_factory=tuple)
    required_permissions: tuple[str, ...] = field(default_factory=tuple)
    rows_meta: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WarehouseLocationScope:
    warehouse_id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID
    warehouse_active: bool
    operational_status: str


def normalize_location_component(value: object, segment: CodeSegment) -> str:
    """Normalize one coordinate according to the stable warehouse scheme.

    NFKC/trim/upper are deliberately fixed product rules.  Padding is a
    presentation rule from the versioned scheme and never truncates data.
    """

    normalized = unicodedata.normalize("NFKC", "" if value is None else str(value))
    normalized = normalized.strip().upper()
    if _CONTROL_CHARACTERS.search(normalized):
        raise ValidationError(
            f"{segment.label} contiene caracteres de control.",
            code="location_component_control_character",
        )
    if not normalized:
        if segment.required:
            raise ValidationError(
                f"{segment.label} es obligatorio.",
                code="location_component_required",
            )
        return ""
    prefix = unicodedata.normalize("NFKC", segment.prefix).strip().upper()
    if prefix and normalized.startswith(prefix):
        suffix = normalized[len(prefix) :]
        # Accept scanner/import values already rendered by the same scheme.
        # Only strip a prefix when the remainder is numeric; arbitrary text
        # such as aisle "AREA" must not silently become "REA".
        if suffix.isdigit():
            normalized = suffix
        elif not suffix:
            return prefix
    if segment.width and len(normalized) < segment.width:
        normalized = normalized.rjust(segment.width, segment.pad_char)
    return normalized


def project_location_code(
    scheme: LocationCodeScheme, components: Mapping[str, object]
) -> CodeProjection:
    normalized: dict[str, str] = {}
    rendered: list[str] = []
    for segment in scheme.segments:
        value = normalize_location_component(components.get(segment.key), segment)
        normalized[segment.key] = value
        if not value:
            continue
        if scheme.separator in value:
            raise ValidationError(
                f"{segment.label} no puede contener el separador del esquema.",
                code="location_component_separator_forbidden",
            )
        prefix = unicodedata.normalize("NFKC", segment.prefix).strip().upper()
        rendered.append(value if prefix and value == prefix else f"{prefix}{value}")
    code = scheme.separator.join(rendered)
    if not code:
        raise ValidationError(
            "No fue posible generar un código de ubicación.",
            code="location_code_empty",
        )
    if len(code) > MAX_LOCATION_CODE_LENGTH:
        raise ValidationError(
            "El código generado excede los 120 caracteres permitidos.",
            code="location_code_too_long",
        )
    return CodeProjection(
        code=code,
        normalized_components=normalized,
        scheme_id=scheme.id,
        scheme_version=scheme.version,
    )


def default_location_segments() -> tuple[CodeSegment, ...]:
    return (
        CodeSegment("aisle", "Pasillo", "A", 2, "0", True),
        CodeSegment("rack", "Rack", "R", 2, "0", True),
        CodeSegment("level", "Nivel", "N", 2, "0", True),
        CodeSegment("position", "Posición", "P", 2, "0", True),
    )
