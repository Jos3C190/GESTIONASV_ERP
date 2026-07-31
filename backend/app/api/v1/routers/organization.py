"""Company, branch and warehouse maintenance endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import SessionDep, require_permission
from app.api.v1.schemas.organization import (
    BranchIn,
    CompanyIn,
    LocationIn,
    WarehouseCategoryIn,
    WarehouseIn,
)
from app.infrastructure.models.audit import AuditLog
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

router = APIRouter(tags=["organization"])


def _json_value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def _dump(obj: Any) -> dict[str, Any]:
    return {
        column.name: _json_value(value)
        for column in obj.__table__.columns
        if (value := getattr(obj, column.name)) is not None
    }


def _actor_id(request: Request) -> uuid.UUID:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="No autenticado.")
    return user.id


async def _create(
    session: AsyncSession,
    cls: type[Any],
    body: Any,
    *,
    user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    obj = cls(**body.model_dump(exclude_none=True))
    session.add(obj)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "Registro duplicado o relación inválida.") from exc
    state = _dump(obj)
    session.add(
        AuditLog(
            action="CREATE",
            user_id=user_id,
            resource_type=cls.__tablename__,
            resource_id=str(obj.id),
            after_state=state,
        )
    )
    return state


async def _list(session: AsyncSession, cls: type[Any]) -> list[dict[str, Any]]:
    return [_dump(item) for item in (await session.execute(select(cls))).scalars().all()]


async def _update(
    session: AsyncSession,
    cls: type[Any],
    record_id: uuid.UUID,
    values: dict[str, Any],
    *,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    obj = await session.get(cls, record_id)
    if obj is None:
        raise HTTPException(404, "Registro no encontrado.")
    before = _dump(obj)
    for key, value in values.items():
        setattr(obj, key, value)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "Registro duplicado o relación inválida.") from exc
    after = _dump(obj)
    session.add(
        AuditLog(
            action="UPDATE",
            user_id=user_id,
            resource_type=cls.__tablename__,
            resource_id=str(obj.id),
            before_state=before,
            after_state=after,
        )
    )
    return after


async def _validate_address(
    session: AsyncSession,
    department_id: uuid.UUID,
    municipality_id: uuid.UUID,
    district_id: uuid.UUID,
) -> None:
    municipality = await session.get(Municipality, municipality_id)
    district = await session.get(District, district_id)
    if (
        await session.get(GeographicDepartment, department_id) is None
        or municipality is None
        or municipality.department_id != department_id
        or district is None
        or district.municipality_id != municipality_id
    ):
        raise HTTPException(
            status_code=422,
            detail="La combinación departamento, municipio y distrito no es válida.",
        )


async def _require_active(
    session: AsyncSession, cls: type[Any], record_id: uuid.UUID, label: str
) -> Any:
    obj = await session.get(cls, record_id)
    if obj is None:
        raise HTTPException(status_code=422, detail=f"{label} no existe.")
    if not obj.is_active:
        raise HTTPException(status_code=422, detail=f"{label} está inactivo.")
    return obj


@router.get("/geographic-departments")
async def list_geographic_departments(session: SessionDep) -> list[dict[str, Any]]:
    return await _list(session, GeographicDepartment)


@router.get("/municipalities")
async def list_municipalities(
    session: SessionDep, department_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    stmt = select(Municipality)
    if department_id is not None:
        stmt = stmt.where(Municipality.department_id == department_id)
    return [_dump(item) for item in (await session.execute(stmt)).scalars().all()]


@router.get("/districts")
async def list_districts(
    session: SessionDep, municipality_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    stmt = select(District)
    if municipality_id is not None:
        stmt = stmt.where(District.municipality_id == municipality_id)
    return [_dump(item) for item in (await session.execute(stmt)).scalars().all()]


@router.get("/companies", dependencies=[Depends(require_permission("companies.view"))])
async def list_companies(session: SessionDep) -> list[dict[str, Any]]:
    return await _list(session, Company)


@router.post(
    "/companies",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("companies.create"))],
)
async def create_company(body: CompanyIn, request: Request, session: SessionDep) -> dict[str, Any]:
    await _validate_address(session, body.department_id, body.municipality_id, body.district_id)
    return await _create(session, Company, body, user_id=_actor_id(request))


@router.patch(
    "/companies/{record_id}", dependencies=[Depends(require_permission("companies.update"))]
)
async def update_company(
    record_id: uuid.UUID, body: CompanyIn, request: Request, session: SessionDep
) -> dict[str, Any]:
    await _validate_address(session, body.department_id, body.municipality_id, body.district_id)
    return await _update(
        session,
        Company,
        record_id,
        body.model_dump(exclude_none=True),
        user_id=_actor_id(request),
    )


@router.post(
    "/companies/{record_id}/activate",
    dependencies=[Depends(require_permission("companies.activate"))],
)
async def activate_company(
    record_id: uuid.UUID, request: Request, session: SessionDep
) -> dict[str, Any]:
    return await _update(
        session, Company, record_id, {"is_active": True}, user_id=_actor_id(request)
    )


@router.post(
    "/companies/{record_id}/deactivate",
    dependencies=[Depends(require_permission("companies.deactivate"))],
)
async def deactivate_company(
    record_id: uuid.UUID, request: Request, session: SessionDep
) -> dict[str, Any]:
    return await _update(
        session, Company, record_id, {"is_active": False}, user_id=_actor_id(request)
    )


@router.get("/branches", dependencies=[Depends(require_permission("branches.view"))])
async def list_branches(session: SessionDep) -> list[dict[str, Any]]:
    return await _list(session, Branch)


@router.post(
    "/branches",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("branches.create"))],
)
async def create_branch(body: BranchIn, request: Request, session: SessionDep) -> dict[str, Any]:
    await _require_active(session, Company, body.company_id, "La empresa")
    await _validate_address(session, body.department_id, body.municipality_id, body.district_id)
    return await _create(session, Branch, body, user_id=_actor_id(request))


@router.patch(
    "/branches/{record_id}", dependencies=[Depends(require_permission("branches.update"))]
)
async def update_branch(
    record_id: uuid.UUID, body: BranchIn, request: Request, session: SessionDep
) -> dict[str, Any]:
    await _require_active(session, Company, body.company_id, "La empresa")
    await _validate_address(session, body.department_id, body.municipality_id, body.district_id)
    return await _update(
        session,
        Branch,
        record_id,
        body.model_dump(exclude_none=True),
        user_id=_actor_id(request),
    )


@router.post(
    "/branches/{record_id}/activate",
    dependencies=[Depends(require_permission("branches.activate"))],
)
async def activate_branch(
    record_id: uuid.UUID, request: Request, session: SessionDep
) -> dict[str, Any]:
    return await _update(
        session, Branch, record_id, {"is_active": True}, user_id=_actor_id(request)
    )


@router.post(
    "/branches/{record_id}/deactivate",
    dependencies=[Depends(require_permission("branches.deactivate"))],
)
async def deactivate_branch(
    record_id: uuid.UUID, request: Request, session: SessionDep
) -> dict[str, Any]:
    return await _update(
        session, Branch, record_id, {"is_active": False}, user_id=_actor_id(request)
    )


@router.get(
    "/warehouse-categories", dependencies=[Depends(require_permission("warehouse_categories.view"))]
)
async def list_categories(session: SessionDep) -> list[dict[str, Any]]:
    return await _list(session, WarehouseCategory)


@router.post(
    "/warehouse-categories",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("warehouse_categories.create"))],
)
async def create_category(
    body: WarehouseCategoryIn, request: Request, session: SessionDep
) -> dict[str, Any]:
    return await _create(session, WarehouseCategory, body, user_id=_actor_id(request))


@router.patch(
    "/warehouse-categories/{record_id}",
    dependencies=[Depends(require_permission("warehouse_categories.update"))],
)
async def update_category(
    record_id: uuid.UUID,
    body: WarehouseCategoryIn,
    request: Request,
    session: SessionDep,
) -> dict[str, Any]:
    return await _update(
        session,
        WarehouseCategory,
        record_id,
        body.model_dump(exclude_none=True),
        user_id=_actor_id(request),
    )


@router.post(
    "/warehouse-categories/{record_id}/deactivate",
    dependencies=[Depends(require_permission("warehouse_categories.deactivate"))],
)
async def deactivate_category(
    record_id: uuid.UUID, request: Request, session: SessionDep
) -> dict[str, Any]:
    return await _update(
        session,
        WarehouseCategory,
        record_id,
        {"is_active": False},
        user_id=_actor_id(request),
    )


@router.post(
    "/warehouse-categories/{record_id}/activate",
    dependencies=[Depends(require_permission("warehouse_categories.activate"))],
)
async def activate_category(
    record_id: uuid.UUID, request: Request, session: SessionDep
) -> dict[str, Any]:
    return await _update(
        session,
        WarehouseCategory,
        record_id,
        {"is_active": True},
        user_id=_actor_id(request),
    )


@router.get("/warehouses", dependencies=[Depends(require_permission("warehouses.view"))])
async def list_warehouses(session: SessionDep) -> list[dict[str, Any]]:
    return await _list(session, Warehouse)


@router.post(
    "/warehouses",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("warehouses.create"))],
)
async def create_warehouse(
    body: WarehouseIn, request: Request, session: SessionDep
) -> dict[str, Any]:
    await _require_active(session, Branch, body.branch_id, "La sucursal")
    await _require_active(
        session,
        WarehouseCategory,
        body.warehouse_category_id,
        "La categoría de almacén",
    )
    return await _create(session, Warehouse, body, user_id=_actor_id(request))


@router.patch(
    "/warehouses/{record_id}", dependencies=[Depends(require_permission("warehouses.update"))]
)
async def update_warehouse(
    record_id: uuid.UUID, body: WarehouseIn, request: Request, session: SessionDep
) -> dict[str, Any]:
    await _require_active(session, Branch, body.branch_id, "La sucursal")
    await _require_active(
        session,
        WarehouseCategory,
        body.warehouse_category_id,
        "La categoría de almacén",
    )
    return await _update(
        session,
        Warehouse,
        record_id,
        body.model_dump(exclude_none=True),
        user_id=_actor_id(request),
    )


@router.post(
    "/warehouses/{record_id}/deactivate",
    dependencies=[Depends(require_permission("warehouses.deactivate"))],
)
async def deactivate_warehouse(
    record_id: uuid.UUID, request: Request, session: SessionDep
) -> dict[str, Any]:
    return await _update(
        session, Warehouse, record_id, {"is_active": False}, user_id=_actor_id(request)
    )


@router.post(
    "/warehouses/{record_id}/activate",
    dependencies=[Depends(require_permission("warehouses.activate"))],
)
async def activate_warehouse(
    record_id: uuid.UUID, request: Request, session: SessionDep
) -> dict[str, Any]:
    return await _update(
        session, Warehouse, record_id, {"is_active": True}, user_id=_actor_id(request)
    )


@router.get("/locations", dependencies=[Depends(require_permission("locations.view"))])
async def list_locations(session: SessionDep) -> list[dict[str, Any]]:
    return await _list(session, Location)


@router.post(
    "/locations",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("locations.create"))],
)
async def create_location(
    body: LocationIn, request: Request, session: SessionDep
) -> dict[str, Any]:
    await _require_active(session, Warehouse, body.warehouse_id, "El almacén")
    return await _create(session, Location, body, user_id=_actor_id(request))


@router.patch(
    "/locations/{record_id}", dependencies=[Depends(require_permission("locations.update"))]
)
async def update_location(
    record_id: uuid.UUID, body: LocationIn, request: Request, session: SessionDep
) -> dict[str, Any]:
    await _require_active(session, Warehouse, body.warehouse_id, "El almacén")
    return await _update(
        session,
        Location,
        record_id,
        body.model_dump(exclude_none=True),
        user_id=_actor_id(request),
    )


@router.post(
    "/locations/{record_id}/deactivate",
    dependencies=[Depends(require_permission("locations.deactivate"))],
)
async def deactivate_location(
    record_id: uuid.UUID, request: Request, session: SessionDep
) -> dict[str, Any]:
    return await _update(
        session, Location, record_id, {"is_active": False}, user_id=_actor_id(request)
    )


@router.post(
    "/locations/{record_id}/activate",
    dependencies=[Depends(require_permission("locations.activate"))],
)
async def activate_location(
    record_id: uuid.UUID, request: Request, session: SessionDep
) -> dict[str, Any]:
    return await _update(
        session, Location, record_id, {"is_active": True}, user_id=_actor_id(request)
    )
