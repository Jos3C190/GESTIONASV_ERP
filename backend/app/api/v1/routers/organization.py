"""Company, branch and warehouse maintenance endpoints."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.company_access import (
    assigned_warehouse_ids,
    authorize_warehouse_assignment,
    effective_company_id,
    get_branch_context,
    require_company_access,
    require_company_wide_scope,
    require_resource_company,
    resolve_branch_scope,
)
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_check_permission_use_case,
    require_permission,
)
from app.api.v1.schemas.capacity import CapacityConfigurationDiagnosticsOut
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.location import LocationOut
from app.api.v1.schemas.organization import (
    BranchIn,
    CompanyIn,
    LocationIn,
    WarehouseCapacityGroupIn,
    WarehouseCapacityGroupOut,
    WarehouseCategoryIn,
    WarehouseIn,
    WarehouseListSummary,
    WarehousePage,
)
from app.application.locations.use_cases import LocationUseCases
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import AuthorizationError
from app.domain.entities.warehouse_capacity import occupancy_without_inventory
from app.infrastructure.document_categories import ensure_default_document_categories
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
    WarehouseCapacityGroup,
    WarehouseCategory,
)
from app.infrastructure.repositories.capacity_hierarchy_repository import (
    SqlAlchemyCapacityHierarchyRepository,
)
from app.infrastructure.repositories.location_repository import SqlAlchemyLocationRepository

router = APIRouter(tags=["organization"])


async def _capacity_group_location_counts(
    session: AsyncSession,
    warehouse_id: uuid.UUID,
    groups: Sequence[WarehouseCapacityGroup],
) -> dict[uuid.UUID, dict[str, int]]:
    """Return direct and inclusive subtree location counts in two DB queries."""

    if not groups:
        return {}
    direct_rows = (
        await session.execute(
            select(Location.capacity_group_id, func.count(Location.id))
            .where(
                Location.warehouse_id == warehouse_id,
                Location.deleted_at.is_(None),
                Location.capacity_group_id.is_not(None),
            )
            .group_by(Location.capacity_group_id)
        )
    ).all()
    direct = {group_id: int(count) for group_id, count in direct_rows if group_id is not None}
    children: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    known_ids = {group.id for group in groups}
    for group in groups:
        if group.parent_id is not None and group.parent_id in known_ids:
            children[group.parent_id].append(group.id)

    memo: dict[uuid.UUID, int] = {}

    def subtree_count(group_id: uuid.UUID, visiting: frozenset[uuid.UUID] = frozenset()) -> int:
        if group_id in memo:
            return memo[group_id]
        if group_id in visiting:
            return direct.get(group_id, 0)
        total = direct.get(group_id, 0)
        next_visiting = visiting | {group_id}
        for child_id in children.get(group_id, []):
            total += subtree_count(child_id, next_visiting)
        memo[group_id] = total
        return total

    return {
        group.id: {
            "direct_location_count": direct.get(group.id, 0),
            "subtree_location_count": subtree_count(group.id),
        }
        for group in groups
    }


def _capacity_group_response(
    group: WarehouseCapacityGroup,
    counts: Mapping[uuid.UUID, Mapping[str, int]],
) -> WarehouseCapacityGroupOut:
    return WarehouseCapacityGroupOut.model_validate(group).model_copy(
        update=dict(counts.get(group.id, {}))
    )


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
    user_id = getattr(user, "id", None)
    if not isinstance(user_id, uuid.UUID):
        raise HTTPException(status_code=401, detail="No autenticado.")
    return user_id


async def _branch_or_404(session: AsyncSession, branch_id: uuid.UUID) -> Branch:
    branch = await session.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(404, "Sucursal no encontrada.")
    return branch


async def _warehouse_or_404(session: AsyncSession, warehouse_id: uuid.UUID) -> Warehouse:
    warehouse = await session.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(404, "Almacén no encontrado.")
    return warehouse


async def _authorize_warehouse_scope(
    session: AsyncSession,
    current: CurrentUser,
    request: Request,
    warehouse: Warehouse,
) -> uuid.UUID:
    company_id = require_resource_company(
        request, warehouse.company_id, not_found_detail="Almacén no encontrado."
    )
    await resolve_branch_scope(session, current, company_id, warehouse.branch_id)
    await authorize_warehouse_assignment(session, current, company_id, warehouse.id)
    return company_id


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


async def _prepare_branch_input(
    session: AsyncSession,
    body: BranchIn,
    *,
    existing: Branch | None = None,
) -> BranchIn:
    """Resolve the minimum administrative headquarters profile from its company."""
    company = await session.scalar(
        select(Company).where(Company.id == body.company_id).with_for_update()
    )
    if company is None or not company.is_active:
        raise HTTPException(422, "La empresa no existe o está inactiva.")

    if body.is_headquarters:
        return await _prepare_headquarters_input(session, body, company, existing=existing)

    if body.department_id is None or body.municipality_id is None or body.district_id is None:
        raise HTTPException(422, "La dirección y ubicación geográfica son obligatorias.")
    if body.address is None:
        raise HTTPException(422, "La dirección y ubicación geográfica son obligatorias.")
    if body.latitude is None or body.longitude is None:
        raise HTTPException(422, "Las coordenadas son obligatorias para una sucursal operativa.")
    await _validate_address(session, body.department_id, body.municipality_id, body.district_id)
    return body


async def _prepare_headquarters_input(
    session: AsyncSession,
    body: BranchIn,
    company: Company,
    *,
    existing: Branch | None,
) -> BranchIn:
    active_headquarters = select(Branch.id).where(
        Branch.company_id == body.company_id,
        Branch.is_headquarters.is_(True),
        Branch.is_active.is_(True),
        Branch.operational_status == "active",
        Branch.deleted_at.is_(None),
    )
    if existing is not None:
        active_headquarters = active_headquarters.where(Branch.id != existing.id)
    if await session.scalar(active_headquarters.limit(1)) is not None:
        raise HTTPException(409, "La empresa ya tiene una matriz activa.")

    address_values = _headquarters_address_values(body, company, existing)
    await _validate_address(
        session,
        address_values["department_id"],
        address_values["municipality_id"],
        address_values["district_id"],
    )
    code = await _headquarters_code(session, body, existing)
    return body.model_copy(
        update={
            **address_values,
            "code": code,
            "description": body.description or "Recepción y distribución.",
        }
    )


def _headquarters_address_values(
    body: BranchIn, company: Company, existing: Branch | None
) -> dict[str, Any]:
    supplied = (body.address, body.department_id, body.municipality_id, body.district_id)
    if all(value is None for value in supplied):
        return {
            "address": existing.address if existing else company.address,
            "department_id": existing.department_id if existing else company.department_id,
            "municipality_id": existing.municipality_id if existing else company.municipality_id,
            "district_id": existing.district_id if existing else company.district_id,
        }
    if any(value is None for value in supplied):
        raise HTTPException(
            422,
            "Para la matriz, complete la dirección y las tres referencias geográficas, "
            "o déjelas vacías para usar el domicilio de la empresa.",
        )
    return {
        "address": body.address,
        "department_id": body.department_id,
        "municipality_id": body.municipality_id,
        "district_id": body.district_id,
    }


async def _headquarters_code(session: AsyncSession, body: BranchIn, existing: Branch | None) -> str:
    code = body.code or (existing.code if existing else None)
    if code:
        return code
    prefix = f"HQ-{body.company_id.hex[:8]}".upper()
    code = prefix
    suffix = 2
    while await session.scalar(
        select(Branch.id).where(
            Branch.company_id == body.company_id,
            func.lower(Branch.code) == code.casefold(),
            Branch.deleted_at.is_(None),
        )
    ):
        code = f"{prefix[:29]}-{suffix}"
        suffix += 1
    return code


async def _require_active(
    session: AsyncSession, cls: type[Any], record_id: uuid.UUID, label: str
) -> Any:
    obj = await session.get(cls, record_id)
    if obj is None:
        raise HTTPException(status_code=422, detail=f"{label} no existe.")
    if not obj.is_active:
        raise HTTPException(status_code=422, detail=f"{label} está inactivo.")
    return obj


async def _validate_capacity_group_parent(
    session: AsyncSession,
    *,
    warehouse_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    group_id: uuid.UUID | None = None,
) -> None:
    """Validate one hierarchy while the caller holds the warehouse row lock."""

    current_id = parent_id
    visited: set[uuid.UUID] = set()
    while current_id is not None:
        if current_id == group_id or current_id in visited:
            raise HTTPException(409, "El grupo de capacidad formaría un ciclo jerárquico.")
        visited.add(current_id)
        parent = await session.scalar(
            select(WarehouseCapacityGroup)
            .where(
                WarehouseCapacityGroup.id == current_id,
                WarehouseCapacityGroup.warehouse_id == warehouse_id,
                WarehouseCapacityGroup.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if parent is None or not parent.is_active:
            raise HTTPException(409, "El grupo padre no pertenece al almacén o no está activo.")
        current_id = parent.parent_id


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
    warehouse_count_rows = (
        await session.execute(
            select(Warehouse.branch_id, func.count(Warehouse.id))
            .where(
                Warehouse.branch_id.in_(branch_ids),
                Warehouse.is_transit.is_(False),
            )
            .group_by(Warehouse.branch_id)
        )
    ).all()
    warehouse_counts: dict[uuid.UUID, int] = {
        branch_id: int(count) for branch_id, count in warehouse_count_rows if branch_id is not None
    }
    employee_count_rows = (
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
    employee_counts: dict[uuid.UUID, int] = {
        branch_id: int(count) for branch_id, count in employee_count_rows if branch_id is not None
    }
    output: list[dict[str, Any]] = []
    for branch in branches:
        data = _dump(branch)
        district = districts.get(branch.district_id)
        manager = (
            managers.get(branch.manager_employee_id)
            if branch.manager_employee_id is not None
            else None
        )
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
    branch_ids = {
        warehouse.branch_id for warehouse in warehouses if warehouse.branch_id is not None
    }
    manager_ids = {
        warehouse.manager_employee_id
        for warehouse in warehouses
        if warehouse.manager_employee_id is not None
    }
    branches = (
        {
            item.id: item
            for item in (
                await session.execute(select(Branch).where(Branch.id.in_(branch_ids)))
            ).scalars()
        }
        if branch_ids
        else {}
    )
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
    output: list[dict[str, Any]] = []
    for warehouse in warehouses:
        data = _dump(warehouse)
        branch = branches.get(warehouse.branch_id)
        manager = (
            managers.get(warehouse.manager_employee_id)
            if warehouse.manager_employee_id is not None
            else None
        )
        data.update(
            {
                "branch_id": str(warehouse.branch_id) if warehouse.branch_id is not None else None,
                "type": warehouse.warehouse_type,
                "status": warehouse.operational_status,
                "location": warehouse.physical_location or "",
                "branch_name": branch.name if branch else "Sucursal asociada no encontrada",
                "branch_address": branch.address if branch else "",
                "manager": f"{manager.first_name} {manager.last_name}"
                if manager
                else "Sin responsable",
                "manager_initials": f"{manager.first_name[:1]}{manager.last_name[:1]}"
                if manager
                else "—",
                "used": None,
                "products": None,
                "operators": 0,
                "total_skus": 0,
                "top_categories": [],
                "low_stock_items": 0,
                "expiring_items": 0,
                "inventory_value": 0,
                "inventory_turnover": 0,
                "last_movement": "Consulte el módulo de inventario",
                "inbound_this_month": 0,
                "outbound_this_month": 0,
                "daily_movements_avg": 0,
                "trend": [],
                "recent_movements": [],
                "top_products": [],
                "shelves_occupied": None,
            }
        )
        data.update(occupancy_without_inventory(warehouse))
        output.append(data)
    return output


async def _warehouse_out(session: AsyncSession, warehouse: Warehouse) -> dict[str, Any]:
    return (await _warehouses_out(session, [warehouse]))[0]


async def _validate_warehouse_relations(
    session: AsyncSession,
    current: CurrentUser,
    body: WarehouseIn,
    company_id: uuid.UUID,
    *,
    branch_company_error: str,
    branch_company_status_code: int = 409,
    exclude_warehouse_id: uuid.UUID | None = None,
    warehouse_is_active: bool = True,
) -> Branch | None:
    branch = await _validate_warehouse_branch(
        session,
        current,
        body,
        company_id,
        branch_company_error=branch_company_error,
        branch_company_status_code=branch_company_status_code,
    )
    await _validate_central_warehouse(
        session,
        body,
        branch,
        company_id,
        exclude_warehouse_id=exclude_warehouse_id,
        warehouse_is_active=warehouse_is_active,
    )

    category = await _require_active(
        session,
        WarehouseCategory,
        body.warehouse_category_id,
        "La categoría de almacén",
    )
    if category.company_id != company_id:
        raise HTTPException(409, "La categoría de almacén pertenece a otra empresa.")

    if body.manager_employee_id and branch is not None:
        manager = await session.get(Employee, body.manager_employee_id)
        assignment = await session.scalar(
            select(EmployeeBranchAssignment.id).where(
                EmployeeBranchAssignment.employee_id == body.manager_employee_id,
                EmployeeBranchAssignment.branch_id == branch.id,
                EmployeeBranchAssignment.is_active.is_(True),
            )
        )
        if manager is None or manager.status != "activo" or assignment is None:
            raise HTTPException(
                409, "El encargado del almacén debe ser un empleado activo asignado a la sucursal."
            )
    return branch


async def _validate_warehouse_branch(
    session: AsyncSession,
    current: CurrentUser,
    body: WarehouseIn,
    company_id: uuid.UUID,
    *,
    branch_company_error: str,
    branch_company_status_code: int,
) -> Branch:
    if body.branch_id is None:
        raise HTTPException(422, "Todo almacén debe pertenecer a una sucursal.")
    branch = await _require_active(session, Branch, body.branch_id, "La sucursal")
    if branch.company_id != company_id:
        raise HTTPException(branch_company_status_code, branch_company_error)
    if branch.operational_status != "active":
        raise HTTPException(409, "La sucursal seleccionada no está activa.")
    await resolve_branch_scope(session, current, company_id, branch.id)
    return branch


async def _validate_central_warehouse(
    session: AsyncSession,
    body: WarehouseIn,
    branch: Branch,
    company_id: uuid.UUID,
    *,
    exclude_warehouse_id: uuid.UUID | None,
    warehouse_is_active: bool,
) -> None:
    if not body.is_central:
        return
    if not branch.is_headquarters:
        raise HTTPException(422, "La bodega central debe pertenecer a la matriz de la empresa.")
    if not warehouse_is_active or body.operational_status != "active":
        return
    await session.scalar(select(Company.id).where(Company.id == company_id).with_for_update())
    active_mother = select(Warehouse.id).where(
        Warehouse.company_id == company_id,
        Warehouse.is_central.is_(True),
        Warehouse.is_active.is_(True),
        Warehouse.operational_status == "active",
        Warehouse.deleted_at.is_(None),
    )
    if exclude_warehouse_id is not None:
        active_mother = active_mother.where(Warehouse.id != exclude_warehouse_id)
    if await session.scalar(active_mother.limit(1)) is not None:
        raise HTTPException(
            409,
            "La empresa ya tiene una bodega central activa. Edite esa bodega para conservar una sola.",
        )


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
    await ensure_default_document_categories(session, company_id, _actor_id(request))
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
    body = await _prepare_branch_input(session, body)
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
    return await _branch_out(session, await _branch_or_404(session, branch_id))


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
    body = await _prepare_branch_input(session, body, existing=existing)
    if existing.is_headquarters and not body.is_headquarters:
        central_warehouse = await session.scalar(
            select(Warehouse.id)
            .where(
                Warehouse.company_id == existing.company_id,
                Warehouse.branch_id == existing.id,
                Warehouse.is_central.is_(True),
            )
            .limit(1)
        )
        if central_warehouse is not None:
            raise HTTPException(
                409,
                "No se puede quitar la identificación de matriz mientras tenga la bodega central asociada.",
            )
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
    return await _branch_out(session, await _branch_or_404(session, record_id))


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
    if branch.is_headquarters:
        central_warehouse = await session.scalar(
            select(Warehouse.id)
            .where(
                Warehouse.company_id == branch.company_id,
                Warehouse.branch_id == branch.id,
                Warehouse.is_central.is_(True),
            )
            .limit(1)
        )
        if central_warehouse is not None:
            raise HTTPException(
                409,
                "No se puede desactivar la matriz mientras tenga la bodega central asociada.",
            )
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
        None, alias="status", pattern="^(active|inactive|maintenance)$"
    ),
    sort: str = Query("capacity", pattern="^(capacity|weight|volume|name|movement)$"),
) -> WarehousePage:
    await resolve_branch_scope(session, current, company_id, branch_id)
    scope_conditions = [
        Warehouse.company_id == company_id,
        Warehouse.is_transit.is_(False),
    ]
    assigned = await assigned_warehouse_ids(session, current, company_id)
    if assigned is not None:
        scope_conditions.append(Warehouse.id.in_(assigned))
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

    complete_capacity = (
        Warehouse.storage_eligible.is_(True)
        & Warehouse.certified_max_weight_kg.is_not(None)
        & Warehouse.operational_max_weight_kg.is_not(None)
        & Warehouse.certified_usable_volume_m3.is_not(None)
        & Warehouse.operational_usable_volume_m3.is_not(None)
    )
    any_capacity = Warehouse.storage_eligible.is_(True) & or_(
        Warehouse.certified_max_weight_kg.is_not(None),
        Warehouse.operational_max_weight_kg.is_not(None),
        Warehouse.certified_usable_volume_m3.is_not(None),
        Warehouse.operational_usable_volume_m3.is_not(None),
    )
    aggregate = (
        await session.execute(
            select(
                func.count(Warehouse.id),
                func.coalesce(func.sum(Warehouse.certified_max_weight_kg), 0),
                func.coalesce(func.sum(Warehouse.operational_max_weight_kg), 0),
                func.coalesce(func.sum(Warehouse.certified_usable_volume_m3), 0),
                func.coalesce(func.sum(Warehouse.operational_usable_volume_m3), 0),
                func.count(Warehouse.id).filter(Warehouse.storage_eligible.is_(True)),
                func.count(Warehouse.id).filter(complete_capacity),
                func.count(Warehouse.id).filter(any_capacity & ~complete_capacity),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "active"),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "maintenance"),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "inactive"),
            )
            .select_from(Warehouse)
            .outerjoin(Branch, Branch.id == Warehouse.branch_id)
            .where(*conditions)
        )
    ).one()
    total = int(aggregate[0])

    scope_counts = (
        await session.execute(
            select(
                func.count(Warehouse.id),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "active"),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "maintenance"),
                func.count(Warehouse.id).filter(Warehouse.operational_status == "inactive"),
            )
            .select_from(Warehouse)
            .outerjoin(Branch, Branch.id == Warehouse.branch_id)
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
        "capacity": (
            func.coalesce(Warehouse.operational_max_weight_kg, 0).desc(),
            func.coalesce(Warehouse.operational_usable_volume_m3, 0).desc(),
            Warehouse.name,
        ),
        "weight": (
            func.coalesce(Warehouse.operational_max_weight_kg, 0).desc(),
            Warehouse.name,
        ),
        "volume": (
            func.coalesce(Warehouse.operational_usable_volume_m3, 0).desc(),
            Warehouse.name,
        ),
        "name": (Warehouse.name, Warehouse.id),
        "movement": (Warehouse.updated_at.desc().nullslast(), Warehouse.name),
    }[sort]
    rows = list(
        (
            await session.execute(
                select(Warehouse)
                .outerjoin(Branch, Branch.id == Warehouse.branch_id)
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
            total_certified_max_weight_kg=aggregate[1],
            total_operational_max_weight_kg=aggregate[2],
            total_certified_usable_volume_m3=aggregate[3],
            total_operational_usable_volume_m3=aggregate[4],
            storage_eligible=int(aggregate[5]),
            capacity_configured=int(aggregate[6]),
            capacity_incomplete=int(aggregate[7]),
            active=int(aggregate[8]),
            maintenance=int(aggregate[9]),
            inactive=int(aggregate[10]),
            status_counts={
                "all": int(scope_counts[0]),
                "active": int(scope_counts[1]),
                "maintenance": int(scope_counts[2]),
                "inactive": int(scope_counts[3]),
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
    include_company_central: bool = False,
) -> list[dict[str, Any]]:
    context = await resolve_branch_scope(session, current, company_id, branch_id)
    stmt = select(Warehouse).where(
        Warehouse.company_id == company_id,
        Warehouse.is_transit.is_(False),
        Warehouse.deleted_at.is_(None),
    )
    if branch_id is not None:
        if include_company_central:
            headquarters_id = await session.scalar(
                select(Branch.id).where(
                    Branch.company_id == company_id,
                    Branch.is_headquarters.is_(True),
                    Branch.is_active.is_(True),
                    Branch.operational_status == "active",
                    Branch.deleted_at.is_(None),
                )
            )
            include_authorized_central = bool(
                headquarters_id is not None
                and (context.access_all_branches or context.can_access(headquarters_id))
            )
            scope_filter = Warehouse.branch_id == branch_id
            if include_authorized_central:
                scope_filter = or_(
                    scope_filter,
                    and_(
                        Warehouse.is_central.is_(True),
                        Warehouse.branch_id == headquarters_id,
                    ),
                )
            stmt = stmt.where(scope_filter)
        else:
            stmt = stmt.where(Warehouse.branch_id == branch_id)
    rows = list((await session.execute(stmt.order_by(Warehouse.name))).scalars())
    return await _warehouses_out(session, rows)


@router.get(
    "/warehouses/{warehouse_id}/capacity-groups",
    response_model=list[WarehouseCapacityGroupOut],
    dependencies=[Depends(require_permission("warehouses.view"))],
)
async def list_warehouse_capacity_groups(
    warehouse_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> list[WarehouseCapacityGroupOut]:
    warehouse = await session.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(404, "Almacén no encontrado.")
    await _authorize_warehouse_scope(session, current, request, warehouse)
    rows = list(
        (
            await session.execute(
                select(WarehouseCapacityGroup)
                .where(
                    WarehouseCapacityGroup.warehouse_id == warehouse_id,
                    WarehouseCapacityGroup.deleted_at.is_(None),
                )
                .order_by(
                    WarehouseCapacityGroup.parent_id.asc().nulls_first(),
                    WarehouseCapacityGroup.code.asc(),
                    WarehouseCapacityGroup.id.asc(),
                )
            )
        ).scalars()
    )
    counts = await _capacity_group_location_counts(session, warehouse_id, rows)
    return [_capacity_group_response(row, counts) for row in rows]


@router.get(
    "/warehouses/{warehouse_id}/capacity-configuration-diagnostics",
    response_model=CapacityConfigurationDiagnosticsOut,
    dependencies=[Depends(require_permission("warehouses.view"))],
)
async def warehouse_capacity_configuration_diagnostics(
    warehouse_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> CapacityConfigurationDiagnosticsOut:
    warehouse = await session.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(404, "Almacén no encontrado.")
    await _authorize_warehouse_scope(session, current, request, warehouse)
    result = await SqlAlchemyCapacityHierarchyRepository(session).diagnostics(warehouse_id)
    return CapacityConfigurationDiagnosticsOut.model_validate(result)


@router.post(
    "/warehouses/{warehouse_id}/capacity-groups",
    response_model=WarehouseCapacityGroupOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("warehouses.update"))],
)
async def create_warehouse_capacity_group(
    warehouse_id: uuid.UUID,
    body: WarehouseCapacityGroupIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> WarehouseCapacityGroupOut:
    warehouse = await session.scalar(
        select(Warehouse).where(Warehouse.id == warehouse_id).with_for_update()
    )
    if warehouse is None:
        raise HTTPException(404, "Almacén no encontrado.")
    company_id = await _authorize_warehouse_scope(session, current, request, warehouse)
    await _validate_capacity_group_parent(
        session,
        warehouse_id=warehouse_id,
        parent_id=body.parent_id,
    )
    await SqlAlchemyCapacityHierarchyRepository(session).validate_group_write(
        warehouse_id, body.model_dump()
    )
    group = WarehouseCapacityGroup(warehouse_id=warehouse_id, **body.model_dump())
    try:
        async with session.begin_nested():
            session.add(group)
            await session.flush()
            session.add(
                AuditLog(
                    action="CREATE",
                    user_id=_actor_id(request),
                    company_id=company_id,
                    branch_id=warehouse.branch_id,
                    resource_type="warehouse_capacity_groups",
                    resource_id=str(group.id),
                    after_state=_dump(group),
                )
            )
            await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            409, "El código del grupo ya existe o su jerarquía no es válida."
        ) from exc
    counts = await _capacity_group_location_counts(session, warehouse_id, [group])
    return _capacity_group_response(group, counts)


@router.patch(
    "/warehouses/{warehouse_id}/capacity-groups/{group_id}",
    response_model=WarehouseCapacityGroupOut,
    dependencies=[Depends(require_permission("warehouses.update"))],
)
async def update_warehouse_capacity_group(
    warehouse_id: uuid.UUID,
    group_id: uuid.UUID,
    body: WarehouseCapacityGroupIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
) -> WarehouseCapacityGroupOut:
    warehouse = await session.scalar(
        select(Warehouse).where(Warehouse.id == warehouse_id).with_for_update()
    )
    group = await session.scalar(
        select(WarehouseCapacityGroup)
        .where(
            WarehouseCapacityGroup.id == group_id,
            WarehouseCapacityGroup.warehouse_id == warehouse_id,
            WarehouseCapacityGroup.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if warehouse is None or group is None:
        raise HTTPException(404, "Grupo de capacidad no encontrado.")
    company_id = await _authorize_warehouse_scope(session, current, request, warehouse)
    await _validate_capacity_group_parent(
        session,
        warehouse_id=warehouse_id,
        parent_id=body.parent_id,
        group_id=group_id,
    )
    await SqlAlchemyCapacityHierarchyRepository(session).validate_group_write(
        warehouse_id, body.model_dump(), group_id=group_id
    )
    before = _dump(group)
    for key, value in body.model_dump().items():
        setattr(group, key, value)
    try:
        async with session.begin_nested():
            await session.flush()
            session.add(
                AuditLog(
                    action="UPDATE",
                    user_id=_actor_id(request),
                    company_id=company_id,
                    branch_id=warehouse.branch_id,
                    resource_type="warehouse_capacity_groups",
                    resource_id=str(group.id),
                    before_state=before,
                    after_state=_dump(group),
                )
            )
            await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            409, "El código del grupo ya existe o su jerarquía no es válida."
        ) from exc
    all_groups = list(
        (
            await session.execute(
                select(WarehouseCapacityGroup).where(
                    WarehouseCapacityGroup.warehouse_id == warehouse_id,
                    WarehouseCapacityGroup.deleted_at.is_(None),
                )
            )
        ).scalars()
    )
    counts = await _capacity_group_location_counts(session, warehouse_id, all_groups)
    return _capacity_group_response(group, counts)


@router.get(
    "/warehouses/{record_id}", dependencies=[Depends(require_permission("warehouses.view"))]
)
async def get_warehouse(
    record_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    warehouse = await session.get(Warehouse, record_id)
    if warehouse is None:
        raise HTTPException(404, "Almacén no encontrado.")
    await _authorize_warehouse_scope(session, current, request, warehouse)
    return await _warehouse_out(session, warehouse)


@router.post(
    "/warehouses",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("warehouses.create"))],
)
async def create_warehouse(
    body: WarehouseIn, request: Request, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    company_id = effective_company_id(request)
    if body.company_id is not None and body.company_id != company_id:
        raise HTTPException(404, "Empresa no encontrada.")
    branch = await _validate_warehouse_relations(
        session,
        current,
        body,
        company_id,
        branch_company_error="Sucursal no encontrada.",
        branch_company_status_code=404,
    )
    created = await _create(
        session,
        Warehouse,
        body.model_copy(update={"company_id": company_id}),
        user_id=_actor_id(request),
        company_id=company_id,
        branch_id=branch.id if branch else None,
    )
    warehouse = await _warehouse_or_404(session, uuid.UUID(created["id"]))
    for image in body.images:
        await attach_media_by_url(
            session,
            secure_url=image.get("url"),
            company_id=company_id,
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
    existing = await session.scalar(
        select(Warehouse).where(Warehouse.id == record_id).with_for_update()
    )
    if existing is None:
        raise HTTPException(404, "Almacén no encontrado.")
    company_id = await _authorize_warehouse_scope(session, current, request, existing)
    if body.company_id is not None and body.company_id != company_id:
        raise HTTPException(404, "Empresa no encontrada.")
    branch = await _validate_warehouse_relations(
        session,
        current,
        body,
        company_id,
        branch_company_error="No se puede mover un almacén entre empresas.",
        exclude_warehouse_id=record_id,
        warehouse_is_active=existing.is_active,
    )
    if existing.branch_id != body.branch_id:
        active_location = await session.scalar(
            select(Location.id)
            .where(
                Location.warehouse_id == record_id,
                Location.is_active.is_(True),
                Location.deleted_at.is_(None),
            )
            .limit(1)
        )
        if active_location is not None:
            raise HTTPException(
                409,
                "No se puede cambiar la sucursal mientras el almacén tenga ubicaciones físicas activas.",
            )
    await SqlAlchemyCapacityHierarchyRepository(session).validate_warehouse_update(
        record_id, body.model_dump()
    )
    await _update(
        session,
        Warehouse,
        record_id,
        body.model_dump() | {"company_id": company_id},
        user_id=_actor_id(request),
        company_id=company_id,
        branch_id=branch.id if branch else None,
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
            company_id=company_id,
            owner_type="warehouse",
            owner_id=record_id,
        )
    return await _warehouse_out(session, await _warehouse_or_404(session, record_id))


@router.post(
    "/warehouses/{record_id}/deactivate",
    dependencies=[Depends(require_permission("warehouses.deactivate"))],
)
async def deactivate_warehouse(
    record_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser
) -> dict[str, Any]:
    warehouse = await session.scalar(
        select(Warehouse).where(Warehouse.id == record_id).with_for_update()
    )
    if warehouse is None:
        raise HTTPException(404, "Almacén no encontrado.")
    company_id = await _authorize_warehouse_scope(session, current, request, warehouse)
    active_location = await session.scalar(
        select(Location.id)
        .where(
            Location.warehouse_id == record_id,
            Location.is_active.is_(True),
            Location.deleted_at.is_(None),
        )
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
        company_id=company_id,
        branch_id=warehouse.branch_id,
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
    company_id = await _authorize_warehouse_scope(session, current, request, warehouse)
    return await _update(
        session,
        Warehouse,
        record_id,
        {"is_active": True, "operational_status": "active"},
        user_id=_actor_id(request),
        company_id=company_id,
        branch_id=warehouse.branch_id,
        action="ACTIVATE",
    )


@router.get("/locations", dependencies=[Depends(require_permission("locations.view"))])
async def list_locations(
    request: Request, session: SessionDep, current: CurrentUser, warehouse_id: uuid.UUID
) -> list[dict[str, Any]]:
    warehouse = await session.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(404, "Almacén no encontrado.")
    await _authorize_warehouse_scope(session, current, request, warehouse)
    stmt = select(Location).where(
        Location.warehouse_id == warehouse_id, Location.deleted_at.is_(None)
    )
    return [
        {**_dump(item), "capacity_status": item.capacity_status}
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
    await _authorize_warehouse_scope(session, current, request, warehouse)
    record = await LocationUseCases(SqlAlchemyLocationRepository(session)).create_location(
        body.warehouse_id,
        body.model_dump(exclude={"warehouse_id", "code"}),
        actor_id=_actor_id(request),
    )
    return LocationOut.model_validate(record).model_dump(mode="json", exclude_none=True)


@router.patch(
    "/locations/{record_id}", dependencies=[Depends(require_permission("locations.update"))]
)
async def update_location(
    record_id: uuid.UUID,
    body: LocationIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
) -> dict[str, Any]:
    existing = await session.get(Location, record_id)
    if existing is None:
        raise HTTPException(404, "Ubicación no encontrada.")
    current_warehouse = await _warehouse_or_404(session, existing.warehouse_id)
    company_id = await _authorize_warehouse_scope(session, current, request, current_warehouse)
    if body.warehouse_id != existing.warehouse_id:
        raise HTTPException(409, "No se puede mover una ubicación entre almacenes.")
    location_values = {
        "area": existing.area,
        "aisle": body.aisle,
        "rack": body.rack,
        "level": body.level,
        "position": body.position,
        "capacity_group_id": body.capacity_group_id,
        "certified_max_weight_kg": body.certified_max_weight_kg,
        "operational_max_weight_kg": body.operational_max_weight_kg,
        "certified_usable_volume_m3": body.certified_usable_volume_m3,
        "operational_usable_volume_m3": body.operational_usable_volume_m3,
        "capacity_profile": body.capacity_profile,
        "capacity_enforcement_mode": body.capacity_enforcement_mode,
        "storage_eligible": body.storage_eligible,
        "usable_length_m": body.usable_length_m,
        "usable_width_m": body.usable_width_m,
        "usable_height_m": body.usable_height_m,
        "notes": body.notes if "notes" in body.model_fields_set else existing.notes,
        "location_type": existing.location_type,
        "lifecycle_status": existing.lifecycle_status,
        "barcode": existing.barcode,
        "verification_code": existing.verification_code,
        "pick_sequence": existing.pick_sequence,
        "putaway_sequence": existing.putaway_sequence,
        "external_id": existing.external_id,
    }
    use_cases = LocationUseCases(SqlAlchemyLocationRepository(session))
    required = await use_cases.required_update_permissions(
        existing.warehouse_id, record_id, location_values
    )
    for permission in required:
        result = await checker.execute(current.id, company_id, permission)
        if not result.allowed:
            raise AuthorizationError(
                f"Permiso requerido: {permission}",
                code="location_operation_forbidden",
            )
    record = await use_cases.update_location(
        existing.warehouse_id,
        record_id,
        location_values,
        actor_id=_actor_id(request),
    )
    return LocationOut.model_validate(record).model_dump(mode="json", exclude_none=True)


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
    location = await session.scalar(
        select(Location).where(Location.id == record_id, Location.deleted_at.is_(None))
    )
    if location is None:
        raise HTTPException(404, "Ubicación no encontrada.")
    warehouse = await session.scalar(
        select(Warehouse).where(Warehouse.id == location.warehouse_id).with_for_update()
    )
    if warehouse is None:
        raise HTTPException(404, "Almacén no encontrado.")
    location = await session.scalar(
        select(Location)
        .where(Location.id == record_id, Location.deleted_at.is_(None))
        .with_for_update()
    )
    company_id = await _authorize_warehouse_scope(session, current, request, warehouse)
    return await _update(
        session,
        Location,
        record_id,
        {"is_active": False, "lifecycle_status": "retired"},
        user_id=_actor_id(request),
        company_id=company_id,
        branch_id=warehouse.branch_id,
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
    location = await session.scalar(
        select(Location).where(Location.id == record_id, Location.deleted_at.is_(None))
    )
    if location is None:
        raise HTTPException(404, "Ubicación no encontrada.")
    warehouse = await session.scalar(
        select(Warehouse).where(Warehouse.id == location.warehouse_id).with_for_update()
    )
    if warehouse is None:
        raise HTTPException(404, "Almacén no encontrado.")
    location = await session.scalar(
        select(Location)
        .where(Location.id == record_id, Location.deleted_at.is_(None))
        .with_for_update()
    )
    company_id = await _authorize_warehouse_scope(session, current, request, warehouse)
    if not warehouse.is_active or warehouse.operational_status == "inactive":
        raise HTTPException(409, "El almacén no admite activar ubicaciones en su estado actual.")
    return await _update(
        session,
        Location,
        record_id,
        {"is_active": True, "lifecycle_status": "active"},
        user_id=_actor_id(request),
        company_id=company_id,
        branch_id=warehouse.branch_id,
        action="ACTIVATE",
    )
