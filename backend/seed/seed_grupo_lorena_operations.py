"""Idempotent seed that puts Grupo Lorena's daily operation in motion.

It runs after ``seed_grupo_lorena`` and ``seed_grupo_lorena_fleet`` and adds:

* Store teams (cajeras, panaderos, pasteleras, auxiliares de bodega and
  repartidores) and the headquarters purchasing and cost-accounting staff,
  following the same rules as the base seeds (department opened in the branch,
  active primary assignment, accounts with an unrecoverable random password).
* Delivery vehicles for the larger stores with their repartidor as driver,
  demonstration documents through the real document pipeline and their transit
  location for transfers.
* A layout for the central warehouse and for store warehouses that only had
  their three base locations, created with the location generator (preview and
  publish) exactly as the Locations screen does it.
* Complete purchase cycles: store requests, approval, consolidation in the
  central warehouse, RFQs to several suppliers, responses, evaluation,
  adjudication per product, purchase orders, actual expenses, supplier receipts,
  retaceos (freight and insurance, DAI, additional expenses), verification,
  measurement, labels and placement into BOD-CENTRAL-01, so kardex movements,
  handling units, balances and valuation entries come from the real code.

Business documents are created only through the HTTP API of the application,
in process, authenticated as the seeded employee who would do each step. Each
document carries ``Ref. GLOPS-...`` in its notes; a rerun finds it and continues
from its current state, so nothing is duplicated and a half-finished run can be
resumed. Existing configuration is never rewritten: roles, staff, vehicles and
locations are created only when they are missing.

Run inside the backend container: ``python -m seed.seed_grupo_lorena_operations``.
"""

from __future__ import annotations

import asyncio
import secrets
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from seed.grupo_lorena_documents import driver_documents, ensure_documents, vehicle_documents
from seed.grupo_lorena_media import COMPANY_ID
from seed.grupo_lorena_operations_data import (
    AWARD_REASON,
    CENTRAL_BLOCKS,
    CENTRAL_GROUPS,
    CENTRAL_MANAGER,
    CENTRAL_SCHEME,
    CENTRAL_WAREHOUSE,
    CONSOLIDATIONS,
    EXTRA_FLEET,
    EXTRA_ROLE_GRANTS,
    HQ_STAFF,
    IMPORT_SUPPLIER,
    LICENSE_CLASSES,
    LOOSE_REQUESTS,
    PRODUCTS,
    REGIONAL_WAREHOUSE_MANAGER,
    ROLES,
    SOURCE,
    STORE_COLD_BLOCK,
    STORE_LAYOUT_THRESHOLD,
    STORE_SHELVES,
    STORE_STAFF,
    TRANSFERS,
    ConsolidationSeed,
    LocationBlock,
    OrderSeed,
    RequestSeed,
    StaffSeed,
    TransferSeed,
    marker,
    pallet_measures,
    validate_operations_seed,
)
from seed.seed_grupo_lorena import HEADQUARTERS, SUPER_ADMIN_USERNAME, _session_factory

BUSINESS_TZ = ZoneInfo("America/El_Salvador")
PURCHASING_CHIEF = "lissette.rodas"
PURCHASING_ANALYST = "gerardo.melara"
COST_ACCOUNTANT = "sandra.pineda"
ACCOUNTING_CHIEF = "hugo.alfaro"
DRIVER_ROLE = "EMPLEADO"
API = "/api/v1"


def _snapshot(row: Any) -> Any:
    """Plain copy of a row: the API commits elsewhere, so seed reads never go stale."""
    if row is None:
        return None
    columns = inspect(row).mapper.column_attrs
    return SimpleNamespace(**{column.key: getattr(row, column.key) for column in columns})


def _today() -> date:
    return datetime.now(BUSINESS_TZ).date()


@dataclass
class Report:
    created: Counter[str] = field(default_factory=Counter)
    notes: list[str] = field(default_factory=list)

    def add(self, key: str, amount: int = 1) -> None:
        if amount:
            self.created[key] += amount


# =========================================================================== ORM
# Staff, accounts and vehicles are master data; like the base seeds, they are
# written through the ORM with their audit trail. Only missing rows are created.


async def _audit(
    session: AsyncSession,
    actor_id: UUID,
    action: str,
    resource_type: str,
    resource_id: object,
    after_state: dict[str, object],
    branch_id: UUID | None = None,
) -> None:
    from app.infrastructure.models.audit import AuditLog

    session.add(
        AuditLog(
            user_id=actor_id,
            company_id=COMPANY_ID,
            branch_id=branch_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            after_state=after_state,
            status="success",
            metadata_={"source": SOURCE, "identity": "fictional"},
        )
    )


async def _ensure_roles(session: AsyncSession, actor_id: UUID, report: Report) -> dict[str, Any]:
    """Create the purchasing roles once; an existing role keeps its permissions."""
    from app.infrastructure.models.rbac import Permission, Role, RolePermission

    permissions = {
        row.code: row
        for row in await session.scalars(select(Permission).where(Permission.deleted_at.is_(None)))
    }
    roles: dict[str, Any] = {}
    for name, (description, codes) in ROLES.items():
        role = await session.scalar(
            select(Role).where(
                Role.company_id == COMPANY_ID,
                func.lower(Role.name) == name.casefold(),
                Role.deleted_at.is_(None),
            )
        )
        if role is None:
            role = Role(name=name, description=description, is_system=False, company_id=COMPANY_ID)
            session.add(role)
            await session.flush()
            for code in codes:
                session.add(RolePermission(role_id=role.id, permission_id=permissions[code].id))
            await _audit(
                session, actor_id, "CREATE", "roles", role.id, {"name": name, "permissions": codes}
            )
            report.add("roles")
        roles[name] = role
    driver_role = await session.scalar(
        select(Role).where(Role.company_id == COMPANY_ID, Role.name == DRIVER_ROLE)
    )
    if driver_role is None:
        raise RuntimeError(f"Falta el rol {DRIVER_ROLE}; ejecute primero seed_grupo_lorena.")
    roles[DRIVER_ROLE] = driver_role
    return roles


async def _branches(session: AsyncSession) -> dict[str, Any]:
    from app.infrastructure.models.organization import Branch

    rows = list(
        await session.scalars(
            select(Branch).where(Branch.company_id == COMPANY_ID, Branch.deleted_at.is_(None))
        )
    )
    result = {row.code: row for row in rows}
    headquarters = [row for row in rows if row.is_headquarters and row.is_active]
    if len(headquarters) != 1:
        raise RuntimeError("Grupo Lorena debe tener exactamente una matriz activa.")
    result[HEADQUARTERS] = headquarters[0]
    return result


async def _open_department(
    session: AsyncSession, department_id: UUID, branch_id: UUID, report: Report
) -> None:
    from app.infrastructure.models.employee import DepartmentBranchAssignment

    opening = await session.scalar(
        select(DepartmentBranchAssignment).where(
            DepartmentBranchAssignment.department_id == department_id,
            DepartmentBranchAssignment.branch_id == branch_id,
        )
    )
    if opening is None:
        session.add(
            DepartmentBranchAssignment(
                department_id=department_id, branch_id=branch_id, is_active=True
            )
        )
        report.add("department_openings")
    elif not opening.is_active:
        # A closed department cannot receive new hires; reopening is what HR does.
        opening.is_active = True
        opening.closed_at = None


