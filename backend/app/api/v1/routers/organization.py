"""Company, branch and warehouse maintenance endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.company_access import (
    get_branch_context,
    require_company_access,
    require_company_wide_scope,
    resolve_branch_scope,
)
from app.api.v1.deps import CurrentUser, SessionDep, require_permission
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.organization import (
    BranchIn,
    CompanyIn,
    LocationIn,
    WarehouseCategoryIn,
    WarehouseIn,
    WarehouseListSummary,
    WarehousePage,
)
from app.infrastructure.media_assets import attach_media_by_url
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.employee import Employee, EmployeeBranchAssignment
from app.infrastructure.models.media import MediaAsset
from app.infrastructure.models.organization import (
    Branch,
    Company,
    District,
    GeographicDepartment,
    Location,
    Municipality,
    UserCompany,
    Warehouse,
    WarehouseCategory,
)

router = APIRouter(tags=["organization"])


def _json_value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
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
    company_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
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
            company_id=company_id,
            branch_id=branch_id,
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
    company_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    action: str = "UPDATE",
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
            action=action,
            user_id=user_id,
            company_id=company_id,
            branch_id=branch_id,
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


async def _require_company_access(
    session: AsyncSession, current: CurrentUser, company_id: uuid.UUID
) -> Company:
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    if current.is_superuser:
        return company
    membership = await session.get(UserCompany, (current.id, company_id))
    if membership is None:
        raise HTTPException(status_code=403, detail="No tiene acceso a esta empresa.")
    return company


async def _ensure_branch_manager_assignment(
    session: AsyncSession,
    *,
    employee_id: uuid.UUID,
    branch_id: uuid.UUID,
    company_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> None:
    assignment = await session.scalar(
        select(EmployeeBranchAssignment).where(
            EmployeeBranchAssignment.employee_id == employee_id,
            EmployeeBranchAssignment.branch_id == branch_id,
        )
    )
    if assignment is None:
        assignment = EmployeeBranchAssignment(
            employee_id=employee_id,
            branch_id=branch_id,
            is_primary=False,
            is_active=True,
        )
        session.add(assignment)
        await session.flush()
    elif not assignment.is_active:
        assignment.is_active = True
        assignment.assigned_until = None
    session.add(
        AuditLog(
            action="ASSIGN",
            user_id=user_id,
            company_id=company_id,
            branch_id=branch_id,
            resource_type="employee_branch_assignments",
            resource_id=str(assignment.id),
            after_state={"employee_id": str(employee_id), "manager": True},
        )
    )


async def _branches_out(session: AsyncSession, branches: list[Branch]) -> list[dict[str, Any]]:
    """Serialize branches with a constant number of aggregate queries."""
    if not branches:
        return []
    branch_ids = [branch.id for branch in branches]
    district_ids = {branch.district_id for branch in branches}
    manager_ids = {
        branch.manager_employee_id for branch in branches if branch.manager_employee_id is not None
    }
    districts = {
        item.id: item
        for item in (
            await session.execute(select(District).where(District.id.in_(district_ids)))
        ).scalars()
    }
    managers = (
        {
            item.id: item
            for item in (
                await session.execute(select(Employee).where(Employee.id.in_(manager_ids)))
            ).scalars()
        }
        if manager_ids
        else {}
    )
    warehouse_counts = dict(
        (
            await session.execute(
                select(Warehouse.branch_id, func.count(Warehouse.id))
                .where(Warehouse.branch_id.in_(branch_ids))
                .group_by(Warehouse.branch_id)
            )
        ).all()
    )
    employee_counts = dict(
        (
            await session.execute(
                select(
                    EmployeeBranchAssignment.branch_id,
                    func.count(EmployeeBranchAssignment.id),
                )
                .where(
                    EmployeeBranchAssignment.branch_id.in_(branch_ids),
                    EmployeeBranchAssignment.is_active.is_(True),
                )
                .group_by(EmployeeBranchAssignment.branch_id)
            )
        ).all()
    )
    output: list[dict[str, Any]] = []
    for branch in branches:
        data = _dump(branch)
        district = districts.get(branch.district_id)
        manager = managers.get(branch.manager_employee_id)
        data.update(
            {
                "city": district.name if district else "",
                "manager": f"{manager.first_name} {manager.last_name}"
                if manager
                else "Sin responsable",
                "manager_initials": f"{manager.first_name[:1]}{manager.last_name[:1]}"
                if manager
                else "—",
                "employees": employee_counts.get(branch.id, 0),
                "warehouses": warehouse_counts.get(branch.id, 0),
                "sales_this_month": 0,
                "sales_last_month": 0,
                "sales_ytd": 0,
                "trend": [],
            }
        )
        output.append(data)
    return output


async def _branch_out(session: AsyncSession, branch: Branch) -> dict[str, Any]:
    return (await _branches_out(session, [branch]))[0]


async def _warehouses_out(
    session: AsyncSession, warehouses: list[Warehouse]
) -> list[dict[str, Any]]:
    """Serialize warehouses without per-row branch, manager and capacity lookups."""
    if not warehouses:
        return []
    warehouse_ids = [warehouse.id for warehouse in warehouses]
    branch_ids = {warehouse.branch_id for warehouse in warehouses}
    manager_ids = {
        warehouse.manager_employee_id
        for warehouse in warehouses
        if warehouse.manager_employee_id is not None
    }
    branches = {
        item.id: item
        for item in (
            await session.execute(select(Branch).where(Branch.id.in_(branch_ids)))
        ).scalars()
    }
    managers = (
        {
            item.id: item
            for item in (
                await session.execute(select(Employee).where(Employee.id.in_(manager_ids)))
            ).scalars()
        }
        if manager_ids
        else {}
    )
    capacities = dict(
        (
            await session.execute(
                select(Location.warehouse_id, func.coalesce(func.sum(Location.capacity), 0))
                .where(
                    Location.warehouse_id.in_(warehouse_ids),
                    Location.is_active.is_(True),
                )
                .group_by(Location.warehouse_id)
            )
        ).all()
    )
    output: list[dict[str, Any]] = []
    for warehouse in warehouses:
        data = _dump(warehouse)
        branch = branches.get(warehouse.branch_id)
        manager = managers.get(warehouse.manager_employee_id)
        data.update(
            {
                "type": warehouse.warehouse_type,
                "status": warehouse.operational_status,
                "location": warehouse.physical_location or "",
                "branch_name": branch.name if branch else "",
                "branch_address": branch.address if branch else "",
                "manager": f"{manager.first_name} {manager.last_name}"
                if manager
                else "Sin responsable",
                "manager_initials": f"{manager.first_name[:1]}{manager.last_name[:1]}"
                if manager
                else "—",
                "capacity": warehouse.capacity or capacities.get(warehouse.id, 0),
                "used": 0,
                "products": 0,
                "operators": 0,
                "total_skus": 0,
                "top_categories": [],
                "low_stock_items": 0,
                "expiring_items": 0,
                "inventory_value": 0,
                "inventory_turnover": 0,
                "last_movement": "Sin integración de inventario",
                "inbound_this_month": 0,
                "outbound_this_month": 0,
                "daily_movements_avg": 0,
                "trend": [],
                "recent_movements": [],
                "top_products": [],
                "shelves_occupied": 0,
            }
        )
        output.append(data)
    return output


async def _warehouse_out(session: AsyncSession, warehouse: Warehouse) -> dict[str, Any]:
    return (await _warehouses_out(session, [warehouse]))[0]


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


@router.get("/companies/accessible")
async def list_accessible_companies(
    session: SessionDep, current: CurrentUser
) -> list[dict[str, Any]]:
    stmt = select(Company).order_by(Company.commercial_name)
    if not current.is_superuser:
        stmt = stmt.join(UserCompany).where(UserCompany.user_id == current.id)
    return [_dump(item) for item in (await session.execute(stmt)).scalars().all()]


@router.get("/companies", dependencies=[Depends(require_permission("companies.view"))])
async def list_companies(session: SessionDep, current: CurrentUser) -> list[dict[str, Any]]:
    return await list_accessible_companies(session, current)


@router.get("/companies/{record_id}", dependencies=[Depends(require_permission("companies.view"))])
async def get_company(
    record_id: uuid.UUID, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    return _dump(await _require_company_access(session, current, record_id))


@router.post(
    "/companies",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("companies.create"))],
)
async def create_company(body: CompanyIn, request: Request, session: SessionDep) -> dict[str, Any]:
    await _validate_address(session, body.department_id, body.municipality_id, body.district_id)
    created = await _create(session, Company, body, user_id=_actor_id(request))
    company_id = uuid.UUID(created["id"])
    await attach_media_by_url(
        session,
        secure_url=body.logo,
        company_id=company_id,
        owner_type="company",
        owner_id=company_id,
        replace_single=True,
    )
    session.add(
        UserCompany(
            user_id=_actor_id(request),
            company_id=company_id,
            is_default=False,
            access_all_branches=True,
        )
    )
    return created


@router.patch(
    "/companies/{record_id}", dependencies=[Depends(require_permission("companies.update"))]
)
async def update_company(
    record_id: uuid.UUID,
    body: CompanyIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> dict[str, Any]:
    await _require_company_access(session, current, record_id)
    await _validate_address(session, body.department_id, body.municipality_id, body.district_id)
    updated = await _update(
        session,
        Company,
        record_id,
        body.model_dump(exclude_none=True),
        user_id=_actor_id(request),
    )
    await attach_media_by_url(
        session,
        secure_url=body.logo,
        company_id=record_id,
        owner_type="company",
        owner_id=record_id,
        replace_single=True,
    )
    return updated


@router.post(
    "/companies/{record_id}/activate",
    dependencies=[Depends(require_permission("companies.activate"))],
)
async def activate_company(
    record_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    await _require_company_access(session, current, record_id)
    return await _update(
        session,
        Company,
        record_id,
        {"is_active": True},
        user_id=_actor_id(request),
        action="ACTIVATE",
    )


@router.post(
    "/companies/{record_id}/deactivate",
    dependencies=[Depends(require_permission("companies.deactivate"))],
)
async def deactivate_company(
    record_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    await _require_company_access(session, current, record_id)
    active_branch = await session.scalar(
        select(Branch.id).where(Branch.company_id == record_id, Branch.is_active.is_(True)).limit(1)
    )
    if active_branch:
        raise HTTPException(409, "Desactive primero todas las sucursales de la empresa.")
    return await _update(
        session,
        Company,
        record_id,
        {"is_active": False},
        user_id=_actor_id(request),
        action="DEACTIVATE",
    )


@router.get("/branches", dependencies=[Depends(require_permission("branches.view"))])
async def list_branches(
    session: SessionDep, current: CurrentUser, company_id: uuid.UUID
) -> list[dict[str, Any]]:
    context = await get_branch_context(session, current, company_id)
    accessible_ids = {branch.id for branch in context.branches}
    stmt = select(Branch).where(Branch.company_id == company_id)
    if not context.access_all_branches:
        stmt = stmt.where(Branch.id.in_(accessible_ids))
    rows = (await session.execute(stmt.order_by(Branch.name))).scalars().all()
    return await _branches_out(session, list(rows))


@router.get("/branches/{record_id}", dependencies=[Depends(require_permission("branches.view"))])
async def get_branch(
    record_id: uuid.UUID, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    branch = await session.get(Branch, record_id)
    if branch is None:
        raise HTTPException(404, "Sucursal no encontrada.")
    await resolve_branch_scope(session, current, branch.company_id, branch.id)
    return await _branch_out(session, branch)


@router.post(
    "/branches",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("branches.create"))],
)
async def create_branch(
    body: BranchIn, request: Request, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    await require_company_wide_scope(session, current, body.company_id)
    await _require_active(session, Company, body.company_id, "La empresa")
    await _validate_address(session, body.department_id, body.municipality_id, body.district_id)
    if body.manager_employee_id:
        manager = await session.get(Employee, body.manager_employee_id)
        if manager is None or manager.company_id != body.company_id or manager.status != "activo":
            raise HTTPException(
                409, "El encargado debe ser un empleado activo de la misma empresa."
            )
    created = await _create(
        session,
        Branch,
        body,
        user_id=_actor_id(request),
        company_id=body.company_id,
    )
    branch_id = uuid.UUID(created["id"])
    if body.manager_employee_id:
        await _ensure_branch_manager_assignment(
            session,
            employee_id=body.manager_employee_id,
            branch_id=branch_id,
            company_id=body.company_id,
            user_id=_actor_id(request),
        )
    for image in body.images:
        await attach_media_by_url(
            session,
            secure_url=image.get("url"),
            company_id=body.company_id,
            owner_type="branch",
            owner_id=branch_id,
        )
    return await _branch_out(session, await session.get(Branch, branch_id))


@router.patch(
    "/branches/{record_id}", dependencies=[Depends(require_permission("branches.update"))]
)
async def update_branch(
    record_id: uuid.UUID,
    body: BranchIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> dict[str, Any]:
    existing = await session.get(Branch, record_id)
    if existing is None:
        raise HTTPException(404, "Sucursal no encontrada.")
    await require_company_wide_scope(session, current, existing.company_id)
    await require_company_wide_scope(session, current, body.company_id)
    if existing.company_id != body.company_id:
        raise HTTPException(409, "No se puede mover una sucursal entre empresas.")
    await _require_active(session, Company, body.company_id, "La empresa")
    await _validate_address(session, body.department_id, body.municipality_id, body.district_id)
    if body.manager_employee_id:
        manager = await session.get(Employee, body.manager_employee_id)
        if manager is None or manager.company_id != body.company_id or manager.status != "activo":
            raise HTTPException(
                409, "El encargado debe ser un empleado activo de la misma empresa."
            )
        await _ensure_branch_manager_assignment(
            session,
            employee_id=body.manager_employee_id,
            branch_id=record_id,
            company_id=body.company_id,
            user_id=_actor_id(request),
        )
    await _update(
        session,
        Branch,
        record_id,
        body.model_dump(exclude_none=True),
        user_id=_actor_id(request),
        company_id=body.company_id,
        branch_id=record_id,
    )
    retained_urls = [image.get("url") for image in body.images if image.get("url")]
    detach_query = update(MediaAsset).where(
        MediaAsset.owner_type == "branch",
        MediaAsset.owner_id == record_id,
        MediaAsset.status == "active",
    )
    if retained_urls:
        detach_query = detach_query.where(MediaAsset.secure_url.not_in(retained_urls))
    await session.execute(detach_query.values(status="detached"))
    for image in body.images:
        await attach_media_by_url(
            session,
            secure_url=image.get("url"),
            company_id=body.company_id,
            owner_type="branch",
            owner_id=record_id,
        )
    return await _branch_out(session, await session.get(Branch, record_id))


@router.post(
    "/branches/{record_id}/activate",
    dependencies=[Depends(require_permission("branches.activate"))],
)
async def activate_branch(
    record_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    branch = await session.get(Branch, record_id)
    if branch is None:
        raise HTTPException(404, "Sucursal no encontrada.")
    await require_company_wide_scope(session, current, branch.company_id)
    return await _update(
        session,
        Branch,
        record_id,
        {"is_active": True, "operational_status": "active"},
        user_id=_actor_id(request),
        company_id=branch.company_id,
        branch_id=record_id,
        action="ACTIVATE",
    )


@router.post(
    "/branches/{record_id}/deactivate",
    dependencies=[Depends(require_permission("branches.deactivate"))],
)
async def deactivate_branch(
    record_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    branch = await session.get(Branch, record_id)
    if branch is None:
        raise HTTPException(404, "Sucursal no encontrada.")
    await require_company_wide_scope(session, current, branch.company_id)
    active_warehouse = await session.scalar(
        select(Warehouse.id)
        .where(Warehouse.branch_id == record_id, Warehouse.is_active.is_(True))
        .limit(1)
    )
    active_employee = await session.scalar(
        select(EmployeeBranchAssignment.id)
        .where(
            EmployeeBranchAssignment.branch_id == record_id,
            EmployeeBranchAssignment.is_active.is_(True),
        )
        .limit(1)
    )
    if active_warehouse or active_employee:
        raise HTTPException(
            409,
            "Desactive los almacenes y finalice las asignaciones de empleados antes de desactivar la sucursal.",
        )
    return await _update(
        session,
        Branch,
        record_id,
        {"is_active": False, "operational_status": "inactive"},
        user_id=_actor_id(request),
        company_id=branch.company_id,
        branch_id=record_id,
        action="DEACTIVATE",
    )


@router.get(
    "/warehouse-categories",
    response_model=Page[dict[str, Any]],
    dependencies=[Depends(require_permission("warehouse_categories.view"))],
)
async def list_categories(
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    page: int = Query(1, ge=1),
    size: int = Query(12, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
) -> Page[dict[str, Any]]:
    await require_company_access(session, current, company_id)
    conditions = [WarehouseCategory.company_id == company_id]
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                WarehouseCategory.name.ilike(pattern),
                WarehouseCategory.description.ilike(pattern),
            )
        )
    total = int(
        (
            await session.execute(select(func.count(WarehouseCategory.id)).where(*conditions))
        ).scalar_one()
    )
    rows = list(
        (
            await session.execute(
                select(WarehouseCategory)
                .where(*conditions)
                .order_by(WarehouseCategory.name, WarehouseCategory.id)
                .offset((page - 1) * size)
                .limit(size)
            )
        ).scalars()
    )
    return Page(
        items=[_dump(item) for item in rows],
        meta=PageMeta(
            page=page,
            size=size,
            total=total,
            pages=(total + size - 1) // size if total else 1,
        ),
    )


@router.get(
    "/warehouse-categories/catalogue",
    response_model=list[dict[str, Any]],
    dependencies=[Depends(require_permission("warehouse_categories.view"))],
)
async def warehouse_category_catalogue(
    session: SessionDep, current: CurrentUser, company_id: uuid.UUID
) -> list[dict[str, Any]]:
    await require_company_access(session, current, company_id)
    rows = (
        (
            await session.execute(
                select(WarehouseCategory)
                .where(WarehouseCategory.company_id == company_id)
                .order_by(WarehouseCategory.name, WarehouseCategory.id)
            )
        )
        .scalars()
        .all()
    )
    return [_dump(item) for item in rows]


@router.post(
    "/warehouse-categories",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("warehouse_categories.create"))],
)
async def create_category(
    body: WarehouseCategoryIn, request: Request, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    await require_company_wide_scope(session, current, body.company_id)
    return await _create(
        session,
        WarehouseCategory,
        body,
        user_id=_actor_id(request),
        company_id=body.company_id,
    )


@router.patch(
    "/warehouse-categories/{record_id}",
    dependencies=[Depends(require_permission("warehouse_categories.update"))],
)
async def update_category(
    record_id: uuid.UUID,
    body: WarehouseCategoryIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> dict[str, Any]:
    existing = await session.get(WarehouseCategory, record_id)
    if existing is None:
        raise HTTPException(404, "Categoría de almacén no encontrada.")
    await require_company_wide_scope(session, current, existing.company_id)
    if existing.company_id != body.company_id:
        raise HTTPException(409, "No se puede mover una categoría entre empresas.")
    return await _update(
        session,
        WarehouseCategory,
        record_id,
        body.model_dump(exclude_none=True, exclude={"company_id"}),
        user_id=_actor_id(request),
        company_id=existing.company_id,
    )


@router.post(
    "/warehouse-categories/{record_id}/deactivate",
    dependencies=[Depends(require_permission("warehouse_categories.deactivate"))],
)
async def deactivate_category(
    record_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> dict[str, Any]:
    category = await session.get(WarehouseCategory, record_id)
    if category is None:
        raise HTTPException(404, "Categoría de almacén no encontrada.")
    await require_company_wide_scope(session, current, category.company_id)
    in_use = await session.scalar(
        select(Warehouse.id)
        .where(Warehouse.warehouse_category_id == record_id, Warehouse.is_active.is_(True))
        .limit(1)
    )
    if in_use:
        raise HTTPException(
            409, "No puede desactivar una categoría utilizada por almacenes activos."
        )
    return await _update(
        session,
        WarehouseCategory,
        record_id,
        {"is_active": False},
        user_id=_actor_id(request),
        company_id=category.company_id,
        action="DEACTIVATE",
    )


@router.post(
    "/warehouse-categories/{record_id}/activate",
    dependencies=[Depends(require_permission("warehouse_categories.activate"))],
)
async def activate_category(
    record_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> dict[str, Any]:
    category = await session.get(WarehouseCategory, record_id)
    if category is None:
        raise HTTPException(404, "Categoría de almacén no encontrada.")
    await require_company_wide_scope(session, current, category.company_id)
    return await _update(
        session,
        WarehouseCategory,
        record_id,
        {"is_active": True},
        user_id=_actor_id(request),
        company_id=category.company_id,
        action="ACTIVATE",
    )


@router.get(
    "/warehouses",
    response_model=WarehousePage,
    dependencies=[Depends(require_permission("warehouses.view"))],
)
async def list_warehouses(
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    branch_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(9, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
    status_filter: str | None = Query(
        None, alias="status", pattern="^(active|inactive|maintenance|full)$"
    ),
    sort: str = Query("capacity", pattern="^(capacity|name|movement)$"),
) -> WarehousePage:
    await resolve_branch_scope(session, current, company_id, branch_id)
    scope_conditions = [Branch.company_id == company_id]
    if branch_id is not None:
        scope_conditions.append(Warehouse.branch_id == branch_id)
    conditions = list(scope_conditions)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Warehouse.name.ilike(pattern),
                Warehouse.code.ilike(pattern),
                Warehouse.physical_location.ilike(pattern),
                Branch.name.ilike(pattern),
            )
        )
    if status_filter:
        conditions.append(Warehouse.operational_status == status_filter)

    aggregate = (
        await session.execute(
            select(
                func.count(Warehouse.id),
                func.coalesce(func.sum(Warehouse.capacity), 0),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "active"),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "full"),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "maintenance"),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "inactive"),
            )
            .select_from(Warehouse)
            .join(Branch)
            .where(*conditions)
        )
    ).one()
    total = int(aggregate[0])

    scope_counts = (
        await session.execute(
            select(
                func.count(Warehouse.id),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "active"),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "full"),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "maintenance"),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "inactive"),
            )
            .select_from(Warehouse)
            .join(Branch)
            .where(*scope_conditions)
        )
    ).one()
    branch_rows = (
        await session.execute(
            select(Branch.id, Branch.name)
            .join(Warehouse, Warehouse.branch_id == Branch.id)
            .where(*scope_conditions)
            .distinct()
            .order_by(Branch.name, Branch.id)
        )
    ).all()

    order = {
        "capacity": (func.coalesce(Warehouse.capacity, 0).desc(), Warehouse.name),
        "name": (Warehouse.name, Warehouse.id),
        "movement": (Warehouse.updated_at.desc().nullslast(), Warehouse.name),
    }[sort]
    rows = list(
        (
            await session.execute(
                select(Warehouse)
                .join(Branch)
                .where(*conditions)
                .order_by(*order)
                .offset((page - 1) * size)
                .limit(size)
            )
        ).scalars()
    )
    return WarehousePage(
        items=await _warehouses_out(session, rows),
        meta=PageMeta(
            page=page,
            size=size,
            total=total,
            pages=(total + size - 1) // size if total else 1,
        ),
        summary=WarehouseListSummary(
            total_capacity=int(aggregate[1]),
            active=int(aggregate[2]),
            full=int(aggregate[3]),
            maintenance=int(aggregate[4]),
            inactive=int(aggregate[5]),
            status_counts={
                "all": int(scope_counts[0]),
                "active": int(scope_counts[1]),
                "full": int(scope_counts[2]),
                "maintenance": int(scope_counts[3]),
                "inactive": int(scope_counts[4]),
            },
            branches=[{"id": str(item.id), "name": item.name} for item in branch_rows],
        ),
    )


@router.get(
    "/warehouses/catalogue",
    response_model=list[dict[str, Any]],
    dependencies=[Depends(require_permission("warehouses.view"))],
)
async def warehouse_catalogue(
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    branch_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    await resolve_branch_scope(session, current, company_id, branch_id)
    stmt = select(Warehouse).join(Branch).where(Branch.company_id == company_id)
    if branch_id is not None:
        stmt = stmt.where(Warehouse.branch_id == branch_id)
    rows = list((await session.execute(stmt.order_by(Warehouse.name))).scalars())
    return await _warehouses_out(session, rows)


@router.get(
    "/warehouses/{record_id}", dependencies=[Depends(require_permission("warehouses.view"))]
)
async def get_warehouse(
    record_id: uuid.UUID, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    warehouse = await session.get(Warehouse, record_id)
    if warehouse is None:
        raise HTTPException(404, "Almacén no encontrado.")
    branch = await session.get(Branch, warehouse.branch_id)
    await resolve_branch_scope(session, current, branch.company_id, branch.id)
    return await _warehouse_out(session, warehouse)


@router.post(
    "/warehouses",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("warehouses.create"))],
)
async def create_warehouse(
    body: WarehouseIn, request: Request, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    branch = await _require_active(session, Branch, body.branch_id, "La sucursal")
    await resolve_branch_scope(session, current, branch.company_id, branch.id)
    category = await _require_active(
        session,
        WarehouseCategory,
        body.warehouse_category_id,
        "La categoría de almacén",
    )
    if category.company_id != branch.company_id:
        raise HTTPException(409, "La categoría de almacén pertenece a otra empresa.")
    if body.manager_employee_id:
        manager = await session.get(Employee, body.manager_employee_id)
        assignment = await session.scalar(
            select(EmployeeBranchAssignment.id).where(
                EmployeeBranchAssignment.employee_id == body.manager_employee_id,
                EmployeeBranchAssignment.branch_id == body.branch_id,
                EmployeeBranchAssignment.is_active.is_(True),
            )
        )
        if manager is None or manager.status != "activo" or assignment is None:
            raise HTTPException(
                409, "El encargado del almacén debe ser un empleado activo asignado a la sucursal."
            )
    created = await _create(
        session,
        Warehouse,
        body,
        user_id=_actor_id(request),
        company_id=branch.company_id,
        branch_id=branch.id,
    )
    warehouse = await session.get(Warehouse, uuid.UUID(created["id"]))
    for image in body.images:
        await attach_media_by_url(
            session,
            secure_url=image.get("url"),
            company_id=branch.company_id,
            owner_type="warehouse",
            owner_id=warehouse.id,
        )
    return await _warehouse_out(session, warehouse)


@router.patch(
    "/warehouses/{record_id}", dependencies=[Depends(require_permission("warehouses.update"))]
)
async def update_warehouse(
    record_id: uuid.UUID,
    body: WarehouseIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> dict[str, Any]:
    existing = await session.get(Warehouse, record_id)
    if existing is None:
        raise HTTPException(404, "Almacén no encontrado.")
    current_branch = await session.get(Branch, existing.branch_id)
    await resolve_branch_scope(session, current, current_branch.company_id, current_branch.id)
    branch = await _require_active(session, Branch, body.branch_id, "La sucursal")
    await resolve_branch_scope(session, current, branch.company_id, branch.id)
    if current_branch.company_id != branch.company_id:
        raise HTTPException(409, "No se puede mover un almacén entre empresas.")
    if existing.branch_id != body.branch_id:
        active_location = await session.scalar(
            select(Location.id)
            .where(
                Location.warehouse_id == record_id,
                Location.is_active.is_(True),
            )
            .limit(1)
        )
        if active_location is not None:
            raise HTTPException(
                409,
                "No se puede cambiar la sucursal mientras el almacén tenga ubicaciones físicas activas.",
            )
    category = await _require_active(
        session,
        WarehouseCategory,
        body.warehouse_category_id,
        "La categoría de almacén",
    )
    if category.company_id != branch.company_id:
        raise HTTPException(409, "La categoría de almacén pertenece a otra empresa.")
    if body.manager_employee_id:
        manager = await session.get(Employee, body.manager_employee_id)
        assignment = await session.scalar(
            select(EmployeeBranchAssignment.id).where(
                EmployeeBranchAssignment.employee_id == body.manager_employee_id,
                EmployeeBranchAssignment.branch_id == body.branch_id,
                EmployeeBranchAssignment.is_active.is_(True),
            )
        )
        if manager is None or manager.status != "activo" or assignment is None:
            raise HTTPException(
                409, "El encargado del almacén debe ser un empleado activo asignado a la sucursal."
            )
    await _update(
        session,
        Warehouse,
        record_id,
        body.model_dump(),
        user_id=_actor_id(request),
        company_id=branch.company_id,
        branch_id=branch.id,
    )
    retained_urls = [image.get("url") for image in body.images if image.get("url")]
    detach_query = update(MediaAsset).where(
        MediaAsset.owner_type == "warehouse",
        MediaAsset.owner_id == record_id,
        MediaAsset.status == "active",
    )
    if retained_urls:
        detach_query = detach_query.where(MediaAsset.secure_url.not_in(retained_urls))
    await session.execute(detach_query.values(status="detached"))
    for image in body.images:
        await attach_media_by_url(
            session,
            secure_url=image.get("url"),
            company_id=branch.company_id,
            owner_type="warehouse",
            owner_id=record_id,
        )
    return await _warehouse_out(session, await session.get(Warehouse, record_id))


@router.post(
    "/warehouses/{record_id}/deactivate",
    dependencies=[Depends(require_permission("warehouses.deactivate"))],
)
async def deactivate_warehouse(
    record_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    warehouse = await session.get(Warehouse, record_id)
    if warehouse is None:
        raise HTTPException(404, "Almacén no encontrado.")
    branch = await session.get(Branch, warehouse.branch_id)
    await resolve_branch_scope(session, current, branch.company_id, branch.id)
    active_location = await session.scalar(
        select(Location.id)
        .where(Location.warehouse_id == record_id, Location.is_active.is_(True))
        .limit(1)
    )
    if active_location:
        raise HTTPException(409, "Desactive primero las ubicaciones físicas del almacén.")
    return await _update(
        session,
        Warehouse,
        record_id,
        {"is_active": False, "operational_status": "inactive"},
        user_id=_actor_id(request),
        company_id=branch.company_id,
        branch_id=branch.id,
        action="DEACTIVATE",
    )


@router.post(
    "/warehouses/{record_id}/activate",
    dependencies=[Depends(require_permission("warehouses.activate"))],
)
async def activate_warehouse(
    record_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    warehouse = await session.get(Warehouse, record_id)
    if warehouse is None:
        raise HTTPException(404, "Almacén no encontrado.")
    branch = await session.get(Branch, warehouse.branch_id)
    await resolve_branch_scope(session, current, branch.company_id, branch.id)
    return await _update(
        session,
        Warehouse,
        record_id,
        {"is_active": True, "operational_status": "active"},
        user_id=_actor_id(request),
        company_id=branch.company_id,
        branch_id=branch.id,
        action="ACTIVATE",
    )


@router.get("/locations", dependencies=[Depends(require_permission("locations.view"))])
async def list_locations(
    session: SessionDep, current: CurrentUser, warehouse_id: uuid.UUID
) -> list[dict[str, Any]]:
    warehouse = await session.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(404, "Almacén no encontrado.")
    branch = await session.get(Branch, warehouse.branch_id)
    await resolve_branch_scope(session, current, branch.company_id, branch.id)
    stmt = select(Location).where(Location.warehouse_id == warehouse_id)
    return [
        _dump(item)
        for item in (await session.execute(stmt.order_by(Location.code))).scalars().all()
    ]


@router.post(
    "/locations",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("locations.create"))],
)
async def create_location(
    body: LocationIn, request: Request, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    warehouse = await _require_active(session, Warehouse, body.warehouse_id, "El almacén")
    branch = await session.get(Branch, warehouse.branch_id)
    await resolve_branch_scope(session, current, branch.company_id, branch.id)
    current_capacity = await session.scalar(
        select(func.coalesce(func.sum(Location.capacity), 0)).where(
            Location.warehouse_id == body.warehouse_id, Location.is_active.is_(True)
        )
    )
    if warehouse.capacity and int(current_capacity or 0) + body.capacity > warehouse.capacity:
        raise HTTPException(
            409, "La capacidad acumulada de las ubicaciones supera la capacidad del almacén."
        )
    return await _create(
        session,
        Location,
        body,
        user_id=_actor_id(request),
        company_id=branch.company_id,
        branch_id=branch.id,
    )


@router.patch(
    "/locations/{record_id}", dependencies=[Depends(require_permission("locations.update"))]
)
async def update_location(
    record_id: uuid.UUID,
    body: LocationIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> dict[str, Any]:
    existing = await session.get(Location, record_id)
    if existing is None:
        raise HTTPException(404, "Ubicación no encontrada.")
    current_warehouse = await session.get(Warehouse, existing.warehouse_id)
    current_branch = await session.get(Branch, current_warehouse.branch_id)
    await resolve_branch_scope(session, current, current_branch.company_id, current_branch.id)
    warehouse = await _require_active(session, Warehouse, body.warehouse_id, "El almacén")
    branch = await session.get(Branch, warehouse.branch_id)
    await resolve_branch_scope(session, current, branch.company_id, branch.id)
    if current_branch.company_id != branch.company_id:
        raise HTTPException(409, "No se puede mover una ubicación entre empresas.")
    current_capacity = await session.scalar(
        select(func.coalesce(func.sum(Location.capacity), 0)).where(
            Location.warehouse_id == body.warehouse_id,
            Location.is_active.is_(True),
            Location.id != record_id,
        )
    )
    if warehouse.capacity and int(current_capacity or 0) + body.capacity > warehouse.capacity:
        raise HTTPException(
            409, "La capacidad acumulada de las ubicaciones supera la capacidad del almacén."
        )
    return await _update(
        session,
        Location,
        record_id,
        body.model_dump(exclude_none=True),
        user_id=_actor_id(request),
        company_id=branch.company_id,
        branch_id=branch.id,
    )


@router.post(
    "/locations/{record_id}/deactivate",
    dependencies=[Depends(require_permission("locations.deactivate"))],
)
async def deactivate_location(
    record_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> dict[str, Any]:
    location = await session.get(Location, record_id)
    if location is None:
        raise HTTPException(404, "Ubicación no encontrada.")
    warehouse = await session.get(Warehouse, location.warehouse_id)
    branch = await session.get(Branch, warehouse.branch_id)
    await resolve_branch_scope(session, current, branch.company_id, branch.id)
    return await _update(
        session,
        Location,
        record_id,
        {"is_active": False},
        user_id=_actor_id(request),
        company_id=branch.company_id,
        branch_id=branch.id,
        action="DEACTIVATE",
    )


@router.post(
    "/locations/{record_id}/activate",
    dependencies=[Depends(require_permission("locations.activate"))],
)
async def activate_location(
    record_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> dict[str, Any]:
    location = await session.get(Location, record_id)
    if location is None:
        raise HTTPException(404, "Ubicación no encontrada.")
    warehouse = await session.get(Warehouse, location.warehouse_id)
    branch = await session.get(Branch, warehouse.branch_id)
    await resolve_branch_scope(session, current, branch.company_id, branch.id)
    if not warehouse.is_active:
        raise HTTPException(409, "No se puede activar una ubicación de un almacén inactivo.")
    current_capacity = await session.scalar(
        select(func.coalesce(func.sum(Location.capacity), 0)).where(
            Location.warehouse_id == location.warehouse_id,
            Location.is_active.is_(True),
            Location.id != record_id,
        )
    )
    if warehouse.capacity and int(current_capacity or 0) + location.capacity > warehouse.capacity:
        raise HTTPException(
            409, "La capacidad acumulada de las ubicaciones supera la capacidad del almacén."
        )
    return await _update(
        session,
        Location,
        record_id,
        {"is_active": True},
        user_id=_actor_id(request),
        company_id=branch.company_id,
        branch_id=branch.id,
        action="ACTIVATE",
    )
