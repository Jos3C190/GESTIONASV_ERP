"""Input-boundary tests for staged CSV/XLSX warehouse-location imports."""

from __future__ import annotations

import io
import uuid
import zipfile
from decimal import Decimal
from types import SimpleNamespace

import pytest
from app.application.locations import use_cases as location_module
from app.application.locations.use_cases import LocationUseCases
from app.core.exceptions import ValidationError
from app.domain.entities.location import LocationCodeScheme, default_location_segments

from tests.unit.test_location_generation import RecordingLocationRepository

pytestmark = pytest.mark.unit


@pytest.fixture
def import_service() -> tuple[LocationUseCases, RecordingLocationRepository, LocationCodeScheme]:
    scheme = LocationCodeScheme(
        id=uuid.uuid4(),
        warehouse_id=uuid.uuid4(),
        name="Importación",
        version=1,
        separator="-",
        segments=default_location_segments(),
        is_active=True,
    )
    repository = RecordingLocationRepository(scheme)
    return LocationUseCases(repository), repository, scheme


@pytest.mark.asyncio
async def test_csv_spanish_aliases_are_normalized_and_external_id_is_preserved(
    import_service: tuple[LocationUseCases, RecordingLocationRepository, LocationCodeScheme],
) -> None:
    service, repository, scheme = import_service
    content = (
        "Zona;Pasillo;Estante;Nivel;Posición;Peso máximo certificado kg;"
        "Peso máximo operativo kg;Volumen útil certificado m3;"
        "Volumen útil operativo m3;Modo control capacidad;ID externo;Notas\n"
        '  picking ;1;2;3;4;1000;900;12.5;10;enforce;LEGACY-004;'
        '=HYPERLINK("https://invalid.example")\n'
    ).encode()

    job = await service.preview_import(
        scheme.warehouse_id,
        filename="ubicaciones.CSV",
        content=content,
        idempotency_key="spanish-aliases",
        actor_id=uuid.uuid4(),
    )

    row = repository.preview_calls[-1]["source_rows"][0]
    assert job.error_count == 0
    assert row["code"] == "A01-R02-N03-P04"
    assert row["area"] == "PICKING"
    assert row["certified_max_weight_kg"] == Decimal("1000")
    assert row["operational_max_weight_kg"] == Decimal("900")
    assert row["certified_usable_volume_m3"] == Decimal("12.5")
    assert row["operational_usable_volume_m3"] == Decimal("10")
    assert row["capacity_enforcement_mode"] == "enforce"
    assert row["external_id"] == "LEGACY-004"
    # Formula-looking text is inert server-side. Any future CSV/XLSX export
    # must still neutralise it before a spreadsheet application opens it.
    assert row["notes"].startswith("=HYPERLINK")


@pytest.mark.asyncio
async def test_import_rejects_empty_payload_before_parsing(
    import_service: tuple[LocationUseCases, RecordingLocationRepository, LocationCodeScheme],
) -> None:
    service, repository, scheme = import_service

    with pytest.raises(ValidationError) as error:
        await service.preview_import(
            scheme.warehouse_id,
            filename="locations.csv",
            content=b"",
            idempotency_key="invalid-size",
            actor_id=uuid.uuid4(),
        )

    assert error.value.code == "location_import_size_invalid"
    assert repository.preview_calls == []


@pytest.mark.asyncio
async def test_import_rejects_payload_over_20_mb_before_parsing(
    import_service: tuple[LocationUseCases, RecordingLocationRepository, LocationCodeScheme],
) -> None:
    service, repository, scheme = import_service

    with pytest.raises(ValidationError) as error:
        await service.preview_import(
            scheme.warehouse_id,
            filename="locations.csv",
            content=b"x" * (location_module.MAX_IMPORT_BYTES + 1),
            idempotency_key="invalid-size",
            actor_id=uuid.uuid4(),
        )

    assert error.value.code == "location_import_size_invalid"
    assert repository.preview_calls == []


@pytest.mark.asyncio
async def test_import_rejects_unsupported_extension_before_repository_access(
    import_service: tuple[LocationUseCases, RecordingLocationRepository, LocationCodeScheme],
) -> None:
    service, repository, scheme = import_service

    with pytest.raises(ValidationError) as error:
        await service.preview_import(
            scheme.warehouse_id,
            filename="locations.xlsm",
            content=b"not-a-workbook",
            idempotency_key="bad-extension",
            actor_id=uuid.uuid4(),
        )

    assert error.value.code == "location_import_type_invalid"
    assert repository.preview_calls == []


def test_csv_rejects_non_utf8_input() -> None:
    with pytest.raises(ValidationError) as error:
        location_module._parse_csv(b"pasillo,rack,nivel,posicion\n\xff,1,1,1")

    assert error.value.code == "location_import_encoding_invalid"


def test_csv_rejects_files_without_any_recognized_header() -> None:
    with pytest.raises(ValidationError) as error:
        location_module._parse_csv(b"foo,bar\n1,2\n")

    assert error.value.code == "location_import_headers_invalid"


def test_csv_rejects_two_headers_that_map_to_the_same_coordinate() -> None:
    with pytest.raises(ValidationError) as error:
        location_module._parse_csv(b"aisle,pasillo,rack,level,position\n1,2,1,1,1\n")

    assert error.value.code == "location_import_header_repeated"


def test_oversized_csv_field_is_reported_as_validation_error_not_csv_internal_error() -> None:
    content = b"aisle,rack,level,position,notes\n1,1,1,1," + (b"x" * 1_048_577)

    with pytest.raises(ValidationError) as error:
        location_module._parse_csv(content)

    assert error.value.code == "location_import_field_too_large"


def test_xlsx_preflight_rejects_path_traversal_entry() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../outside.xml", b"x")

    with pytest.raises(ValidationError) as error:
        location_module._validate_xlsx_archive(buffer.getvalue())

    assert error.value.code == "location_import_xlsx_invalid"


def test_xlsx_preflight_rejects_zip_bomb_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = SimpleNamespace(
        filename="xl/worksheets/sheet1.xml",
        flag_bits=0,
        file_size=location_module.MAX_XLSX_UNCOMPRESSED_BYTES + 1,
        compress_size=1,
    )

    class FakeArchive:
        def __enter__(self) -> FakeArchive:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def infolist(self) -> list[SimpleNamespace]:
            return [entry]

    monkeypatch.setattr(location_module.zipfile, "ZipFile", lambda _: FakeArchive())

    with pytest.raises(ValidationError) as error:
        location_module._validate_xlsx_archive(b"PK")

    assert error.value.code == "location_import_xlsx_too_large"


@pytest.mark.asyncio
async def test_import_row_limit_is_enforced_before_repository_write(
    import_service: tuple[LocationUseCases, RecordingLocationRepository, LocationCodeScheme],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, repository, scheme = import_service
    monkeypatch.setattr(location_module, "MAX_BATCH_ROWS", 3)
    content = b"aisle,rack,level,position\n1,1,1,1\n2,1,1,1\n3,1,1,1\n4,1,1,1\n"

    with pytest.raises(ValidationError) as error:
        await service.preview_import(
            scheme.warehouse_id,
            filename="locations.csv",
            content=content,
            idempotency_key="too-many-rows",
            actor_id=uuid.uuid4(),
        )

    assert error.value.code == "location_batch_too_large"
    assert repository.preview_calls == []