async def _ensure_user(
    session: AsyncSession,
    *,
    username: str,
    employee: Any,
    branch: Any,
    all_branches: bool,
    roles: Iterable[Any],
    actor_id: UUID,
    password_hash: str,
    report: Report,
) -> Any:
    from app.infrastructure.models.organization import UserBranch, UserCompany
    from app.infrastructure.models.rbac import UserRole
    from app.infrastructure.models.user import User

    user = await session.scalar(
        select(User).where(func.lower(User.username) == username.casefold())
    )
    if user is None:
        user = User(
            username=username,
            email=f"{username}@grupo-lorena.example",
            password_hash=password_hash,
            is_active=True,
            is_superuser=False,
        )
        session.add(user)
        await session.flush()
        await _audit(
            session,
            actor_id,
            "CREATE",
            "users",
            user.id,
            {"username": username, "employee_code": employee.employee_code},
            branch.id,
        )
        report.add("users")
    if employee.user_id is None:
        employee.user_id = user.id
    if await session.get(UserCompany, (user.id, COMPANY_ID)) is None:
        session.add(
            UserCompany(
                user_id=user.id,
                company_id=COMPANY_ID,
                is_default=True,
                access_all_branches=all_branches,
                last_branch_id=branch.id,
            )
        )
        await session.flush()
    for role in roles:
        if await session.get(UserRole, (user.id, COMPANY_ID, role.id)) is None:
            session.add(
                UserRole(
                    user_id=user.id, company_id=COMPANY_ID, role_id=role.id, assigned_by=actor_id
                )
            )
    if not all_branches and await session.get(UserBranch, (user.id, branch.id)) is None:
        session.add(
            UserBranch(
                user_id=user.id,
                company_id=COMPANY_ID,
                branch_id=branch.id,
                assigned_by=actor_id,
                is_default=True,
                is_active=True,
            )
        )
    return user


async def _ensure_staff(
    session: AsyncSession,
    *,
    branches: dict[str, Any],
    roles: dict[str, Any],
    actor_id: UUID,
    report: Report,
) -> dict[str, Any]:
    from app.core.security import hash_password
    from app.infrastructure.models.employee import Department, Employee, EmployeeBranchAssignment

    departments = {
        row.name: row
        for row in await session.scalars(
            select(Department).where(
                Department.company_id == COMPANY_ID, Department.deleted_at.is_(None)
            )
        )
    }
    password_hash = hash_password(secrets.token_urlsafe(48))
    employees: dict[str, Any] = {}
    people: tuple[StaffSeed, ...] = (*HQ_STAFF, *STORE_STAFF)
    for branch_code, department in {(p.branch, p.department) for p in people}:
        await _open_department(
            session, departments[department].id, branches[branch_code].id, report
        )
    await session.flush()
    for index, person in enumerate(people):
        branch = branches[person.branch]
        employee = await session.scalar(
            select(Employee)
            .where(
                Employee.company_id == COMPANY_ID,
                func.lower(Employee.employee_code) == person.code.casefold(),
            )
            .execution_options(include_deleted=True)
        )
        if employee is None:
            employee = Employee(
                company_id=COMPANY_ID,
                employee_code=person.code,
                first_name=person.first,
                last_name=person.last,
                department_id=departments[person.department].id,
                position=person.position,
                hire_date=date(2023 + index % 3, index % 12 + 1, 1 + index % 27),
                status="activo",
            )
            session.add(employee)
            await session.flush()
            session.add(
                EmployeeBranchAssignment(
                    employee_id=employee.id,
                    branch_id=branch.id,
                    is_primary=True,
                    position=person.position,
                    shift=person.shift,
                    is_active=True,
                )
            )
            await _audit(
                session,
                actor_id,
                "CREATE",
                "employees",
                employee.id,
                {
                    "employee_code": person.code,
                    "name": f"{person.first} {person.last}",
                    "position": person.position,
                },
                branch.id,
            )
            report.add("employees")
        employees[person.code] = employee
        if person.username and person.role:
            await _ensure_user(
                session,
                username=person.username,
                employee=employee,
                branch=branch,
                all_branches=person.branch == HEADQUARTERS,
                roles=(roles[person.role],),
                actor_id=actor_id,
                password_hash=password_hash,
                report=report,
            )
    await _grant_extra_roles(session, roles, actor_id, report)
    return employees


async def _grant_extra_roles(
    session: AsyncSession, roles: dict[str, Any], actor_id: UUID, report: Report
) -> None:
    from app.infrastructure.models.rbac import UserRole
    from app.infrastructure.models.user import User

    for username, role_name in EXTRA_ROLE_GRANTS:
        user = await session.scalar(select(User).where(User.username == username))
        if user is None:
            raise RuntimeError(f"Falta el usuario {username}; ejecute primero seed_grupo_lorena.")
        role = roles[role_name]
        if await session.get(UserRole, (user.id, COMPANY_ID, role.id)) is None:
            session.add(
                UserRole(
                    user_id=user.id, company_id=COMPANY_ID, role_id=role.id, assigned_by=actor_id
                )
            )
            await _audit(session, actor_id, "ASSIGN_ROLE", "users", user.id, {"role": role_name})
            report.add("role_grants")


@dataclass(slots=True)
class _FleetPair:
    branch_id: UUID
    vehicle: Any
    driver: Any
    employee: Any
    seed: Any
    vehicle_seed: Any


async def _ensure_fleet(
    session: AsyncSession,
    *,
    branches: dict[str, Any],
    employees: dict[str, Any],
    roles: dict[str, Any],
    actor_id: UUID,
    report: Report,
) -> list[_FleetPair]:
    from app.api.v1.routers.fleet import ensure_inventory_vehicle
    from app.core.security import hash_password
    from app.infrastructure.models.fleet import (
        DriverModel,
        FleetVehicleModel,
        FleetVehicleTypeModel,
        OdometerReadingModel,
    )

    catalogue = {
        row.code: frozenset(row.license_classes)
        for row in await session.scalars(
            select(FleetVehicleTypeModel).where(FleetVehicleTypeModel.company_id == COMPANY_ID)
        )
    }
    password_hash = hash_password(secrets.token_urlsafe(48))
    pairs: list[_FleetPair] = []
    for item in EXTRA_FLEET:
        branch = branches[item.branch]
        vehicles: dict[str, Any] = {}
        for seed in item.vehicles:
            if not catalogue.get(seed.kind, frozenset()) & LICENSE_CLASSES[seed.kind]:
                raise RuntimeError(f"El catálogo de la empresa no admite {seed.kind}.")
            vehicle = await session.scalar(
                select(FleetVehicleModel)
                .where(
                    FleetVehicleModel.company_id == COMPANY_ID,
                    func.lower(FleetVehicleModel.code) == seed.code.casefold(),
                )
                .execution_options(include_deleted=True)
            )
            if vehicle is None:
                vehicle = FleetVehicleModel(
                    company_id=COMPANY_ID,
                    branch_id=branch.id,
                    code=seed.code,
                    plate=seed.plate,
                    kind=seed.kind,
                    brand=seed.brand,
                    model=seed.model,
                    year=seed.year,
                    color="Rojo" if seed.kind == "motorcycle" else "Blanco",
                    capacity_kg=Decimal(seed.capacity_kg),
                    fuel_type=seed.fuel_type,
                    odometer_km=Decimal(seed.odometer_km),
                    notes=seed.notes,
                    status="active",
                    created_by=actor_id,
                    updated_by=actor_id,
                )
                vehicle.inventory_vehicle_id = await ensure_inventory_vehicle(
                    session, vehicle, actor_id
                )
                session.add(vehicle)
                await session.flush()
                session.add(
                    OdometerReadingModel(
                        company_id=COMPANY_ID,
                        vehicle_id=vehicle.id,
                        reading_km=vehicle.odometer_km,
                        read_at=datetime.now(UTC),
                        source="manual",
                        notes="Lectura inicial al registrar el vehículo.",
                        recorded_by=actor_id,
                    )
                )
                await _audit(
                    session,
                    actor_id,
                    "CREATE",
                    "fleet_vehicles",
                    vehicle.id,
                    {"code": seed.code, "plate": seed.plate, "kind": seed.kind},
                    branch.id,
                )
                report.add("vehicles")
            elif vehicle.inventory_vehicle_id is None and vehicle.deleted_at is None:
                vehicle.inventory_vehicle_id = await ensure_inventory_vehicle(
                    session, vehicle, actor_id
                )
            vehicles[seed.code] = (vehicle, seed)
        for driver_seed in item.drivers:
            employee = employees[driver_seed.code]
            await _ensure_user(
                session,
                username=driver_seed.username,
                employee=employee,
                branch=branch,
                all_branches=False,
                roles=(roles[DRIVER_ROLE],),
                actor_id=actor_id,
                password_hash=password_hash,
                report=report,
            )
            driver = await session.scalar(
                select(DriverModel).where(
                    DriverModel.company_id == COMPANY_ID,
                    DriverModel.employee_id == employee.id,
                    DriverModel.deleted_at.is_(None),
                )
            )
            if driver is None:
                driver = DriverModel(
                    company_id=COMPANY_ID,
                    employee_id=employee.id,
                    branch_id=branch.id,
                    license_class=driver_seed.license_class,
                    status="active",
                    created_by=actor_id,
                    updated_by=actor_id,
                )
                session.add(driver)
                await session.flush()
                await _audit(
                    session,
                    actor_id,
                    "CREATE",
                    "drivers",
                    driver.id,
                    {"employee_id": str(employee.id), "license_class": driver.license_class},
                    branch.id,
                )
                report.add("drivers")
            vehicle, vehicle_seed = vehicles[driver_seed.vehicle]
            pairs.append(
                _FleetPair(branch.id, vehicle, driver, employee, driver_seed, vehicle_seed)
            )
    return pairs


