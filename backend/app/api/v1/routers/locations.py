"""Versioned, generated and bulk warehouse-location API."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status

from app.api.v1.company_access import require_resource_company, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_check_permission_use_case,
    require_permission,
)
from app.api.v1.schemas.common import PageMeta
from app.api.v1.schemas.location import (
    GeneratorPreviewIn,
    LocationBatchOut,
    LocationCodePreviewIn,
    LocationCodePreviewOut,
    LocationCodeSchemeIn,
    LocationCodeSchemeOut,
    LocationOut,
    LocationPage,
    LocationSummaryOut,
    LocationWrite,
)
from app.application.locations import LocationUseCases
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import AuthorizationError, ValidationError
from app.domain.entities.location import WarehouseLocationScope
from app.infrastructure.repositories.location_repository import SqlAlchemyLocationRepository

router = APIRouter(tags=["locations"])


def _use_cases(session: SessionDep) -> LocationUseCases:
    return LocationUseCases(SqlAlchemyLocationRepository(session))


async def _authorize_warehouse(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: LocationUseCases,
    warehouse_id: uuid.UUID,
) -> WarehouseLocationScope:
    scope = await use_cases.warehouse_scope(warehouse_id)
    require_resource_company(request, scope.company_id, not_found_detail="Almacén no encontrado.")
    await resolve_branch_scope(session, current, scope.company_id, scope.branch_id)
    return scope


async def _authorize_batch(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: LocationUseCases,
    job_id: uuid.UUID,
) -> WarehouseLocationScope:
    scope = await use_cases.batch_scope(job_id)
    require_resource_company(request, scope.company_id, not_found_detail="Lote no encontrado.")
    await resolve_branch_scope(session, current, scope.company_id, scope.branch_id)
    return scope


async def _require_dynamic_permissions(
    checker: CheckPermissionUseCase,
    current: CurrentUser,
    company_id: uuid.UUID,
    permissions: tuple[str, ...],
) -> None:
    for permission in permissions:
        result = await checker.execute(current.id, company_id, permission)
        if not result.allowed:
            raise AuthorizationError(
                f"Permiso requerido: {permission}",
                code="location_operation_forbidden",
            )


@router.get(
    "/warehouses/{warehouse_id}/locations",
    response_model=LocationPage,
    dependencies=[Depends(require_permission("locations.view"))],
)
async def list_locations(
    warehouse_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    search: str | None = Query(None, max_length=120),
    area: str | None = Query(None, max_length=64),
    location_type: str | None = Query(None, max_length=32),
    lifecycle_status: str | None = Query(None, max_length=24),
    is_active: bool | None = None,
    capacity_group_id: uuid.UUID | None = Query(None),
    include_descendants: bool = Query(True),
    unassigned: bool = Query(False),
) -> LocationPage:
    use_cases = _use_cases(session)
    await _authorize_warehouse(request, session, current, use_cases, warehouse_id)
    if capacity_group_id is not None and unassigned:
        raise ValidationError(
            "Seleccione una estructura o las ubicaciones sin estructura, no ambas.",
            code="location_filter_conflict",
        )
    items, total = await use_cases.list_locations(
        warehouse_id,
        page=page,
        size=size,
        search=search,
        area=area,
        location_type=location_type,
        lifecycle_status=lifecycle_status,
        is_active=is_active,
        capacity_group_id=capacity_group_id,
        include_descendants=include_descendants,
        unassigned=unassigned,
    )
    return LocationPage(
        items=[LocationOut.model_validate(item) for item in items],
        meta=PageMeta(
            page=page,
            size=size,
            total=total,
            pages=(total + size - 1) // size if total else 1,
        ),
    )


@router.get(
    "/warehouses/{warehouse_id}/locations/summary",
    response_model=LocationSummaryOut,
    dependencies=[Depends(require_permission("locations.view"))],
)
async def location_summary(
    warehouse_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> LocationSummaryOut:
    use_cases = _use_cases(session)
    await _authorize_warehouse(request, session, current, use_cases, warehouse_id)
    return LocationSummaryOut.model_validate(await use_cases.summary(warehouse_id))


@router.post(
    "/warehouses/{warehouse_id}/locations/code-preview",
    response_model=LocationCodePreviewOut,
    dependencies=[Depends(require_permission("locations.view"))],
)
async def preview_location_code(
    warehouse_id: uuid.UUID,
    body: LocationCodePreviewIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> LocationCodePreviewOut:
    use_cases = _use_cases(session)
    await _authorize_warehouse(request, session, current, use_cases, warehouse_id)
    projection, code_exists, coordinates_exist = await use_cases.preview_code(
        warehouse_id,
        body.model_dump(exclude={"scheme_version", "exclude_location_id"}),
        scheme_version=body.scheme_version,
        exclude_location_id=body.exclude_location_id,
    )
    return LocationCodePreviewOut(
        code=projection.code,
        normalized_components=projection.normalized_components,
        scheme_id=projection.scheme_id,
        scheme_version=projection.scheme_version,
        code_exists=code_exists,
        coordinates_exist=coordinates_exist,
    )


@router.get(
    "/warehouses/{warehouse_id}/location-code-scheme",
    response_model=LocationCodeSchemeOut,
    dependencies=[Depends(require_permission("locations.view"))],
)
async def get_location_code_scheme(
    warehouse_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    version: int | None = Query(None, ge=1),
) -> LocationCodeSchemeOut:
    use_cases = _use_cases(session)
    await _authorize_warehouse(request, session, current, use_cases, warehouse_id)
    return LocationCodeSchemeOut.model_validate(await use_cases.get_scheme(warehouse_id, version))


@router.put(
    "/warehouses/{warehouse_id}/location-code-scheme",
    response_model=LocationCodeSchemeOut,
    dependencies=[Depends(require_permission("locations.scheme"))],
)
async def update_location_code_scheme(
    warehouse_id: uuid.UUID,
    body: LocationCodeSchemeIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> LocationCodeSchemeOut:
    use_cases = _use_cases(session)
    await _authorize_warehouse(request, session, current, use_cases, warehouse_id)
    scheme = await use_cases.update_scheme(
        warehouse_id,
        name=body.name,
        separator=body.separator,
        segments=[item.model_dump() for item in body.segments],
        actor_id=current.id,
    )
    return LocationCodeSchemeOut.model_validate(scheme)


@router.post(
    "/warehouses/{warehouse_id}/locations",
    response_model=LocationOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("locations.create"))],
)
async def create_location(
    warehouse_id: uuid.UUID,
    body: LocationWrite,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> LocationOut:
    use_cases = _use_cases(session)
    await _authorize_warehouse(request, session, current, use_cases, warehouse_id)
    location = await use_cases.create_location(
        warehouse_id,
        body.model_dump(exclude={"scheme_version", "expected_updated_at"}),
        actor_id=current.id,
        scheme_version=body.scheme_version,
    )
    return LocationOut.model_validate(location)


@router.get(
    "/warehouses/{warehouse_id}/locations/{location_id}",
    response_model=LocationOut,
    dependencies=[Depends(require_permission("locations.view"))],
)
async def get_location(
    warehouse_id: uuid.UUID,
    location_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> LocationOut:
    use_cases = _use_cases(session)
    await _authorize_warehouse(request, session, current, use_cases, warehouse_id)
    return LocationOut.model_validate(await use_cases.get_location(warehouse_id, location_id))


@router.patch(
    "/warehouses/{warehouse_id}/locations/{location_id}",
    response_model=LocationOut,
    dependencies=[Depends(require_permission("locations.update"))],
)
async def update_location(
    warehouse_id: uuid.UUID,
    location_id: uuid.UUID,
    body: LocationWrite,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
) -> LocationOut:
    use_cases = _use_cases(session)
    scope = await _authorize_warehouse(request, session, current, use_cases, warehouse_id)
    if body.expected_updated_at is None:
        raise ValidationError(
            "Recargue la ubicación antes de guardarla para evitar sobrescribir cambios recientes.",
            code="location_update_precondition_required",
        )
    values = body.model_dump(exclude={"scheme_version", "expected_updated_at"})
    required = await use_cases.required_update_permissions(
        warehouse_id,
        location_id,
        values,
        scheme_version=body.scheme_version,
    )
    await _require_dynamic_permissions(checker, current, scope.company_id, required)
    location = await use_cases.update_location(
        warehouse_id,
        location_id,
        values,
        actor_id=current.id,
        scheme_version=body.scheme_version,
        expected_updated_at=body.expected_updated_at,
    )
    return LocationOut.model_validate(location)


@router.post(
    "/warehouses/{warehouse_id}/location-batches/generate/preview",
    response_model=LocationBatchOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permission("locations.bulk")),
        Depends(require_permission("locations.view")),
    ],
)
async def preview_location_generator(
    warehouse_id: uuid.UUID,
    body: GeneratorPreviewIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> LocationBatchOut:
    use_cases = _use_cases(session)
    await _authorize_warehouse(request, session, current, use_cases, warehouse_id)
    job = await use_cases.preview_generator(
        warehouse_id,
        axes=[axis.model_dump(exclude_none=True) for axis in body.axes],
        defaults=body.defaults.model_dump(),
        idempotency_key=body.idempotency_key,
        actor_id=current.id,
        scheme_version=body.scheme_version,
    )
    return LocationBatchOut.model_validate(job)


@router.post(
    "/warehouses/{warehouse_id}/location-imports/preview",
    response_model=LocationBatchOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permission("locations.import")),
        Depends(require_permission("locations.view")),
    ],
)
async def preview_location_import(
    warehouse_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    file: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str, Form(min_length=8, max_length=120)],
    scheme_version: Annotated[int | None, Form(ge=1)] = None,
) -> LocationBatchOut:
    use_cases = _use_cases(session)
    await _authorize_warehouse(request, session, current, use_cases, warehouse_id)
    content = await file.read(20 * 1024 * 1024 + 1)
    job = await use_cases.preview_import(
        warehouse_id,
        filename=file.filename or "",
        content=content,
        idempotency_key=idempotency_key,
        actor_id=current.id,
        scheme_version=scheme_version,
    )
    return LocationBatchOut.model_validate(job)


@router.get(
    "/location-batches/{job_id}",
    response_model=LocationBatchOut,
    dependencies=[Depends(require_permission("locations.view"))],
)
async def get_location_batch(
    job_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=100),
) -> LocationBatchOut:
    use_cases = _use_cases(session)
    await _authorize_batch(request, session, current, use_cases, job_id)
    return LocationBatchOut.model_validate(await use_cases.get_batch(job_id, page=page, size=size))


@router.post(
    "/location-batches/{job_id}/publish",
    response_model=LocationBatchOut,
    dependencies=[Depends(require_permission("locations.view"))],
)
async def publish_location_batch(
    job_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
) -> LocationBatchOut:
    use_cases = _use_cases(session)
    scope = await _authorize_batch(request, session, current, use_cases, job_id)
    await _require_dynamic_permissions(
        checker,
        current,
        scope.company_id,
        await use_cases.batch_required_permissions(job_id),
    )
    return LocationBatchOut.model_validate(
        await use_cases.publish_batch(job_id, actor_id=current.id)
    )
