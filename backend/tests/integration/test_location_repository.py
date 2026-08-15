"""PostgreSQL guarantees for location batches, aliases, capacity and lifecycle.

These tests intentionally exercise real unique indexes and row locks. They are
not part of the database-free unit run and must only run against ``erp_db_test``.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from typing import Any

import pytest
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.entities.location import (
    CodeProjection,
    default_location_segments,
)
from app.domain.entities.location import (
    LocationCodeScheme as DomainLocationCodeScheme,
)
from app.infrastructure.db.session import async_session_factory, dispose_engine
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.location import (
    LocationBatchJob,
    LocationBatchRow,
    LocationCodeAlias,
    LocationCodeScheme,
)
from app.infrastructure.models.organization import (
    Branch,
    Company,
    District,
    GeographicDepartment,
    Location,
    Municipality,
    Warehouse,
    WarehouseCategory,
)
from app.infrastructure.models.user import User
from app.infrastructure.repositories.lifecycle_repository import (
    SqlAlchemyLifecycleRepository,
)
from app.infrastructure.repositories.location_repository import (
    SqlAlchemyLocationRepository,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class LocationContext:
    actor_id: uuid.UUID
    company_id: uuid.UUID
    warehouse_id: uuid.UUID
    scheme: DomainLocationCodeScheme


@pytest.fixture
async def location_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            if transaction.is_active:
                await transaction.rollback()
    await dispose_engine()


def _suffix() -> str:
    return uuid.uuid4().hex[:12]


async def _add_context(
    session: AsyncSession,
    *,
    warehouse_capacity: int = 100,
    operational_status: str = "active",
) -> LocationContext:
    suffix = _suffix()
    department = GeographicDepartment(id=uuid.uuid4(), name=f"Location test {suffix}")
    session.add(department)
    await session.flush()
    municipality = Municipality(
        id=uuid.uuid4(), department_id=department.id, name=f"Municipality {suffix}"
    )
    session.add(municipality)
    await session.flush()
    district = District(id=uuid.uuid4(), municipality_id=municipality.id, name=f"District {suffix}")
    session.add(district)
    await session.flush()
    company = Company(
        id=uuid.uuid4(),
        name=f"Location Test {suffix}, S.A. de C.V.",
        commercial_name=f"Location Test {suffix}",
        nit=f"LOC-{suffix}-NIT",
        nrc=f"LOC-{suffix}-NRC",
        address="San Salvador, El Salvador",
        department_id=department.id,
        municipality_id=municipality.id,
        district_id=district.id,
        is_active=True,
    )
    session.add(company)
    await session.flush()
    # Use a self-contained actor rather than relying on the canonical seed.
    # The database enforces an employee profile for every visible user, so the
    # actor and its employee are created together after the test company.
    actor = User(
        username=f"location-test-{suffix}",
        email=f"location-test-{suffix}@example.test",
        password_hash="integration-test-only",
        is_active=True,
        is_superuser=True,
    )
    session.add(actor)
    await session.flush()
    session.add(
        Employee(
            company_id=company.id,
            user_id=actor.id,
            employee_code=f"LOC-{suffix[:12].upper()}",
            first_name="Location",
            last_name="Test",
            status="activo",
        )
    )
    await session.flush()
    branch = Branch(
        id=uuid.uuid4(),
        company_id=company.id,
        name=f"Branch {suffix}",
        code=f"B{suffix[:8]}",
        address="San Salvador, El Salvador",
        department_id=department.id,
        municipality_id=municipality.id,
        district_id=district.id,
        operational_status="active",
        is_active=True,
    )
    category = WarehouseCategory(
        id=uuid.uuid4(),
        company_id=company.id,
        name=f"Category {suffix}",
        is_active=True,
    )
    session.add_all([branch, category])
    await session.flush()
    warehouse = Warehouse(
        id=uuid.uuid4(),
        branch_id=branch.id,
        warehouse_category_id=category.id,
        name=f"Warehouse {suffix}",
        code=f"W{suffix[:8]}",
        warehouse_type="general",
        operational_status=operational_status,
        capacity=warehouse_capacity,
        is_active=True,
    )
    session.add(warehouse)
    await session.flush()
    scheme_id = uuid.uuid4()
    segments = default_location_segments()
    scheme_model = LocationCodeScheme(
        id=scheme_id,
        warehouse_id=warehouse.id,
        name="Default test scheme",
        version=1,
        separator="-",
        segments=[asdict(segment) for segment in segments],
        is_active=True,
        created_by=actor.id,
    )
    session.add(scheme_model)
    await session.flush()
    return LocationContext(
        actor_id=actor.id,
        company_id=company.id,
        warehouse_id=warehouse.id,
        scheme=DomainLocationCodeScheme(
            id=scheme_id,
            warehouse_id=warehouse.id,
            name="Default test scheme",
            version=1,
            separator="-",
            segments=segments,
            is_active=True,
        ),
    )


def _projection(
    context: LocationContext,
    *,
    code: str,
    aisle: str,
    rack: str = "01",
    level: str = "01",
    position: str = "01",
) -> CodeProjection:
    return CodeProjection(
        code=code,
        normalized_components={
            "area": "",
            "aisle": aisle,
            "rack": rack,
            "level": level,
            "position": position,
        },
        scheme_id=context.scheme.id,
        scheme_version=context.scheme.version,
    )


def _values(
    projection: CodeProjection,
    *,
    capacity: int,
    external_id: str | None = None,
    code_source: str = "generated",
) -> dict[str, Any]:
    components = projection.normalized_components
    return {
        "area": None,
        "aisle": components["aisle"],
        "rack": components["rack"],
        "level": components["level"],
        "position": components["position"],
        "capacity": capacity,
        "notes": None,
        "location_type": "standard",
        "lifecycle_status": "active",
        "barcode": None,
        "verification_code": None,
        "pick_sequence": None,
        "putaway_sequence": None,
        "external_id": external_id,
        "scheme_id": projection.scheme_id,
        "scheme_version": projection.scheme_version,
        "code_source": code_source,
        "is_active": True,
    }


def _source_row(
    projection: CodeProjection,
    *,
    capacity: int,
    external_id: str | None = None,
    row_number: int = 2,
) -> dict[str, Any]:
    return {
        "row_number": row_number,
        "code": projection.code,
        **_values(
            projection,
            capacity=capacity,
            external_id=external_id,
            code_source="imported",
        ),
    }


@pytest.mark.asyncio
async def test_historical_alias_is_reserved_from_reuse_by_another_location(
    location_session: AsyncSession,
) -> None:
    context = await _add_context(location_session)
    repository = SqlAlchemyLocationRepository(location_session)
    old_projection = _projection(context, code="A01-R01-N01-P01", aisle="01")
    location = await repository.create_location(
        context.warehouse_id,
        projection=old_projection,
        values=_values(old_projection, capacity=1, external_id="LEGACY-1"),
        actor_id=context.actor_id,
    )
    new_projection = _projection(context, code="A02-R01-N01-P01", aisle="02")

    await repository.update_location(
        context.warehouse_id,
        location.id,
        projection=new_projection,
        values=_values(new_projection, capacity=1, external_id="LEGACY-1"),
        actor_id=context.actor_id,
    )
    alias = await location_session.scalar(
        select(LocationCodeAlias).where(LocationCodeAlias.alias_code == old_projection.code)
    )
    assert alias is not None
    assert alias.location_id == location.id

    other_projection = _projection(
        context,
        code=old_projection.code,
        aisle="03",
        position="02",
    )
    with pytest.raises(ConflictError) as error:
        await repository.create_location(
            context.warehouse_id,
            projection=other_projection,
            values=_values(other_projection, capacity=1, external_id="OTHER-1"),
            actor_id=context.actor_id,
        )

    assert error.value.code == "location_alias_conflict"


@pytest.mark.asyncio
async def test_bulk_update_capacity_delta_is_revalidated_under_warehouse_lock(
    location_session: AsyncSession,
) -> None:
    context = await _add_context(location_session, warehouse_capacity=10)
    repository = SqlAlchemyLocationRepository(location_session)
    projection = _projection(context, code="A01-R01-N01-P01", aisle="01")
    await repository.create_location(
        context.warehouse_id,
        projection=projection,
        values=_values(projection, capacity=4, external_id="CAPACITY-1"),
        actor_id=context.actor_id,
    )
    job = await repository.create_batch_preview(
        context.warehouse_id,
        kind="import",
        idempotency_key=f"capacity-{_suffix()}",
        input_checksum="a" * 64,
        scheme=context.scheme,
        source_rows=[_source_row(projection, capacity=11, external_id="CAPACITY-1")],
        actor_id=context.actor_id,
    )
    assert job.update_count == 1

    with pytest.raises(ConflictError) as error:
        await repository.publish_batch(job.id, actor_id=context.actor_id)

    assert error.value.code == "warehouse_location_capacity_exceeded"


@pytest.mark.asyncio
async def test_bulk_publish_rejects_stale_update_without_overwriting_third_party_change(
    location_session: AsyncSession,
) -> None:
    context = await _add_context(location_session)
    repository = SqlAlchemyLocationRepository(location_session)
    projection = _projection(context, code="A01-R01-N01-P01", aisle="01")
    location = await repository.create_location(
        context.warehouse_id,
        projection=projection,
        values=_values(projection, capacity=1, external_id="STALE-1"),
        actor_id=context.actor_id,
    )
    job = await repository.create_batch_preview(
        context.warehouse_id,
        kind="import",
        idempotency_key=f"stale-{_suffix()}",
        input_checksum="8" * 64,
        scheme=context.scheme,
        source_rows=[_source_row(projection, capacity=2, external_id="STALE-1")],
        actor_id=context.actor_id,
    )
    await repository.update_location(
        context.warehouse_id,
        location.id,
        projection=projection,
        values=_values(projection, capacity=3, external_id="STALE-1"),
        actor_id=context.actor_id,
    )

    with pytest.raises(ConflictError) as error:
        await repository.publish_batch(job.id, actor_id=context.actor_id)

    assert error.value.code == "location_batch_stale_preview"
    assert await location_session.scalar(
        select(Location.capacity).where(Location.id == location.id)
    ) == 3
    assert await location_session.scalar(
        select(LocationBatchJob.status).where(LocationBatchJob.id == job.id)
    ) == "preview"


@pytest.mark.asyncio
async def test_bulk_recode_cycle_reuses_aliases_owned_by_same_location(
    location_session: AsyncSession,
) -> None:
    context = await _add_context(location_session)
    repository = SqlAlchemyLocationRepository(location_session)
    projection_a = _projection(context, code="A01-R01-N01-P01", aisle="01")
    projection_b = _projection(context, code="A02-R01-N01-P01", aisle="02")
    location = await repository.create_location(
        context.warehouse_id,
        projection=projection_a,
        values=_values(projection_a, capacity=1, external_id="CYCLE-1"),
        actor_id=context.actor_id,
    )
    for sequence, projection in enumerate(
        (projection_b, projection_a, projection_b), start=1
    ):
        job = await repository.create_batch_preview(
            context.warehouse_id,
            kind="import",
            idempotency_key=f"cycle-{sequence}-{_suffix()}",
            input_checksum=str(sequence) * 64,
            scheme=context.scheme,
            source_rows=[
                _source_row(projection, capacity=1, external_id="CYCLE-1")
            ],
            actor_id=context.actor_id,
        )
        published = await repository.publish_batch(job.id, actor_id=context.actor_id)
        assert published.status == "published"

    assert await location_session.scalar(
        select(Location.code).where(Location.id == location.id)
    ) == projection_b.code
    assert await location_session.scalar(
        select(func.count(LocationCodeAlias.id)).where(
            LocationCodeAlias.location_id == location.id
        )
    ) == 2


@pytest.mark.asyncio
async def test_bulk_preview_rejects_positive_impact_in_non_commissionable_warehouse(
    location_session: AsyncSession,
) -> None:
    context = await _add_context(
        location_session,
        warehouse_capacity=100,
        operational_status="full",
    )
    repository = SqlAlchemyLocationRepository(location_session)
    projection = _projection(context, code="A01-R01-N01-P01", aisle="01")
    with pytest.raises(ConflictError) as error:
        await repository.create_batch_preview(
            context.warehouse_id,
            kind="generate",
            idempotency_key=f"full-{_suffix()}",
            input_checksum="b" * 64,
            scheme=context.scheme,
            source_rows=[_source_row(projection, capacity=1)],
            actor_id=context.actor_id,
        )

    assert error.value.code == "warehouse_not_commissionable"


@pytest.mark.asyncio
async def test_coordinate_only_match_adopts_unique_legacy_location(
    location_session: AsyncSession,
) -> None:
    context = await _add_context(location_session)
    repository = SqlAlchemyLocationRepository(location_session)
    legacy_projection = _projection(
        context,
        code="LEGACY-BIN-0007",
        aisle="A01",
        rack="R01",
        level="N01",
        position="P01",
    )
    legacy_values = _values(legacy_projection, capacity=4, code_source="legacy")
    legacy = await repository.create_location(
        context.warehouse_id,
        projection=legacy_projection,
        values=legacy_values,
        actor_id=context.actor_id,
    )
    generated_projection = _projection(
        context,
        code="A01-R01-N01-P01",
        aisle="01",
        rack="01",
        level="01",
        position="01",
    )

    job = await repository.create_batch_preview(
        context.warehouse_id,
        kind="import",
        idempotency_key=f"adopt-{_suffix()}",
        input_checksum="1" * 64,
        scheme=context.scheme,
        source_rows=[_source_row(generated_projection, capacity=4)],
        actor_id=context.actor_id,
    )

    assert job.update_count == 1
    assert job.conflict_count == 0
    assert all(not key.startswith("_") for key in job.rows[0].normalized_data)
    published = await repository.publish_batch(job.id, actor_id=context.actor_id)
    assert published.status == "published"
    adopted = await location_session.get(Location, legacy.id)
    assert adopted is not None
    assert adopted.code == generated_projection.code
    assert adopted.aisle == "01"
    assert await location_session.scalar(
        select(func.count(LocationCodeAlias.id)).where(
            LocationCodeAlias.location_id == legacy.id,
            LocationCodeAlias.alias_code == legacy_projection.code,
        )
    ) == 1


@pytest.mark.asyncio
async def test_coordinate_only_match_never_hijacks_managed_location(
    location_session: AsyncSession,
) -> None:
    context = await _add_context(location_session)
    repository = SqlAlchemyLocationRepository(location_session)
    current_projection = _projection(
        context,
        code="CURRENT-MANAGED-CODE",
        aisle="A01",
        rack="R01",
        level="N01",
        position="P01",
    )
    await repository.create_location(
        context.warehouse_id,
        projection=current_projection,
        values=_values(current_projection, capacity=1, code_source="generated"),
        actor_id=context.actor_id,
    )
    incoming = _projection(context, code="A01-R01-N01-P01", aisle="01")

    job = await repository.create_batch_preview(
        context.warehouse_id,
        kind="import",
        idempotency_key=f"no-hijack-{_suffix()}",
        input_checksum="2" * 64,
        scheme=context.scheme,
        source_rows=[_source_row(incoming, capacity=1)],
        actor_id=context.actor_id,
    )

    assert job.conflict_count == 1
    assert job.update_count == 0


@pytest.mark.asyncio
async def test_partial_import_preserves_omitted_metadata_and_retired_state_when_full(
    location_session: AsyncSession,
) -> None:
    context = await _add_context(location_session)
    repository = SqlAlchemyLocationRepository(location_session)
    projection = _projection(context, code="A01-R01-N01-P01", aisle="01")
    values = _values(projection, capacity=5, external_id="PARTIAL-1")
    values.update(
        {
            "notes": "Metadato que debe conservarse",
            "barcode": "BAR-PARTIAL-1",
            "verification_code": "VERIFY-PARTIAL-1",
            "pick_sequence": 17,
            "location_type": "reserve",
            "lifecycle_status": "retired",
            "is_active": False,
        }
    )
    location = await repository.create_location(
        context.warehouse_id,
        projection=projection,
        values=values,
        actor_id=context.actor_id,
    )
    warehouse = await location_session.get(Warehouse, context.warehouse_id)
    assert warehouse is not None
    warehouse.operational_status = "full"
    await location_session.flush()
    source = _source_row(projection, capacity=3)
    source["_provided_fields"] = ["aisle", "rack", "level", "position", "capacity"]

    job = await repository.create_batch_preview(
        context.warehouse_id,
        kind="import",
        idempotency_key=f"partial-{_suffix()}",
        input_checksum="3" * 64,
        scheme=context.scheme,
        source_rows=[source],
        actor_id=context.actor_id,
    )

    assert job.update_count == 1
    assert job.required_permissions == ("locations.import", "locations.update")
    row_data = job.rows[0].normalized_data
    assert row_data["notes"] == "Metadato que debe conservarse"
    assert row_data["barcode"] == "BAR-PARTIAL-1"
    assert row_data["lifecycle_status"] == "retired"
    assert row_data["is_active"] is False
    assert "_provided_fields" not in row_data

    await repository.publish_batch(job.id, actor_id=context.actor_id)
    persisted = await location_session.get(Location, location.id)
    assert persisted is not None
    assert persisted.capacity == 3
    assert persisted.notes == "Metadato que debe conservarse"
    assert persisted.barcode == "BAR-PARTIAL-1"
    assert persisted.verification_code == "VERIFY-PARTIAL-1"
    assert persisted.pick_sequence == 17
    assert persisted.location_type == "reserve"
    assert persisted.lifecycle_status == "retired"
    assert persisted.is_active is False


@pytest.mark.asyncio
async def test_large_preview_response_is_windowed_but_all_rows_are_persisted(
    location_session: AsyncSession,
) -> None:
    context = await _add_context(location_session, warehouse_capacity=5000)
    repository = SqlAlchemyLocationRepository(location_session)
    rows = [
        _source_row(
            _projection(
                context,
                code=f"A{number:04}-R01-N01-P01",
                aisle=f"{number:04}",
            ),
            capacity=1,
            row_number=number + 1,
        )
        for number in range(1, 1001)
    ]

    job = await repository.create_batch_preview(
        context.warehouse_id,
        kind="generate",
        idempotency_key=f"window-{_suffix()}",
        input_checksum="f" * 64,
        scheme=context.scheme,
        source_rows=rows,
        actor_id=context.actor_id,
    )

    assert job.total_rows == 1000
    assert len(job.rows) == 100
    assert await location_session.scalar(
        select(func.count()).select_from(LocationBatchRow).where(LocationBatchRow.job_id == job.id)
    ) == 1000


@pytest.mark.asyncio
async def test_batch_preview_canonicalizes_uuid_values_for_jsonb(
    location_session: AsyncSession,
) -> None:
    context = await _add_context(location_session)
    repository = SqlAlchemyLocationRepository(location_session)
    projection = _projection(context, code="A01-R01-N01-P01", aisle="01")
    job = await repository.create_batch_preview(
        context.warehouse_id,
        kind="generate",
        idempotency_key=f"json-{_suffix()}",
        input_checksum="0" * 64,
        scheme=context.scheme,
        source_rows=[_source_row(projection, capacity=1)],
        actor_id=context.actor_id,
    )

    json.dumps(job.rows[0].normalized_data)


@pytest.mark.asyncio
async def test_location_restore_conflict_keeps_original_in_trash(
    location_session: AsyncSession,
) -> None:
    context = await _add_context(location_session)
    locations = SqlAlchemyLocationRepository(location_session)
    lifecycle = SqlAlchemyLifecycleRepository(location_session)
    original_projection = _projection(context, code="A01-R01-N01-P01", aisle="01")
    original = await locations.create_location(
        context.warehouse_id,
        projection=original_projection,
        values=_values(original_projection, capacity=1),
        actor_id=context.actor_id,
    )
    await lifecycle.soft_delete(
        "locations",
        str(original.id),
        company_id=context.company_id,
        actor_id=context.actor_id,
        reason="Prueba de restauración",
    )
    replacement_projection = _projection(
        context,
        code=original_projection.code,
        aisle="02",
    )
    await locations.create_location(
        context.warehouse_id,
        projection=replacement_projection,
        values=_values(replacement_projection, capacity=1),
        actor_id=context.actor_id,
    )

    with pytest.raises(ConflictError) as error:
        await lifecycle.restore(
            "locations",
            str(original.id),
            company_id=context.company_id,
            actor_id=context.actor_id,
        )

    assert error.value.code == "restore_unique_conflict"
    deleted_at = await location_session.scalar(
        select(Location.deleted_at)
        .where(Location.id == original.id)
        .execution_options(include_deleted=True)
    )
    assert deleted_at is not None


@pytest.mark.asyncio
async def test_location_lifecycle_scope_rejects_another_company(
    location_session: AsyncSession,
) -> None:
    owner = await _add_context(location_session)
    intruder = await _add_context(location_session)
    locations = SqlAlchemyLocationRepository(location_session)
    projection = _projection(owner, code="A01-R01-N01-P01", aisle="01")
    location = await locations.create_location(
        owner.warehouse_id,
        projection=projection,
        values=_values(projection, capacity=1),
        actor_id=owner.actor_id,
    )

    with pytest.raises(NotFoundError):
        await SqlAlchemyLifecycleRepository(location_session).soft_delete(
            "locations",
            str(location.id),
            company_id=intruder.company_id,
            actor_id=intruder.actor_id,
            reason="Cross-tenant attempt",
        )

    assert (
        await location_session.scalar(
            select(func.count(Location.id)).where(Location.id == location.id)
        )
        == 1
    )


@pytest.mark.asyncio
async def test_location_id_cannot_be_updated_through_another_company_warehouse(
    location_session: AsyncSession,
) -> None:
    owner = await _add_context(location_session)
    intruder = await _add_context(location_session)
    repository = SqlAlchemyLocationRepository(location_session)
    owner_projection = _projection(owner, code="A01-R01-N01-P01", aisle="01")
    location = await repository.create_location(
        owner.warehouse_id,
        projection=owner_projection,
        values=_values(owner_projection, capacity=1),
        actor_id=owner.actor_id,
    )
    intruder_projection = _projection(
        intruder,
        code="A99-R01-N01-P01",
        aisle="99",
    )

    with pytest.raises(NotFoundError) as error:
        await repository.update_location(
            intruder.warehouse_id,
            location.id,
            projection=intruder_projection,
            values=_values(intruder_projection, capacity=1),
            actor_id=intruder.actor_id,
        )

    assert error.value.code == "location_not_found"
    persisted_code = await location_session.scalar(
        select(Location.code).where(Location.id == location.id)
    )
    assert persisted_code == owner_projection.code


@pytest.mark.asyncio
async def test_real_repository_idempotency_reuses_job_and_rejects_new_payload(
    location_session: AsyncSession,
) -> None:
    context = await _add_context(location_session)
    repository = SqlAlchemyLocationRepository(location_session)
    projection = _projection(context, code="A01-R01-N01-P01", aisle="01")
    key = f"sequential-{_suffix()}"
    arguments = {
        "kind": "generate",
        "idempotency_key": key,
        "input_checksum": "c" * 64,
        "scheme": context.scheme,
        "source_rows": [_source_row(projection, capacity=1)],
        "actor_id": context.actor_id,
    }

    first = await repository.create_batch_preview(context.warehouse_id, **arguments)
    second = await repository.create_batch_preview(context.warehouse_id, **arguments)

    assert first.id == second.id
    with pytest.raises(ConflictError) as error:
        await repository.create_batch_preview(
            context.warehouse_id,
            **{**arguments, "input_checksum": "d" * 64},
        )
    assert error.value.code == "location_batch_idempotency_mismatch"


@pytest.mark.asyncio
async def test_concurrent_idempotent_previews_return_one_persisted_job() -> None:
    async with async_session_factory() as setup_session, setup_session.begin():
        context = await _add_context(setup_session)

    projection = _projection(context, code="A01-R01-N01-P01", aisle="01")
    key = f"concurrent-{_suffix()}"
    ready = 0
    ready_lock = asyncio.Lock()
    release = asyncio.Event()

    async def submit() -> uuid.UUID:
        nonlocal ready
        async with async_session_factory() as session, session.begin():
            async with ready_lock:
                ready += 1
                if ready == 4:
                    release.set()
            await release.wait()
            job = await SqlAlchemyLocationRepository(session).create_batch_preview(
                context.warehouse_id,
                kind="generate",
                idempotency_key=key,
                input_checksum="e" * 64,
                scheme=context.scheme,
                source_rows=[_source_row(projection, capacity=1)],
                actor_id=context.actor_id,
            )
            return job.id

    job_ids = await asyncio.gather(*(submit() for _ in range(4)))

    assert len(set(job_ids)) == 1
    async with async_session_factory() as verification_session:
        count = await verification_session.scalar(
            select(func.count(LocationBatchJob.id)).where(
                LocationBatchJob.warehouse_id == context.warehouse_id,
                LocationBatchJob.kind == "generate",
                LocationBatchJob.idempotency_key == key,
            )
        )
    assert count == 1
    await dispose_engine()