async def _document_and_assign_fleet(
    session: AsyncSession, pairs: list[_FleetPair], actor_id: UUID, report: Report
) -> None:
    """Upload the demonstration documents, then assign each free vehicle to its driver."""
    from app.application.fleet.costs import BUSINESS_TZ as FLEET_TZ
    from app.application.fleet.settings import settings_from
    from app.core.config import settings
    from app.infrastructure.models.fleet import FleetSettingsModel, VehicleDriverAssignmentModel

    override: str | None = None
    if settings.OBJECT_STORAGE_ENABLED:
        today = datetime.now(FLEET_TZ).date()
        warning_days = settings_from(
            await session.get(FleetSettingsModel, COMPANY_ID)
        ).document_warning_days
        for pair in pairs:
            vehicle_seed = pair.vehicle_seed
            report.add(
                "documents",
                await ensure_documents(
                    session,
                    company_id=COMPANY_ID,
                    actor_id=actor_id,
                    module="fleet",
                    owner_type="vehicle",
                    owner_id=pair.vehicle.id,
                    documents=vehicle_documents(
                        vehicle_seed.code,
                        pair.vehicle.plate or vehicle_seed.plate,
                        vehicle_seed.brand,
                        vehicle_seed.model,
                        today,
                    ),
                    today=today,
                    warning_days=warning_days,
                ),
            )
            report.add(
                "documents",
                await ensure_documents(
                    session,
                    company_id=COMPANY_ID,
                    actor_id=actor_id,
                    module="employees",
                    owner_type="employee",
                    owner_id=pair.employee.id,
                    documents=driver_documents(
                        pair.seed.code,
                        f"{pair.seed.first} {pair.seed.last}",
                        pair.seed.license_class,
                        today,
                    ),
                    today=today,
                    warning_days=warning_days,
                ),
            )
    else:
        override = "Datos de desarrollo: documentos pendientes de cargar (almacenamiento inactivo)."
        report.notes.append("Sin almacenamiento de objetos: vehículos asignados con excepción.")
    for pair in pairs:
        busy = await session.scalar(
            select(func.count())
            .select_from(VehicleDriverAssignmentModel)
            .where(
                VehicleDriverAssignmentModel.ends_at.is_(None),
                (VehicleDriverAssignmentModel.vehicle_id == pair.vehicle.id)
                | (VehicleDriverAssignmentModel.driver_id == pair.driver.id),
            )
        )
        if busy or pair.vehicle.deleted_at is not None or pair.vehicle.status == "retired":
            continue
        link = VehicleDriverAssignmentModel(
            company_id=COMPANY_ID,
            vehicle_id=pair.vehicle.id,
            driver_id=pair.driver.id,
            starts_at=datetime.now(UTC),
            assigned_by=actor_id,
        )
        session.add(link)
        await session.flush()
        await _audit(
            session,
            actor_id,
            "ASSIGN_DRIVER",
            "fleet_vehicles",
            pair.vehicle.id,
            {"driver_id": str(pair.driver.id), "assignment_id": str(link.id)}
            | ({"compliance_override": override} if override else {}),
            pair.branch_id,
        )
        report.add("driver_assignments")
    await session.commit()


# =========================================================================== API


class ApiError(RuntimeError):
    pass


class Api:
    """The real application, called in process as the employee doing each step."""

    def __init__(self, client: Any, tokens: dict[str, str]) -> None:
        self.client = client
        self.tokens = tokens

    async def call(
        self,
        actor: str,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        ok: tuple[int, ...] = (200, 201),
    ) -> Any:
        response = await self.client.request(
            method,
            f"{API}{path}",
            json=json,
            params=params,
            headers={
                "Authorization": f"Bearer {self.tokens[actor]}",
                "X-Company-ID": str(COMPANY_ID),
            },
        )
        if response.status_code not in ok:
            raise ApiError(f"{method} {path} como {actor}: {response.status_code} {response.text}")
        return response.json() if response.content else None


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


@dataclass
class Context:
    session: AsyncSession
    api: Api
    report: Report
    branches: dict[str, Any]
    warehouses: dict[str, Any]
    products: dict[str, Any]
    suppliers: dict[str, int]
    expense_types: dict[str, UUID]

    @property
    def central(self) -> Any:
        return self.warehouses[CENTRAL_WAREHOUSE]


async def _tokens(session: AsyncSession) -> dict[str, str]:
    from app.infrastructure.models.user import User
    from app.infrastructure.repositories.token_service import JwtTokenService

    actors = {
        PURCHASING_CHIEF,
        PURCHASING_ANALYST,
        COST_ACCOUNTANT,
        ACCOUNTING_CHIEF,
        CENTRAL_MANAGER,
        REGIONAL_WAREHOUSE_MANAGER,
        *(request.requester for seed in CONSOLIDATIONS for request in seed.requests),
        *(request.requester for request in LOOSE_REQUESTS),
    }
    service = JwtTokenService()
    tokens: dict[str, str] = {}
    for username in actors:
        user = await session.scalar(
            select(User).where(User.username == username, User.deleted_at.is_(None))
        )
        if user is None or not user.is_active:
            raise RuntimeError(f"El usuario {username} no existe o está inactivo.")
        tokens[username] = service.issue_access_token(
            user_id=user.id, username=user.username, is_superuser=user.is_superuser
        )
    return tokens


async def _refresh(ctx: Context) -> None:
    """Reload reference rows; the API commits in its own sessions."""
    from app.infrastructure.models.catalog import ProductModel
    from app.infrastructure.models.organization import Warehouse
    from app.infrastructure.models.purchase_quotation import ExpenseTypeModel
    from app.infrastructure.models.supplier import SupplierModel

    ctx.session.expire_all()
    ctx.warehouses = {
        row.code: _snapshot(row)
        for row in await ctx.session.scalars(
            select(Warehouse).where(
                Warehouse.company_id == COMPANY_ID, Warehouse.deleted_at.is_(None)
            )
        )
    }
    ctx.products = {
        row.sku: _snapshot(row)
        for row in await ctx.session.scalars(
            select(ProductModel).where(
                ProductModel.company_id == COMPANY_ID, ProductModel.deleted_at.is_(None)
            )
        )
    }
    ctx.suppliers = {
        row.code: row.id_supplier
        for row in await ctx.session.scalars(
            select(SupplierModel).where(
                SupplierModel.company_id == COMPANY_ID, SupplierModel.deleted_at.is_(None)
            )
        )
    }
    ctx.expense_types = {
        row.name: row.id
        for row in await ctx.session.scalars(
            select(ExpenseTypeModel).where(
                ExpenseTypeModel.company_id == COMPANY_ID, ExpenseTypeModel.is_active.is_(True)
            )
        )
    }


