"""Pure domain/application tests for deterministic warehouse-location codes."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from app.api.v1.schemas.location import LocationCodeSchemeOut
from app.application.locations import use_cases as location_module
from app.application.locations.use_cases import LocationUseCases
from app.core.exceptions import ConflictError, ValidationError
from app.domain.entities.location import (
    CodeProjection,
    CodeSegment,
    LocationCodeScheme,
    default_location_segments,
    normalize_location_component,
    project_location_code,
)
from app.infrastructure.repositories.location_repository import (
    _effective_code_source,
    _effective_update_projection,
)

pytestmark = pytest.mark.unit


class RecordingLocationRepository:
    """Small in-memory port double; it intentionally performs no I/O."""

    def __init__(self, scheme: LocationCodeScheme) -> None:
        self.scheme = scheme
        self.preview_calls: list[dict[str, Any]] = []
        self._idempotent_jobs: dict[tuple[uuid.UUID, str], Any] = {}
        self.jobs: dict[uuid.UUID, Any] = {}

    async def get_scheme(
        self, warehouse_id: uuid.UUID, version: int | None = None
    ) -> LocationCodeScheme:
        assert warehouse_id == self.scheme.warehouse_id
        assert version is None or version == self.scheme.version
        return self.scheme

    async def create_batch_preview(
        self,
        warehouse_id: uuid.UUID,
        *,
        kind: str,
        idempotency_key: str,
        input_checksum: str,
        scheme: LocationCodeScheme,
        source_rows: list[dict[str, Any]],
        actor_id: uuid.UUID,
    ) -> Any:
        call = {
            "warehouse_id": warehouse_id,
            "kind": kind,
            "idempotency_key": idempotency_key,
            "input_checksum": input_checksum,
            "scheme": scheme,
            "source_rows": [dict(row) for row in source_rows],
            "actor_id": actor_id,
        }
        self.preview_calls.append(call)
        key = (warehouse_id, idempotency_key)
        previous = self._idempotent_jobs.get(key)
        if previous is not None:
            if previous.input_checksum != input_checksum:
                raise ConflictError(
                    "La clave de idempotencia ya se utilizó con otro contenido.",
                    code="location_idempotency_conflict",
                )
            return previous

        error_count = sum(1 for row in source_rows if row.get("_errors"))
        job = SimpleNamespace(
            id=uuid.uuid5(uuid.NAMESPACE_URL, f"{warehouse_id}:{idempotency_key}"),
            warehouse_id=warehouse_id,
            kind=kind,
            status="preview",
            idempotency_key=idempotency_key,
            input_checksum=input_checksum,
            total_rows=len(source_rows),
            create_count=len(source_rows) - error_count,
            update_count=0,
            unchanged_count=0,
            conflict_count=0,
            error_count=error_count,
            rows=tuple(source_rows),
        )
        self._idempotent_jobs[key] = job
        self.jobs[job.id] = job
        return job

    async def get_batch(self, job_id: uuid.UUID, **_: Any) -> Any:
        return self.jobs[job_id]

    async def publish_batch(self, job_id: uuid.UUID, *, actor_id: uuid.UUID) -> Any:
        job = self.jobs[job_id]
        job.status = "published"
        job.published_by = actor_id
        return job


@pytest.fixture
def scheme() -> LocationCodeScheme:
    return LocationCodeScheme(
        id=uuid.uuid4(),
        warehouse_id=uuid.uuid4(),
        name="Esquema operativo",
        version=3,
        separator="-",
        segments=default_location_segments(),
        is_active=True,
    )


def test_component_normalization_is_nfkc_trimmed_uppercase_and_padded() -> None:
    segment = CodeSegment("aisle", "Pasillo", prefix="A", width=3)

    assert normalize_location_component("  １a  ", segment) == "01A"
    assert normalize_location_component("1234", segment) == "1234"


def test_rendered_prefix_inputs_are_equivalent_to_numeric_components() -> None:
    segment = CodeSegment("rack", "Rack", prefix="R", width=2)

    assert normalize_location_component("1", segment) == "01"
    assert normalize_location_component("R01", segment) == "01"


def test_component_normalization_rejects_control_characters() -> None:
    segment = CodeSegment("rack", "Rack")

    with pytest.raises(ValidationError) as error:
        normalize_location_component("R\n01", segment)

    assert error.value.code == "location_component_control_character"


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"label": "Rack\nmalicioso"}, "location_scheme_label_invalid"),
        ({"label": "Rack", "prefix": "R\x00"}, "location_scheme_prefix_invalid"),
    ],
)
def test_scheme_segment_metadata_rejects_control_characters(
    kwargs: dict[str, str], code: str
) -> None:
    with pytest.raises(ValidationError) as error:
        CodeSegment("rack", **kwargs)

    assert error.value.code == code


def test_scheme_rejects_separator_inside_prefix() -> None:
    with pytest.raises(ValidationError) as error:
        LocationCodeScheme(
            id=uuid.uuid4(),
            warehouse_id=uuid.uuid4(),
            name="Ambiguo",
            version=1,
            separator="-",
            segments=(CodeSegment("rack", "Rack", prefix="R-"),),
            is_active=True,
        )

    assert error.value.code == "location_scheme_prefix_separator_forbidden"


def test_projection_is_deterministic_and_independent_of_mapping_order(
    scheme: LocationCodeScheme,
) -> None:
    first = project_location_code(
        scheme,
        {"aisle": "1", "rack": "2", "level": "3", "position": "4"},
    )
    second = project_location_code(
        scheme,
        {"position": "4", "level": "3", "rack": "2", "aisle": "1"},
    )

    assert first == second
    assert first.code == "A01-R02-N03-P04"
    assert first.scheme_version == 3


def test_scheme_response_serializes_domain_segments(scheme: LocationCodeScheme) -> None:
    response = LocationCodeSchemeOut.model_validate(scheme)

    assert response.id == scheme.id
    assert [segment.key for segment in response.segments] == [
        "aisle",
        "rack",
        "level",
        "position",
    ]
    assert response.segments[0].prefix == "A"


def test_projection_forbids_ambiguous_separator_inside_coordinates(
    scheme: LocationCodeScheme,
) -> None:
    with pytest.raises(ValidationError) as error:
        project_location_code(
            scheme,
            {"aisle": "1-2", "rack": "2", "level": "3", "position": "4"},
        )

    assert error.value.code == "location_component_separator_forbidden"


def test_non_physical_update_preserves_exact_legacy_code_and_provenance() -> None:
    legacy_scheme_id = uuid.uuid4()
    generated_scheme_id = uuid.uuid4()
    legacy = SimpleNamespace(
        code="REC-01",
        area=None,
        aisle="REC",
        rack="R01",
        level="N01",
        position="P01",
        code_scheme_id=legacy_scheme_id,
        scheme_version=1,
        code_source="legacy",
    )
    generated = CodeProjection(
        code="AREC-RR01-NN01-PP01",
        normalized_components={},
        scheme_id=generated_scheme_id,
        scheme_version=2,
    )

    effective = _effective_update_projection(
        legacy,
        {
            "area": None,
            "aisle": "REC",
            "rack": "R01",
            "level": "N01",
            "position": "P01",
            "capacity": 25,
            "notes": "Solo cambia información operativa",
        },
        generated,
    )

    assert effective.code == "REC-01"
    assert effective.scheme_id == legacy_scheme_id
    assert effective.scheme_version == 1
    assert _effective_code_source(legacy, effective) == "legacy"


@pytest.mark.parametrize(
    ("axis", "expected"),
    [
        ({"start": "A01", "end": "A05", "step": 2}, ["A01", "A03", "A05"]),
        ({"start": "1", "end": "3"}, ["1", "2", "3"]),
        ({"start": "A", "end": "C"}, ["A", "B", "C"]),
        ({"values": [" a ", "ｂ"]}, ["A", "B"]),
    ],
)
def test_axis_expansion_preserves_range_padding_and_order(
    axis: dict[str, Any], expected: list[str]
) -> None:
    assert location_module._expand_axis(axis) == expected


def test_axis_step_is_reported_as_domain_validation_not_an_internal_error() -> None:
    with pytest.raises(ValidationError) as error:
        location_module._expand_axis({"start": "1", "end": "9", "step": "abc"})

    assert error.value.code == "location_axis_invalid"


def test_axis_rejects_huge_range_before_materializing_it() -> None:
    with pytest.raises(ValidationError) as error:
        location_module._expand_axis({"start": "1", "end": "999999999"})

    assert error.value.code == "location_batch_too_large"


@pytest.mark.asyncio
async def test_generator_cartesian_product_has_stable_order_and_cardinality(
    scheme: LocationCodeScheme,
) -> None:
    repository = RecordingLocationRepository(scheme)
    use_cases = LocationUseCases(repository)

    job = await use_cases.preview_generator(
        scheme.warehouse_id,
        axes=(
            {"key": "aisle", "values": ["1", "2"]},
            {"key": "rack", "start": "1", "end": "3"},
        ),
        defaults={"level": "1", "position": "1", "capacity": 5},
        idempotency_key="generator-order",
        actor_id=uuid.uuid4(),
    )

    assert job.total_rows == 6
    assert [row["code"] for row in repository.preview_calls[-1]["source_rows"]] == [
        "A01-R01-N01-P01",
        "A01-R02-N01-P01",
        "A01-R03-N01-P01",
        "A02-R01-N01-P01",
        "A02-R02-N01-P01",
        "A02-R03-N01-P01",
    ]


@pytest.mark.asyncio
async def test_generator_rejects_cardinality_above_configured_limit(
    scheme: LocationCodeScheme,
) -> None:
    repository = RecordingLocationRepository(scheme)

    with pytest.raises(ValidationError) as error:
        await LocationUseCases(repository).preview_generator(
            scheme.warehouse_id,
            axes=(
                {"key": "aisle", "start": "1", "end": "224"},
                {"key": "rack", "start": "1", "end": "224"},
            ),
            defaults={"level": "1", "position": "1"},
            idempotency_key="too-large",
            actor_id=uuid.uuid4(),
        )

    assert location_module.MAX_BATCH_ROWS < 224 * 224
    assert error.value.code == "location_batch_too_large"
    assert repository.preview_calls == []


@pytest.mark.asyncio
async def test_generator_checksum_and_idempotency_are_deterministic(
    scheme: LocationCodeScheme,
) -> None:
    repository = RecordingLocationRepository(scheme)
    use_cases = LocationUseCases(repository)
    actor_id = uuid.uuid4()

    first = await use_cases.preview_generator(
        scheme.warehouse_id,
        axes=({"key": "aisle", "start": "1", "end": "2", "step": 1},),
        defaults={"rack": "1", "level": "1", "position": "1", "capacity": 2},
        idempotency_key="same-request",
        actor_id=actor_id,
    )
    second = await use_cases.preview_generator(
        scheme.warehouse_id,
        axes=({"end": "2", "step": 1, "start": "1", "key": "aisle"},),
        defaults={"position": "1", "capacity": 2, "level": "1", "rack": "1"},
        idempotency_key="same-request",
        actor_id=actor_id,
    )

    assert first.id == second.id
    assert first.input_checksum == second.input_checksum

    with pytest.raises(ConflictError) as error:
        await use_cases.preview_generator(
            scheme.warehouse_id,
            axes=({"key": "aisle", "start": "1", "end": "3", "step": 1},),
            defaults={"rack": "1", "level": "1", "position": "1", "capacity": 2},
            idempotency_key="same-request",
            actor_id=actor_id,
        )
    assert error.value.code == "location_idempotency_conflict"


@pytest.mark.parametrize("capacity", [0, -1, "x", None])
def test_capacity_must_be_a_positive_integer(capacity: object) -> None:
    with pytest.raises(ValidationError) as error:
        location_module._normalize_operational_values({"capacity": capacity})

    assert error.value.code == "location_capacity_invalid"


@pytest.mark.parametrize("capacity", [1.5, True])
def test_capacity_rejects_lossy_or_boolean_values(capacity: object) -> None:
    with pytest.raises(ValidationError) as error:
        location_module._normalize_operational_values({"capacity": capacity})

    assert error.value.code == "location_capacity_invalid"


@pytest.mark.parametrize("sequence", [1.5, True])
def test_sequence_rejects_lossy_or_boolean_values(sequence: object) -> None:
    with pytest.raises(ValidationError) as error:
        location_module._normalize_operational_values(
            {"capacity": 1, "pick_sequence": sequence}
        )

    assert error.value.code == "location_sequence_invalid"


@pytest.mark.asyncio
async def test_publish_is_blocked_when_preview_contains_errors_or_conflicts(
    scheme: LocationCodeScheme,
) -> None:
    repository = RecordingLocationRepository(scheme)
    job_id = uuid.uuid4()
    repository.jobs[job_id] = SimpleNamespace(error_count=1, conflict_count=0)

    with pytest.raises(ConflictError) as error:
        await LocationUseCases(repository).publish_batch(job_id, actor_id=uuid.uuid4())

    assert error.value.code == "location_batch_not_publishable"