# --------------------------------------------------------------------- suppliers


async def _ensure_import_supplier(ctx: Context) -> None:
    if IMPORT_SUPPLIER["code"] in ctx.suppliers:
        return
    created = await ctx.api.call(PURCHASING_CHIEF, "POST", "/suppliers", json=IMPORT_SUPPLIER)
    ctx.suppliers[str(IMPORT_SUPPLIER["code"])] = int(created["id_supplier"])
    ctx.report.add("suppliers")


# --------------------------------------------------------------------- inventory


async def _ensure_inventory_setup(ctx: Context) -> None:
    """Each purchased product needs its inventory identity and purchase presentation."""
    from app.infrastructure.models.catalog import UnitModel
    from app.infrastructure.models.inventory import InventoryItemModel, InventoryPackagingModel

    units = {
        row.code: row.id_unit
        for row in await ctx.session.scalars(
            select(UnitModel).where(UnitModel.owner_company_id.is_(None))
        )
    }
    for sku, setup in PRODUCTS.items():
        product = ctx.products[sku]
        item = await ctx.session.scalar(
            select(InventoryItemModel).where(
                InventoryItemModel.company_id == COMPANY_ID,
                InventoryItemModel.product_id == product.id_product,
                InventoryItemModel.variant_id.is_(None),
            )
        )
        if item is None:
            created = await ctx.api.call(
                REGIONAL_WAREHOUSE_MANAGER,
                "POST",
                "/inventory/items",
                json={"product_id": product.id_product, "base_unit_id": units[setup.base_unit]},
            )
            item_id, base_unit_id = UUID(created["id"]), int(created["base_unit_id"])
            ctx.report.add("inventory_items")
        else:
            item_id, base_unit_id = item.id, item.base_unit_id
        if base_unit_id == product.purchase_unit:
            continue
        current = await ctx.session.scalar(
            select(InventoryPackagingModel.id).where(
                InventoryPackagingModel.company_id == COMPANY_ID,
                InventoryPackagingModel.inventory_item_id == item_id,
                InventoryPackagingModel.packaging_unit_id == product.purchase_unit,
                InventoryPackagingModel.is_current.is_(True),
                InventoryPackagingModel.is_active.is_(True),
            )
        )
        if current is not None or setup.packaging_code is None:
            continue
        await ctx.api.call(
            REGIONAL_WAREHOUSE_MANAGER,
            "POST",
            f"/inventory/items/{item_id}/packaging",
            json={
                "code": setup.packaging_code,
                "name": setup.packaging_name,
                "packaging_type": setup.packaging_type,
                "packaging_unit_id": product.purchase_unit,
                "base_quantity": str(setup.per_purchase_unit),
                "measures": {
                    "gross_weight_kg": str(setup.unit_weight_kg),
                    "volume_m3": str(setup.unit_volume_m3),
                },
                "stackable": True,
            },
        )
        ctx.report.add("packaging_definitions")


# --------------------------------------------------------------------- locations


def _block_defaults(block: LocationBlock, group_id: UUID | None) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "location_type": block.location_type,
        "capacity_profile": block.profile,
        "storage_eligible": block.storage_eligible,
        "capacity_enforcement_mode": "enforce" if block.limits else "disabled",
        "notes": block.label,
    }
    if block.area:
        defaults["area"] = block.area
    if block.limits:
        defaults |= block.limits.payload()
    if group_id:
        defaults["capacity_group_id"] = str(group_id)
    return defaults


async def _create_block_one_by_one(
    ctx: Context, actor: str, warehouse: Any, block: LocationBlock, group_id: UUID
) -> None:
    """Locations inside a capacity structure are created one by one.

    The generator stores the structure id as text in its staged rows and the
    capacity validation then compares it with UUIDs, so publishing a batch with
    a structure fails (``location_capacity_group_unavailable``). The single
    location form validates it correctly; missing coordinates are created there.
    """
    from app.infrastructure.models.organization import Location

    ctx.session.expire_all()
    existing = {
        (row.area or "", row.aisle, row.rack, row.level, row.position)
        for row in await ctx.session.scalars(
            select(Location).where(
                Location.warehouse_id == warehouse.id, Location.deleted_at.is_(None)
            )
        )
    }
    defaults = _block_defaults(block, group_id)
    for coordinates in block.coordinates():
        key = (
            coordinates.get("area", ""),
            coordinates["aisle"],
            coordinates["rack"],
            coordinates["level"],
            coordinates["position"],
        )
        if key in existing:
            continue
        await ctx.api.call(
            actor, "POST", f"/warehouses/{warehouse.id}/locations", json=defaults | coordinates
        )
        ctx.report.add("locations")


async def _publish_block(
    ctx: Context, actor: str, warehouse: Any, block: LocationBlock, group_id: UUID | None
) -> None:
    if group_id is not None:
        await _create_block_one_by_one(ctx, actor, warehouse, block, group_id)
        return
    job = await ctx.api.call(
        actor,
        "POST",
        f"/warehouses/{warehouse.id}/location-batches/generate/preview",
        json={
            "idempotency_key": f"glops-{warehouse.code}-{block.key}-v1".lower(),
            "axes": [
                {"key": "aisle", "values": list(block.aisles)},
                {"key": "rack", "values": list(block.racks)},
                {"key": "level", "values": list(block.levels)},
                {"key": "position", "values": list(block.positions)},
            ],
            "defaults": _block_defaults(block, group_id),
        },
    )
    if job["status"] == "published" or job["create_count"] == 0:
        return
    if job["update_count"] or job["conflict_count"] or job["error_count"]:
        ctx.report.notes.append(
            f"{warehouse.code}/{block.key}: el lote modificaría ubicaciones existentes; no se publicó."
        )
        return
    published = await ctx.api.call(actor, "POST", f"/location-batches/{job['id']}/publish")
    ctx.report.add("locations", int(published["create_count"]))


async def _ensure_central_layout(ctx: Context) -> None:
    warehouse = ctx.central
    path = f"/warehouses/{warehouse.id}/location-code-scheme"
    try:
        await ctx.api.call(CENTRAL_MANAGER, "GET", path)
    except ApiError as exc:
        if " 404 " not in str(exc):
            raise
        await ctx.api.call(CENTRAL_MANAGER, "PUT", path, json=CENTRAL_SCHEME)
        ctx.report.add("location_schemes")
    groups = {
        row["code"]: UUID(row["id"])
        for row in await ctx.api.call(
            CENTRAL_MANAGER, "GET", f"/warehouses/{warehouse.id}/capacity-groups"
        )
    }
    for group in CENTRAL_GROUPS:
        if group.code in groups:
            continue
        created = await ctx.api.call(
            CENTRAL_MANAGER,
            "POST",
            f"/warehouses/{warehouse.id}/capacity-groups",
            json={
                "code": group.code,
                "name": group.name,
                "group_type": group.group_type,
                "capacity_profile": group.profile,
                "capacity_enforcement_mode": "enforce",
                "storage_eligible": True,
                **group.limits.payload(),
            },
        )
        groups[group.code] = UUID(created["id"])
        ctx.report.add("capacity_groups")
    for block in CENTRAL_BLOCKS:
        await _publish_block(ctx, CENTRAL_MANAGER, warehouse, block, groups.get(block.group or ""))


async def _ensure_store_layouts(ctx: Context) -> None:
    from app.infrastructure.models.location import LocationBatchJob
    from app.infrastructure.models.organization import Location, WarehouseCapacityGroup

    for code, warehouse in sorted(ctx.warehouses.items()):
        if warehouse.is_central or warehouse.is_transit or not code.startswith("BOD-"):
            continue
        seeded = await ctx.session.scalar(
            select(func.count())
            .select_from(LocationBatchJob)
            .where(
                LocationBatchJob.warehouse_id == warehouse.id,
                LocationBatchJob.idempotency_key.like("glops-%"),
            )
        )
        count = await ctx.session.scalar(
            select(func.count())
            .select_from(Location)
            .where(Location.warehouse_id == warehouse.id, Location.deleted_at.is_(None))
        )
        if not seeded and (count or 0) > STORE_LAYOUT_THRESHOLD:
            continue
        await _publish_block(ctx, REGIONAL_WAREHOUSE_MANAGER, warehouse, STORE_SHELVES, None)
        has_cold = await ctx.session.scalar(
            select(func.count())
            .select_from(WarehouseCapacityGroup)
            .where(
                WarehouseCapacityGroup.warehouse_id == warehouse.id,
                WarehouseCapacityGroup.capacity_profile == "cold",
                WarehouseCapacityGroup.deleted_at.is_(None),
            )
        )
        cold_locations = await ctx.session.scalar(
            select(func.count())
            .select_from(Location)
            .where(
                Location.warehouse_id == warehouse.id,
                Location.capacity_profile == "cold",
                Location.deleted_at.is_(None),
            )
        )
        if not has_cold and not cold_locations:
            await _publish_block(ctx, REGIONAL_WAREHOUSE_MANAGER, warehouse, STORE_COLD_BLOCK, None)


# --------------------------------------------------------------------- purchasing


async def _find(ctx: Context, model: Any, key: str) -> Any:
    ctx.session.expire_all()
    return _snapshot(
        await ctx.session.scalar(
            select(model).where(model.company_id == COMPANY_ID, model.notes.contains(marker(key)))
        )
    )


def _warehouse_for(ctx: Context, branch: str) -> Any:
    if branch == HEADQUARTERS:
        return ctx.central
    return ctx.warehouses[f"BOD-{branch.removeprefix('LOR-')}"]


async def _ensure_request(ctx: Context, seed: RequestSeed) -> Any:
    from app.infrastructure.models.purchase_request import PurchaseRequestModel

    item = await _find(ctx, PurchaseRequestModel, f"SOL-{seed.key}")
    if item is None:
        branch = ctx.branches[seed.branch]
        created = await ctx.api.call(
            seed.requester,
            "POST",
            "/purchase-requests",
            json={
                "branch_id": str(branch.id),
                "warehouse_id": str(_warehouse_for(ctx, seed.branch).id),
                "required_date": (
                    datetime.now(UTC) + timedelta(days=seed.required_in_days)
                ).isoformat(),
                "justification": seed.justification,
                "notes": f"Solicitud de {branch.name}. {marker('SOL-' + seed.key)}",
                "details": [
                    {"product_id": ctx.products[sku].id_product, "quantity": str(quantity)}
                    for sku, quantity in seed.lines
                ],
            },
        )
        ctx.report.add("purchase_requests")
        status, request_id = created["status"], created["id"]
    else:
        status, request_id = item.status, item.id
    if status == "draft" and seed.state != "draft":
        await ctx.api.call(seed.requester, "POST", f"/purchase-requests/{request_id}/submit")
        status = "submitted"
    if status == "submitted" and seed.state == "approved":
        await ctx.api.call(PURCHASING_CHIEF, "POST", f"/purchase-requests/{request_id}/approve")
    return await _find(ctx, PurchaseRequestModel, f"SOL-{seed.key}")


async def _ensure_consolidation(ctx: Context, seed: ConsolidationSeed, requests: list[Any]) -> Any:
    from app.infrastructure.models.purchase_consolidation import PurchaseConsolidationModel

    item = await _find(ctx, PurchaseConsolidationModel, f"CON-{seed.key}")
    if item is not None:
        return item
    days = [request.request_date.astimezone(BUSINESS_TZ).date() for request in requests]
    await ctx.api.call(
        PURCHASING_ANALYST,
        "POST",
        "/purchase-consolidations",
        json={
            "request_ids": [str(request.id) for request in requests],
            "period_start": min(days).isoformat(),
            "period_end": max(days).isoformat(),
            "central_warehouse_id": str(ctx.central.id),
            "notes": f"{seed.title}. {marker('CON-' + seed.key)}",
        },
    )
    ctx.report.add("purchase_consolidations")
    return await _find(ctx, PurchaseConsolidationModel, f"CON-{seed.key}")


async def _ensure_quotations(
    ctx: Context, seed: ConsolidationSeed, consolidation: Any
) -> dict[str, dict[str, Any]]:
    """RFQs per supplier, from draft to evaluation (or left waiting for a reply)."""
    base = f"/purchase-consolidations/{consolidation.id}"
    detail = await ctx.api.call(PURCHASING_ANALYST, "GET", base)
    lines = {line["product_sku"]: line for line in detail["lines"]}
    params = {"consolidation_id": str(consolidation.id)}
    result: dict[str, dict[str, Any]] = {}
    for quote in seed.quotes:
        supplier_id = ctx.suppliers[quote.supplier]
        existing = [
            row
            for row in await ctx.api.call(PURCHASING_ANALYST, "GET", f"{base}/purchase-quotations")
            if row["supplier_id"] == supplier_id and row["status"] != "cancelled"
        ]
        if existing:
            quotation = existing[0]
        else:
            quotation = await ctx.api.call(
                PURCHASING_ANALYST,
                "POST",
                f"{base}/purchase-quotations",
                json={
                    "supplier_id": supplier_id,
                    "currency": "USD",
                    "consolidation_line_ids": [lines[sku]["id"] for sku in quote.prices],
                    "notes": f"Solicitud de precios {consolidation.code}. "
                    f"{marker(f'RFQ-{seed.key}-{quote.supplier}')}",
                },
            )
            ctx.report.add("purchase_quotations")
        qid = quotation["id"]
        if quotation["status"] == "draft":
            quotation = await ctx.api.call(
                PURCHASING_ANALYST, "POST", f"/purchase-quotations/{qid}/send", params=params
            )
        if quotation["status"] == "requested" and quote.respond:
            now = datetime.now(UTC)
            quotation = await ctx.api.call(
                PURCHASING_ANALYST,
                "PUT",
                f"/purchase-quotations/{qid}/response",
                params=params,
                json={
                    "quotation_date": now.isoformat(),
                    "valid_until": (now + timedelta(days=21)).isoformat(),
                    "payment_terms": quote.payment_terms,
                    "delivery_days": quote.delivery_days,
                    "notes": quote.notes or None,
                    "lines": [
                        {
                            "product_id": row["product_id"],
                            "unit_id": row["unit_id"],
                            "offered_quantity": row["quantity"],
                            "available_quantity": row["quantity"],
                            "unit_price": str(quote.prices[_sku_of(ctx, int(row["product_id"]))]),
                            "tax_rate": str(quote.tax_rate),
                        }
                        for row in quotation["details"]
                    ],
                },
            )
        if quotation["status"] == "received":
            quotation = await ctx.api.call(
                PURCHASING_ANALYST, "POST", f"/purchase-quotations/{qid}/evaluate", params=params
            )
        result[quote.supplier] = quotation
    return result


def _sku_of(ctx: Context, product_id: int) -> str:
    return next(sku for sku, row in ctx.products.items() if row.id_product == product_id)


async def _ensure_awards(
    ctx: Context, seed: ConsolidationSeed, consolidation: Any, quotations: dict[str, Any]
) -> None:
    path = f"/purchase-consolidations/{consolidation.id}"
    board = await ctx.api.call(PURCHASING_CHIEF, "GET", f"{path}/adjudication")
    for line in board["lines"]:
        supplier = seed.awards.get(line["product_sku"])
        if supplier is None or Decimal(line["remaining_quantity"]) <= 0:
            continue
        offer = next(
            row for row in line["offers"] if row["quotation_id"] == quotations[supplier]["id"]
        )
        await ctx.api.call(
            PURCHASING_CHIEF,
            "POST",
            f"{path}/awards",
            json={
                "consolidation_line_id": line["id"],
                "quotation_id": offer["quotation_id"],
                "quotation_detail_id": offer["quotation_detail_id"],
                "quantity": line["remaining_quantity"],
                "reason": AWARD_REASON,
            },
        )
        ctx.report.add("awards")


async def _ensure_order(
    ctx: Context, seed: ConsolidationSeed, consolidation: Any, order: OrderSeed, quotation: Any
) -> dict[str, Any]:
    from app.infrastructure.models.purchase_order import PurchaseOrderModel

    key = f"OC-{seed.key}-{order.supplier}"
    item = await _find(ctx, PurchaseOrderModel, key)
    if item is None:
        created = await ctx.api.call(
            PURCHASING_ANALYST,
            "POST",
            f"/purchase-orders/from-consolidation/{consolidation.id}/{quotation['id']}",
            json={
                "warehouse_id": str(ctx.central.id),
                "expected_date": (
                    datetime.now(UTC) + timedelta(days=order.expected_in_days)
                ).isoformat(),
                "expenses": [
                    {
                        "expense_type_id": str(ctx.expense_types[name]),
                        "amount": str(amount),
                        "description": description,
                    }
                    for name, amount, description in order.planned
                ],
                "notes": f"Entrega en {ctx.central.name}, andén de recepción. {marker(key)}",
            },
        )
        ctx.report.add("purchase_orders")
        order_id, status = created["id"], created["status"]
    else:
        order_id, status = item.id, item.status
    steps = (
        ("draft", "submit", PURCHASING_ANALYST),
        ("pending_approval", "approve", PURCHASING_CHIEF),
        ("approved", "send", PURCHASING_CHIEF),
    )
    target_rank = {"pending_approval": 1, "sent": 3, "received": 3}[order.state]
    for rank, (current, action, actor) in enumerate(steps, start=1):
        if rank > target_rank:
            break
        if status == current:
            status = (await ctx.api.call(actor, "POST", f"/purchase-orders/{order_id}/{action}"))[
                "status"
            ]
    result: dict[str, Any] = await ctx.api.call(
        PURCHASING_ANALYST, "GET", f"/purchase-orders/{order_id}"
    )
    if order.actual:
        listed = await ctx.api.call(
            PURCHASING_ANALYST, "GET", f"/purchase-orders/{order_id}/actual-expenses"
        )
        references = {row["reference"] for row in listed}
        for expense in order.actual:
            if expense.reference in references:
                continue
            await ctx.api.call(
                PURCHASING_ANALYST,
                "POST",
                f"/purchase-orders/{order_id}/actual-expenses",
                json={
                    "expense_type_id": str(ctx.expense_types[expense.category]),
                    "amount": str(expense.amount),
                    "incurred_on": (_today() - timedelta(days=expense.days_ago)).isoformat(),
                    "reference": expense.reference,
                    "description": expense.description,
                },
            )
            ctx.report.add("actual_expenses")
    return result


async def _ensure_receipt(ctx: Context, seed: ConsolidationSeed, order: OrderSeed, po: Any) -> None:
    from app.infrastructure.models.purchase import PurchaseModel

    receipt = order.receipt
    if receipt is None:
        return
    key = f"REC-{seed.key}-{order.supplier}"
    item = await _find(ctx, PurchaseModel, key)
    if item is None:
        lines = []
        for detail in po["details"]:
            sku = _sku_of(ctx, int(detail["product_id"]))
            quantity = receipt.partial.get(sku, Decimal(detail["quantity"]))
            lines.append(
                {"purchase_order_detail_id": detail["id"], "quantity_received": str(quantity)}
            )
        created = await ctx.api.call(
            CENTRAL_MANAGER,
            "POST",
            "/purchases",
            json={
                "purchase_order_id": po["id"],
                "supplier_invoice_number": receipt.invoice,
                "supplier_invoice_date": (
                    _today() - timedelta(days=receipt.invoice_days_ago)
                ).isoformat(),
                "lines": lines,
                "notes": f"Recepción de {po['code']} en andén. {marker(key)}",
            },
        )
        ctx.report.add("purchases")
        purchase_id, status = created["id"], created["status"]
    else:
        purchase_id, status = str(item.id), item.status
    if status == "draft":
        status = (await ctx.api.call(CENTRAL_MANAGER, "POST", f"/purchases/{purchase_id}/receive"))[
            "status"
        ]
    if status == "received":
        await _ensure_retaceo(ctx, order, po, purchase_id, key)
        purchase = await ctx.api.call(CENTRAL_MANAGER, "GET", f"/purchases/{purchase_id}")
        dock = await _dock(ctx)
        await ctx.api.call(
            CENTRAL_MANAGER,
            "POST",
            f"/purchases/{purchase_id}/verify",
            json={
                "lines": [
                    {
                        "purchase_detail_id": row["id"],
                        "quantity_accepted": row["quantity_received"],
                        "inventory_location_id": str(dock),
                    }
                    for row in purchase["details"]
                ]
            },
        )
    await _place_receipt(ctx, UUID(str(purchase_id)))


async def _dock(ctx: Context) -> UUID:
    from app.infrastructure.models.organization import Location

    location_id = await ctx.session.scalar(
        select(Location.id)
        .where(
            Location.warehouse_id == ctx.central.id,
            Location.location_type == "receiving",
            Location.is_active.is_(True),
            Location.lifecycle_status == "active",
            Location.deleted_at.is_(None),
        )
        .order_by(Location.code)
        .limit(1)
    )
    if location_id is None:
        raise RuntimeError("La bodega central no tiene andén de recepción activo.")
    return UUID(str(location_id))


async def _ensure_retaceo(
    ctx: Context, order: OrderSeed, po: Any, purchase_id: str, key: str
) -> None:
    from app.infrastructure.models.retaceo import RetaceoModel

    receipt = order.receipt
    assert receipt is not None
    plan = receipt.retaceo
    ctx.session.expire_all()
    item = await ctx.session.scalar(
        select(RetaceoModel).where(
            RetaceoModel.company_id == COMPANY_ID,
            RetaceoModel.purchase_id == UUID(purchase_id),
            RetaceoModel.status != "cancelled",
        )
    )
    import_data = (
        {
            "origin_country": plan.origin_country,
            "import_invoice_number": receipt.invoice,
            "import_invoice_date": (
                _today() - timedelta(days=receipt.invoice_days_ago)
            ).isoformat(),
            "import_policy_number": plan.import_policy,
            "import_policy_date": (_today() - timedelta(days=2)).isoformat(),
        }
        if plan.origin_country
        else None
    )
    notes = f"{plan.notes} {marker('RET-' + key.removeprefix('REC-'))}"
    if item is None:
        retaceo = await ctx.api.call(
            COST_ACCOUNTANT,
            "POST",
            "/retaceos",
            json={
                "purchase_id": purchase_id,
                "import_data": import_data,
                "total_freight": str(plan.freight),
                "total_dai": str(plan.dai),
                "total_expenses": "0",
                "notes": notes,
            },
        )
        ctx.report.add("retaceos")
        retaceo_id, status = retaceo["id"], retaceo["status"]
        if order.actual and status == "draft":
            await _add_actual_expenses(ctx, retaceo, po, import_data, plan, notes)
    else:
        retaceo_id, status = item.id, item.status
    for current, action, actor in (
        ("draft", "calculate", COST_ACCOUNTANT),
        ("calculated", "verify", ACCOUNTING_CHIEF),
        ("verified", "close", ACCOUNTING_CHIEF),
    ):
        if status == current:
            status = (await ctx.api.call(actor, "POST", f"/retaceos/{retaceo_id}/{action}"))[
                "status"
            ]


async def _add_actual_expenses(
    ctx: Context,
    retaceo: dict[str, Any],
    po: Any,
    import_data: dict[str, Any] | None,
    plan: Any,
    notes: str,
) -> None:
    """Bring the order's actual expenses into the retaceo as additional expenses."""
    actuals = await ctx.api.call(
        COST_ACCOUNTANT, "GET", f"/purchase-orders/{po['id']}/actual-expenses"
    )
    names = {value: key for key, value in ctx.expense_types.items()}
    costs = [
        {
            "id": cost["id"],
            "classification": cost["classification"],
            "title": cost["title"],
            "amount": cost["amount"],
        }
        for cost in retaceo["costs"]
        if cost["is_active"]
    ]
    for row in actuals:
        costs.append(
            {
                "classification": "expense",
                "title": names[UUID(row["expense_type_id"])],
                "description": row["description"],
                "amount": row["amount"],
                "expense_type_id": row["expense_type_id"],
                "source_purchase_order_expense_id": row["id"],
                "incurred_on": row["incurred_on"],
            }
        )
    total = sum((Decimal(row["amount"]) for row in actuals), Decimal("0"))
    await ctx.api.call(
        COST_ACCOUNTANT,
        "PUT",
        f"/retaceos/{retaceo['id']}",
        json={
            "import_data": import_data,
            "total_freight": str(plan.freight),
            "total_dai": str(plan.dai),
            "total_expenses": str(total),
            "notes": notes,
            "costs": costs,
        },
    )


async def _place_receipt(ctx: Context, purchase_id: UUID) -> None:
    """Split into pallets, measure, label and place every pending handling unit."""
    from app.infrastructure.models.inventory import InventoryHandlingUnitModel
    from app.infrastructure.models.inventory_lot import InventoryLotDetailModel, InventoryLotModel

    ctx.session.expire_all()
    lot = _snapshot(
        await ctx.session.scalar(
            select(InventoryLotModel).where(
                InventoryLotModel.company_id == COMPANY_ID,
                InventoryLotModel.purchase_id == purchase_id,
            )
        )
    )
    if lot is None:
        return
    details = {
        row.id: _snapshot(row)
        for row in await ctx.session.scalars(
            select(InventoryLotDetailModel).where(
                InventoryLotDetailModel.inventory_lot_id == lot.id
            )
        )
    }

    async def pending() -> list[Any]:
        ctx.session.expire_all()
        return [
            _snapshot(row)
            for row in await ctx.session.scalars(
                select(InventoryHandlingUnitModel)
                .where(
                    InventoryHandlingUnitModel.inventory_lot_id == lot.id,
                    InventoryHandlingUnitModel.inventory_posted_at.is_(None),
                    InventoryHandlingUnitModel.closed_at.is_(None),
                )
                .order_by(InventoryHandlingUnitModel.created_at, InventoryHandlingUnitModel.code)
            )
        ]

    # 1. One pallet per handling unit.
    for unit in await pending():
        sku = _sku_of(ctx, details[unit.inventory_lot_detail_id].product_id)
        setup = PRODUCTS[sku]
        pallet_base = setup.per_purchase_unit * setup.pallet_units
        quantity = unit.quantity_base
        while quantity > pallet_base:
            await ctx.api.call(
                CENTRAL_MANAGER,
                "POST",
                f"/inventory/preparation/{unit.id}/split",
                json={
                    "idempotency_key": f"glops-split-{unit.id}-{quantity}",
                    "quantity_base": str(pallet_base),
                    "unit_scan": unit.code,
                },
            )
            quantity -= pallet_base
            ctx.report.add("pallet_splits")
    # 2. Measure, label and place each pallet.
    for unit in await pending():
        sku = _sku_of(ctx, details[unit.inventory_lot_detail_id].product_id)
        setup = PRODUCTS[sku]
        weight, volume = pallet_measures(sku, unit.quantity_base / setup.per_purchase_unit)
        if unit.measurement_status != "verified":
            await ctx.api.call(
                CENTRAL_MANAGER,
                "PATCH",
                f"/inventory/handling-units/{unit.id}/measurements",
                json={
                    "measures": {"gross_weight_kg": str(weight), "volume_m3": str(volume)},
                    "source": "manual",
                },
            )
        ctx.session.expire_all()
        unit = _snapshot(  # noqa: PLW2901 - the measured unit has a new label revision
            await ctx.session.get(InventoryHandlingUnitModel, unit.id)
        )
        printed = await ctx.api.call(
            CENTRAL_MANAGER,
            "POST",
            "/inventory/labels/prints",
            json={
                "idempotency_key": f"glops-print-{unit.id}-{unit.label_revision}",
                "handling_unit_id": str(unit.id),
                "quantity_printed": 2,
                "print_date": _today().isoformat(),
                "reason": "initial",
            },
        )
        await ctx.api.call(
            CENTRAL_MANAGER,
            "POST",
            "/inventory/labels/confirmations",
            json={
                "idempotency_key": f"glops-label-{unit.id}-{unit.label_revision}",
                "handling_unit_id": str(unit.id),
                "handling_unit_code": unit.code,
                "label_print_id": printed["id"],
            },
        )
        destination = await _free_position(ctx, setup.zone)
        await ctx.api.call(
            CENTRAL_MANAGER,
            "POST",
            f"/inventory/preparation/{unit.id}/place",
            json={
                "idempotency_key": f"glops-place-{unit.id}",
                "quantity_base": str(unit.quantity_base),
                "unit_scan": unit.code,
                "location_scan": destination,
            },
        )
        ctx.report.add("pallets_placed")


async def _free_position(ctx: Context, zone: str) -> str:
    from app.infrastructure.models.inventory import InventoryHandlingUnitModel
    from app.infrastructure.models.organization import Location

    ctx.session.expire_all()
    occupied = (
        select(InventoryHandlingUnitModel.location_id)
        .where(
            InventoryHandlingUnitModel.closed_at.is_(None),
            InventoryHandlingUnitModel.quantity_base > 0,
        )
        .scalar_subquery()
    )
    code = await ctx.session.scalar(
        select(Location.code)
        .where(
            Location.warehouse_id == ctx.central.id,
            Location.area == zone,
            Location.storage_eligible.is_(True),
            Location.is_active.is_(True),
            Location.lifecycle_status == "active",
            Location.deleted_at.is_(None),
            Location.id.not_in(occupied),
        )
        .order_by(Location.level, Location.aisle, Location.rack, Location.position)
        .limit(1)
    )
    if code is None:
        raise RuntimeError(f"No quedan posiciones libres en la zona {zone} de la bodega central.")
    return str(code)


async def _run_consolidation(ctx: Context, seed: ConsolidationSeed) -> None:
    from app.infrastructure.models.purchase_order import PurchaseOrderModel

    requests = [await _ensure_request(ctx, request) for request in seed.requests]
    consolidation = await _ensure_consolidation(ctx, seed, requests)
    if consolidation.status in {"closed", "cancelled"}:
        orders_done = True
    else:
        orders_done = False
        quotations = await _ensure_quotations(ctx, seed, consolidation)
        if seed.awards:
            await _ensure_awards(ctx, seed, consolidation, quotations)
        for order in seed.orders:
            po = await _ensure_order(ctx, seed, consolidation, order, quotations[order.supplier])
            await _ensure_receipt(ctx, seed, order, po)
        if seed.close:
            await ctx.api.call(
                PURCHASING_ANALYST,
                "POST",
                f"/purchase-consolidations/{consolidation.id}/close",
                json={"reason": "Demanda adjudicada y órdenes de compra emitidas."},
            )
    if orders_done:
        # A closed consolidation may still have orders in transit: finish their steps.
        for order in seed.orders:
            item = await _find(ctx, PurchaseOrderModel, f"OC-{seed.key}-{order.supplier}")
            if item is None:
                continue
            po = await ctx.api.call(PURCHASING_ANALYST, "GET", f"/purchase-orders/{item.id}")
            await _ensure_receipt(ctx, seed, order, po)


# --------------------------------------------------------------------- transfers


async def _transfer_line(ctx: Context, sku: str, quantity: Decimal, reason: str) -> dict[str, Any]:
    """Pick the smallest available pallet in the central warehouse that covers the quantity."""
    from app.infrastructure.models.inventory import InventoryHandlingUnitModel, InventoryItemModel

    unit = await ctx.session.scalar(
        select(InventoryHandlingUnitModel)
        .join(
            InventoryItemModel,
            InventoryItemModel.id == InventoryHandlingUnitModel.inventory_item_id,
        )
        .where(
            InventoryHandlingUnitModel.company_id == COMPANY_ID,
            InventoryHandlingUnitModel.warehouse_id == ctx.central.id,
            InventoryItemModel.product_id == ctx.products[sku].id_product,
            InventoryHandlingUnitModel.stock_status == "available",
            InventoryHandlingUnitModel.inventory_posted_at.is_not(None),
            InventoryHandlingUnitModel.closed_at.is_(None),
            InventoryHandlingUnitModel.quantity_base >= quantity,
        )
        .order_by(InventoryHandlingUnitModel.quantity_base, InventoryHandlingUnitModel.code)
        .limit(1)
    )
    if unit is None:
        raise RuntimeError(f"No hay existencias de {sku} para el traslado.")
    return {
        "handling_unit_id": str(unit.id),
        "quantity_base": str(quantity),
        "demand_allocations": [],
        "excess_reason": reason,
    }


async def _vehicle_and_driver(ctx: Context, code: str) -> tuple[UUID, UUID]:
    from app.infrastructure.models.fleet import FleetVehicleModel, VehicleDriverAssignmentModel

    row = (
        await ctx.session.execute(
            select(FleetVehicleModel.inventory_vehicle_id, VehicleDriverAssignmentModel.driver_id)
            .join(
                VehicleDriverAssignmentModel,
                (VehicleDriverAssignmentModel.vehicle_id == FleetVehicleModel.id)
                & VehicleDriverAssignmentModel.ends_at.is_(None),
            )
            .where(FleetVehicleModel.company_id == COMPANY_ID, FleetVehicleModel.code == code)
        )
    ).one_or_none()
    if row is None or row.inventory_vehicle_id is None:
        raise RuntimeError(f"{code} no tiene conductor asignado ni ubicación de tránsito.")
    return row.inventory_vehicle_id, row.driver_id


async def _reception_location(ctx: Context, warehouse_id: UUID) -> UUID:
    from app.infrastructure.models.organization import Location

    location_id = await ctx.session.scalar(
        select(Location.id)
        .where(
            Location.warehouse_id == warehouse_id,
            Location.location_type.in_(("standard", "bulk", "reserve")),
            Location.storage_eligible.is_(True),
            Location.capacity_profile != "cold",
            Location.is_active.is_(True),
            Location.lifecycle_status == "active",
            Location.deleted_at.is_(None),
        )
        .order_by(Location.code)
        .limit(1)
    )
    if location_id is None:
        raise RuntimeError("La tienda no tiene una ubicación de almacenamiento activa.")
    return UUID(str(location_id))


async def _ensure_transfer(ctx: Context, seed: TransferSeed) -> None:
    """Central distribution to a store: preparation, approval, dispatch and receipt."""
    from app.infrastructure.models.inventory_transfer import InventoryTransferModel

    tag = marker(seed.key)
    item = await _find(ctx, InventoryTransferModel, seed.key)
    destination = ctx.warehouses[seed.destination]
    vehicle_id, driver_id = await _vehicle_and_driver(ctx, seed.vehicle)
    if item is None:
        reason = f"Reposición programada de la bodega central. {tag}"
        transfer = await ctx.api.call(
            CENTRAL_MANAGER,
            "POST",
            "/inventory/transfers",
            json={
                "idempotency_key": f"glops-{seed.key}-create".lower(),
                "origin_warehouse_id": str(ctx.central.id),
                "destination_warehouse_id": str(destination.id),
                "vehicle_id": str(vehicle_id),
                "driver_id": str(driver_id),
                "notes": f"{seed.notes} {tag}",
                "lines": [
                    await _transfer_line(ctx, sku, quantity, reason) for sku, quantity in seed.lines
                ],
            },
        )
        ctx.report.add("transfers")
    else:
        transfer = await ctx.api.call(CENTRAL_MANAGER, "GET", f"/inventory/transfers/{item.id}")
    path = f"/inventory/transfers/{transfer['id']}"
    key = f"glops-{seed.key}".lower()
    planned = sorted(quantity for _sku, quantity in seed.lines)
    if transfer["status"] == "preparation" and planned != sorted(
        Decimal(line["quantity_planned"]) for line in transfer["lines"]
    ):
        # A preparation saved by an earlier version of this seed: edit it as the screen does.
        reason = f"Reposición programada de la bodega central. {tag}"
        transfer = await ctx.api.call(
            CENTRAL_MANAGER,
            "PUT",
            path,
            json={
                "idempotency_key": f"{key}-update-{len(planned)}-{sum(planned)}",
                "origin_warehouse_id": str(ctx.central.id),
                "destination_warehouse_id": str(destination.id),
                "vehicle_id": str(vehicle_id),
                "driver_id": str(driver_id),
                "notes": f"{seed.notes} {tag}",
                "lines": [
                    await _transfer_line(ctx, sku, quantity, reason) for sku, quantity in seed.lines
                ],
            },
        )
    if seed.state == "preparation":
        return
    # Transfers from the central warehouse need no approval: they are dispatched as prepared.
    if transfer["status"] in {"preparation", "approved"}:
        transfer = await ctx.api.call(
            CENTRAL_MANAGER,
            "POST",
            f"{path}/dispatch",
            json={"idempotency_key": f"{key}-dispatch", "vehicle_id": str(vehicle_id)},
        )
    if transfer["status"] == "in_transit":
        location_id = await _reception_location(ctx, destination.id)
        await ctx.api.call(
            REGIONAL_WAREHOUSE_MANAGER,
            "POST",
            f"{path}/receive",
            json={
                "idempotency_key": f"{key}-receive",
                "lines": [
                    {
                        "transfer_detail_id": line["id"],
                        "destination_location_id": str(location_id),
                        "quantity_base": line["quantity_in_transit"],
                    }
                    for line in transfer["lines"]
                ],
            },
        )


# =========================================================================== main


async def seed() -> None:
    from app.infrastructure.db.session import dispose_engine
    from app.infrastructure.models.user import User
    from app.main import create_app
    from httpx import ASGITransport, AsyncClient

    validate_operations_seed()
    report = Report()
    factory = _session_factory()
    async with factory() as session:
        actor = await session.scalar(
            select(User).where(User.username == SUPER_ADMIN_USERNAME, User.deleted_at.is_(None))
        )
        if actor is None:
            raise RuntimeError("Ejecute primero seed_grupo_lorena (falta el superadmin).")
        actor_id = actor.id
        roles = await _ensure_roles(session, actor_id, report)
        branches = await _branches(session)
        employees = await _ensure_staff(
            session, branches=branches, roles=roles, actor_id=actor_id, report=report
        )
        pairs = await _ensure_fleet(
            session,
            branches=branches,
            employees=employees,
            roles=roles,
            actor_id=actor_id,
            report=report,
        )
        await session.commit()
        await _document_and_assign_fleet(session, pairs, actor_id, report)

        tokens = await _tokens(session)
        app = create_app()
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://seed.internal"
            ) as client:
                ctx = Context(
                    session,
                    Api(client, tokens),
                    report,
                    {code: _snapshot(branch) for code, branch in branches.items()},
                    {},
                    {},
                    {},
                    {},
                )
                await _refresh(ctx)
                await _ensure_import_supplier(ctx)
                await _ensure_inventory_setup(ctx)
                await _ensure_central_layout(ctx)
                await _ensure_store_layouts(ctx)
                await _refresh(ctx)
                for consolidation in CONSOLIDATIONS:
                    await _run_consolidation(ctx, consolidation)
                for request in LOOSE_REQUESTS:
                    await _ensure_request(ctx, request)
                for transfer in TRANSFERS:
                    await _ensure_transfer(ctx, transfer)
        finally:
            await dispose_engine()
    created = ", ".join(f"{key}: {value}" for key, value in sorted(report.created.items()))
    print(f"Operación de Grupo Lorena lista. Nuevos -> {created or 'nada (ya estaba al día)'}.")
    for note in report.notes:
        print(f"Nota: {note}")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
