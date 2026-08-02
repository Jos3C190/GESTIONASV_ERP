"""Idempotent development seed for Grupo Lorena.

Public company and branch facts were researched from official/public sources.
Employee identities, user accounts and operational details are fictional and
exist only to provide coherent development data without impersonating real
people.  Seeded accounts receive an unrecoverable random password and must be
reset by an administrator before they can be used.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import sys
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if TYPE_CHECKING:
    from app.infrastructure.models.employee import Department
    from app.infrastructure.models.organization import Branch, Company
    from app.infrastructure.models.rbac import Role
    from app.infrastructure.models.user import User

COMPANY_NIT = "1217-060102-101-1"
SUPER_ADMIN_USERNAME = os.environ.get("SUPER_ADMIN_USERNAME", "superadmin")
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@erp-system.dev")
SUPER_ADMIN_EMPLOYEE_CODE = "GL-SYS-001"


@dataclass(frozen=True, slots=True)
class BranchSeed:
    code: str
    name: str
    district: str
    address: str
    latitude: float
    longitude: float
    phone: str
    opening: str
    closing: str
    sunday_opening: str | None = None
    sunday_closing: str | None = None


BRANCHES: tuple[BranchSeed, ...] = (
    BranchSeed(
        "LOR-SM-01",
        "Pastelería Lorena Roosevelt",
        "San Miguel",
        "Avenida Roosevelt Norte No. 407-A, frente al Hospital San Francisco, San Miguel",
        13.4836626,
        -88.1856660,
        "+503 2660-8958",
        "06:30",
        "21:00",
    ),
    BranchSeed(
        "LOR-USU-01",
        "Pastelería Lorena Usulután",
        "Usulután",
        "1.ª Calle Oriente y 8.ª Avenida Sur, Usulután",
        13.3431376,
        -88.4359976,
        "+503 2661-5555",
        "06:30",
        "18:00",
    ),
    BranchSeed(
        "LOR-JIQ-01",
        "Pastelería Lorena Jiquilisco",
        "Jiquilisco",
        "Avenida Rubén Torres Córdova y 2.ª Calle Oriente No. 3, barrio El Centro, Jiquilisco",
        13.3260500,
        -88.5703800,
        "+503 2660-8954",
        "07:00",
        "17:15",
    ),
    BranchSeed(
        "LOR-LU-01",
        "Pastelería Lorena La Unión",
        "La Unión",
        "5.ª Avenida Norte, barrio El Centro, La Unión",
        13.3372311,
        -87.8413651,
        "+503 2660-8950",
        "06:30",
        "18:00",
    ),
    BranchSeed(
        "LOR-SRL-01",
        "Pastelería Lorena Santa Rosa de Lima",
        "Santa Rosa de Lima",
        "Calle Ruta Militar, barrio El Calvario, Santa Rosa de Lima",
        13.6278100,
        -87.8928800,
        "+503 2660-8949",
        "06:30",
        "18:00",
    ),
    BranchSeed(
        "LOR-GOT-01",
        "Pastelería Lorena San Francisco Gotera",
        "San Francisco Gotera",
        "Avenida Thomson Norte No. 18, barrio La Cruz, San Francisco Gotera",
        13.6968106,
        -88.1022245,
        "+503 2660-8947",
        "06:00",
        "17:30",
        "06:00",
        "16:00",
    ),
    BranchSeed(
        "LOR-ET-01",
        "Pastelería Lorena El Tránsito",
        "El Tránsito",
        "Centro Comercial 12 de Marzo, calle José Matías Delgado y 1.ª Avenida Norte No. 9, El Tránsito",
        13.3547920,
        -88.3485069,
        "+503 2660-8951",
        "08:00",
        "18:00",
    ),
)


DEPARTMENTS: tuple[tuple[str, str | None, str], ...] = (
    ("Dirección General", None, "Dirección estratégica y gobierno corporativo."),
    ("Operaciones", "Dirección General", "Coordinación de tiendas y continuidad operativa."),
    ("Producción", "Operaciones", "Elaboración de panadería, pastelería y alimentos."),
    ("Calidad e Inocuidad", "Operaciones", "Control sanitario y aseguramiento de la calidad."),
    ("Comercial y Mercadeo", "Dirección General", "Ventas, marca y experiencia del cliente."),
    ("Servicio al Cliente", "Comercial y Mercadeo", "Atención y seguimiento al consumidor."),
    ("Compras y Abastecimiento", "Dirección General", "Adquisición de materias primas e insumos."),
    ("Logística y Distribución", "Operaciones", "Distribución y reposición entre sucursales."),
    (
        "Finanzas y Contabilidad",
        "Dirección General",
        "Tesorería, contabilidad y control financiero.",
    ),
    ("Talento Humano", "Dirección General", "Gestión y desarrollo de colaboradores."),
    ("Tecnología", "Dirección General", "Sistemas, soporte y seguridad de la información."),
    ("Mantenimiento", "Operaciones", "Mantenimiento preventivo de instalaciones y equipos."),
)


ROLE_PERMISSIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "ADMINISTRADOR DE OPERACIONES": (
        "Administración operativa de sucursales, almacenes y personal.",
        (
            "companies.view",
            "branches.view",
            "branches.create",
            "branches.update",
            "branches.activate",
            "branches.deactivate",
            "warehouse_categories.view",
            "warehouse_categories.create",
            "warehouse_categories.update",
            "warehouses.view",
            "warehouses.create",
            "warehouses.update",
            "warehouses.activate",
            "warehouses.deactivate",
            "locations.view",
            "locations.create",
            "locations.update",
            "employees:read",
            "employees:update",
            "audit_log:read",
            "logs.view",
            "logs.detail",
        ),
    ),
    "GERENTE DE SUCURSAL": (
        "Gestión de una sucursal y consulta de su equipo e inventario.",
        (
            "companies.view",
            "branches.view",
            "branches.update",
            "warehouse_categories.view",
            "warehouses.view",
            "warehouses.update",
            "locations.view",
            "employees:read",
        ),
    ),
    "JEFE DE ALMACÉN": (
        "Control de almacenes, ubicaciones y disponibilidad operativa.",
        (
            "branches.view",
            "warehouse_categories.view",
            "warehouses.view",
            "warehouses.create",
            "warehouses.update",
            "warehouses.activate",
            "warehouses.deactivate",
            "locations.view",
            "locations.create",
            "locations.update",
            "locations.activate",
            "locations.deactivate",
            "employees:read",
        ),
    ),
    "AUDITOR INTERNO": (
        "Consulta de estructura organizativa y trazabilidad de operaciones.",
        (
            "companies.view",
            "branches.view",
            "warehouse_categories.view",
            "warehouses.view",
            "locations.view",
            "employees:read",
            "roles:read",
            "permissions:read",
            "audit_log:read",
            "logs.view",
            "logs.detail",
            "logs.export",
        ),
    ),
}


EMPLOYEES: tuple[dict[str, str | bool], ...] = (
    {
        "code": "GL-0001",
        "first": "Mariana Beatriz",
        "last": "Orellana Cruz",
        "department": "Operaciones",
        "position": "Directora de Operaciones",
        "branch": "LOR-SM-01",
        "username": "mariana.orellana",
        "role": "ADMINISTRADOR DE OPERACIONES",
        "all_branches": True,
    },
    {
        "code": "GL-0002",
        "first": "Andrea Sofía",
        "last": "Menjívar Rivas",
        "department": "Talento Humano",
        "position": "Coordinadora de Talento Humano",
        "branch": "LOR-SM-01",
        "username": "andrea.menjivar",
        "role": "RECURSOS_HUMANOS",
        "all_branches": True,
    },
    {
        "code": "GL-0003",
        "first": "Ricardo Antonio",
        "last": "Portillo Lemus",
        "department": "Logística y Distribución",
        "position": "Coordinador de Distribución",
        "branch": "LOR-SM-01",
        "username": "ricardo.portillo",
        "role": "JEFE DE ALMACÉN",
        "all_branches": True,
    },
    {
        "code": "GL-0004",
        "first": "Claudia Marcela",
        "last": "Romero Abarca",
        "department": "Finanzas y Contabilidad",
        "position": "Auditora Interna",
        "branch": "LOR-SM-01",
        "username": "claudia.romero",
        "role": "AUDITOR INTERNO",
        "all_branches": True,
    },
    {
        "code": "GL-0005",
        "first": "José Mauricio",
        "last": "Hernández Pineda",
        "department": "Operaciones",
        "position": "Gerente de Sucursal",
        "branch": "LOR-SM-01",
        "username": "mauricio.hernandez",
        "role": "GERENTE DE SUCURSAL",
        "all_branches": False,
    },
    {
        "code": "GL-0006",
        "first": "Karla Patricia",
        "last": "Argueta Molina",
        "department": "Operaciones",
        "position": "Gerente de Sucursal",
        "branch": "LOR-USU-01",
        "username": "karla.argueta",
        "role": "GERENTE DE SUCURSAL",
        "all_branches": False,
    },
    {
        "code": "GL-0007",
        "first": "Luis Fernando",
        "last": "Benítez Sorto",
        "department": "Operaciones",
        "position": "Gerente de Sucursal",
        "branch": "LOR-JIQ-01",
        "username": "fernando.benitez",
        "role": "GERENTE DE SUCURSAL",
        "all_branches": False,
    },
    {
        "code": "GL-0008",
        "first": "Elena Marisol",
        "last": "Quintanilla Reyes",
        "department": "Operaciones",
        "position": "Gerente de Sucursal",
        "branch": "LOR-LU-01",
        "username": "elena.quintanilla",
        "role": "GERENTE DE SUCURSAL",
        "all_branches": False,
    },
    {
        "code": "GL-0009",
        "first": "Óscar Armando",
        "last": "Villatoro Flores",
        "department": "Operaciones",
        "position": "Gerente de Sucursal",
        "branch": "LOR-SRL-01",
        "username": "oscar.villatoro",
        "role": "GERENTE DE SUCURSAL",
        "all_branches": False,
    },
    {
        "code": "GL-0010",
        "first": "Verónica Alejandra",
        "last": "Chicas Bonilla",
        "department": "Operaciones",
        "position": "Gerente de Sucursal",
        "branch": "LOR-GOT-01",
        "username": "veronica.chicas",
        "role": "GERENTE DE SUCURSAL",
        "all_branches": False,
    },
    {
        "code": "GL-0011",
        "first": "Carlos Ernesto",
        "last": "Amaya Fuentes",
        "department": "Operaciones",
        "position": "Gerente de Sucursal",
        "branch": "LOR-ET-01",
        "username": "carlos.amaya",
        "role": "GERENTE DE SUCURSAL",
        "all_branches": False,
    },
    {
        "code": "GL-0012",
        "first": "Diana Carolina",
        "last": "Campos Guardado",
        "department": "Logística y Distribución",
        "position": "Jefa de Almacén Regional",
        "branch": "LOR-SM-01",
        "username": "diana.campos",
        "role": "JEFE DE ALMACÉN",
        "all_branches": True,
    },
    {
        "code": "GL-0013",
        "first": "Gabriel Alejandro",
        "last": "Escobar Zelaya",
        "department": "Servicio al Cliente",
        "position": "Encargado de Servicio",
        "branch": "LOR-SM-01",
    },
    {
        "code": "GL-0014",
        "first": "Natalia Isabel",
        "last": "Márquez López",
        "department": "Comercial y Mercadeo",
        "position": "Asesora de Ventas",
        "branch": "LOR-SM-01",
    },
    {
        "code": "GL-0015",
        "first": "Miguel Ángel",
        "last": "Pérez Granados",
        "department": "Servicio al Cliente",
        "position": "Encargado de Servicio",
        "branch": "LOR-USU-01",
    },
    {
        "code": "GL-0016",
        "first": "Silvia Roxana",
        "last": "Guevara Ortiz",
        "department": "Comercial y Mercadeo",
        "position": "Asesora de Ventas",
        "branch": "LOR-USU-01",
    },
    {
        "code": "GL-0017",
        "first": "Daniel Enrique",
        "last": "Navarro Mejía",
        "department": "Servicio al Cliente",
        "position": "Encargado de Servicio",
        "branch": "LOR-JIQ-01",
    },
    {
        "code": "GL-0018",
        "first": "Melissa Abigail",
        "last": "Cáceres Arévalo",
        "department": "Comercial y Mercadeo",
        "position": "Asesora de Ventas",
        "branch": "LOR-JIQ-01",
    },
    {
        "code": "GL-0019",
        "first": "Jorge Alberto",
        "last": "Paniagua Santos",
        "department": "Servicio al Cliente",
        "position": "Encargado de Servicio",
        "branch": "LOR-LU-01",
    },
    {
        "code": "GL-0020",
        "first": "Rebeca Lissette",
        "last": "Martínez Alfaro",
        "department": "Comercial y Mercadeo",
        "position": "Asesora de Ventas",
        "branch": "LOR-LU-01",
    },
    {
        "code": "GL-0021",
        "first": "Samuel David",
        "last": "Coreas Ventura",
        "department": "Servicio al Cliente",
        "position": "Encargado de Servicio",
        "branch": "LOR-SRL-01",
    },
    {
        "code": "GL-0022",
        "first": "Paola Fernanda",
        "last": "López Villacorta",
        "department": "Comercial y Mercadeo",
        "position": "Asesora de Ventas",
        "branch": "LOR-SRL-01",
    },
    {
        "code": "GL-0023",
        "first": "Roberto Carlos",
        "last": "Díaz Salgado",
        "department": "Servicio al Cliente",
        "position": "Encargado de Servicio",
        "branch": "LOR-GOT-01",
    },
    {
        "code": "GL-0024",
        "first": "Fátima Lucía",
        "last": "Membreño Ávila",
        "department": "Comercial y Mercadeo",
        "position": "Asesora de Ventas",
        "branch": "LOR-GOT-01",
    },
    {
        "code": "GL-0025",
        "first": "Kevin Eduardo",
        "last": "Ramos Aparicio",
        "department": "Servicio al Cliente",
        "position": "Encargado de Servicio",
        "branch": "LOR-ET-01",
    },
    {
        "code": "GL-0026",
        "first": "Mónica Patricia",
        "last": "Velásquez Torres",
        "department": "Comercial y Mercadeo",
        "position": "Asesora de Ventas",
        "branch": "LOR-ET-01",
    },
)


def validate_seed_data() -> None:
    """Fail fast if a future edit introduces duplicate or invalid seed data."""
    from app.application.rbac.catalogue import ALL_PERMISSION_CODES, BASE_ROLES

    branch_codes = [branch.code for branch in BRANCHES]
    employee_codes = [str(employee["code"]) for employee in EMPLOYEES]
    usernames = [str(employee["username"]) for employee in EMPLOYEES if "username" in employee]
    department_names = {name for name, _parent, _description in DEPARTMENTS}
    available_roles = {name for name, _description, _system, _permissions in BASE_ROLES}
    available_roles.update(ROLE_PERMISSIONS)
    if len(branch_codes) != len(set(branch_codes)):
        raise ValueError("Los códigos de sucursal deben ser únicos.")
    if len(employee_codes) != len(set(employee_codes)):
        raise ValueError("Los códigos de empleado deben ser únicos.")
    if len(usernames) != len(set(usernames)):
        raise ValueError("Los nombres de usuario deben ser únicos.")
    if any(
        not (-90 <= branch.latitude <= 90 and -180 <= branch.longitude <= 180)
        for branch in BRANCHES
    ):
        raise ValueError("Una o más coordenadas de sucursal no son válidas.")
    unknown_branches = {
        str(employee["branch"]) for employee in EMPLOYEES if employee["branch"] not in branch_codes
    }
    if unknown_branches:
        raise ValueError(f"Empleados con sucursales desconocidas: {sorted(unknown_branches)}")
    unknown_departments = {
        str(employee["department"])
        for employee in EMPLOYEES
        if employee["department"] not in department_names
    }
    if unknown_departments:
        raise ValueError(f"Empleados con departamentos desconocidos: {sorted(unknown_departments)}")
    unknown_roles = {
        str(employee["role"])
        for employee in EMPLOYEES
        if "role" in employee and employee["role"] not in available_roles
    }
    if unknown_roles:
        raise ValueError(f"Empleados con roles desconocidos: {sorted(unknown_roles)}")
    unknown_permissions = {
        code
        for _description, permission_codes in ROLE_PERMISSIONS.values()
        for code in permission_codes
        if code not in ALL_PERMISSION_CODES
    }
    if unknown_permissions:
        raise ValueError(f"Permisos empresariales desconocidos: {sorted(unknown_permissions)}")


def _session_factory() -> async_sessionmaker[AsyncSession]:
    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def _seed_rbac(session: AsyncSession) -> dict[str, Role]:
    """Upsert the audited permission catalogue and all base roles."""
    from app.application.rbac.catalogue import BASE_ROLES, PERMISSION_CATALOGUE
    from app.infrastructure.models.rbac import Permission, Role, RolePermission

    permissions = {
        item.code: item for item in (await session.execute(select(Permission))).scalars().all()
    }
    for specification in PERMISSION_CATALOGUE:
        permission = permissions.get(specification.code)
        if permission is None:
            permission = Permission(code=specification.code)
            session.add(permission)
            permissions[specification.code] = permission
        permission.description = specification.description
        permission.module = specification.module
    await session.flush()

    roles = {item.name: item for item in (await session.execute(select(Role))).scalars().all()}
    for role_name, description, is_system, permission_codes in BASE_ROLES:
        role = roles.get(role_name)
        if role is None:
            role = Role(name=role_name)
            session.add(role)
            await session.flush()
            roles[role_name] = role
        role.description = description
        role.is_system = is_system
        await session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        for code in permission_codes:
            permission = permissions.get(code)
            if permission is None:
                raise RuntimeError(f"No existe el permiso requerido por {role_name}: {code}")
            session.add(RolePermission(role_id=role.id, permission_id=permission.id))
    await session.flush()
    return roles


async def _ensure_superadmin(session: AsyncSession, roles: dict[str, Role]) -> User:
    """Create the technical administrator once without rotating its password."""
    from app.core.security import hash_password
    from app.infrastructure.models.rbac import Role, UserRole
    from app.infrastructure.models.user import User

    user = (
        await session.execute(select(User).where(User.username == SUPER_ADMIN_USERNAME))
    ).scalar_one_or_none()
    if user is None:
        password = os.environ.get("SUPER_ADMIN_PASSWORD")
        if not password:
            raise RuntimeError(
                "SUPER_ADMIN_PASSWORD es obligatoria para inicializar una base de datos nueva."
            )
        user = User(
            username=SUPER_ADMIN_USERNAME,
            email=SUPER_ADMIN_EMAIL,
            password_hash=hash_password(password),
            is_active=True,
            is_superuser=True,
        )
        session.add(user)
        await session.flush()
    else:
        user.is_active = True
        user.is_superuser = True
        user.deleted_at = None

    superadmin_role = roles.get("SUPER_ADMIN")
    if not isinstance(superadmin_role, Role):
        raise TypeError("No se pudo inicializar el rol SUPER_ADMIN.")
    if await session.get(UserRole, (user.id, superadmin_role.id)) is None:
        session.add(UserRole(user_id=user.id, role_id=superadmin_role.id, assigned_by=user.id))
    return user


async def _attach_superadmin_to_company(
    session: AsyncSession,
    *,
    user: User,
    company: Company,
    technology_department: Department,
    headquarters_branch: Branch,
) -> None:
    """Ensure the bootstrap account satisfies user/employee/company invariants."""
    from app.infrastructure.models.employee import Employee
    from app.infrastructure.models.organization import Branch, Company, UserCompany
    from app.infrastructure.models.user import User

    if not isinstance(user, User) or not isinstance(company, Company):
        raise TypeError("El usuario y la empresa de bootstrap no son válidos.")
    if not isinstance(headquarters_branch, Branch):
        raise TypeError("La sucursal principal de bootstrap no es válida.")

    membership = await session.get(UserCompany, (user.id, company.id))
    if membership is None:
        membership = UserCompany(user_id=user.id, company_id=company.id, is_default=True)
        session.add(membership)
    membership.is_default = True
    membership.access_all_branches = True
    membership.last_branch_id = headquarters_branch.id

    employee = (
        await session.execute(select(Employee).where(Employee.user_id == user.id))
    ).scalar_one_or_none()
    if employee is None:
        employee = (
            await session.execute(
                select(Employee).where(
                    Employee.company_id == company.id,
                    Employee.employee_code == SUPER_ADMIN_EMPLOYEE_CODE,
                )
            )
        ).scalar_one_or_none()
    if employee is None:
        employee = Employee(company_id=company.id, employee_code=SUPER_ADMIN_EMPLOYEE_CODE)
        session.add(employee)
    employee.company_id = company.id
    employee.employee_code = SUPER_ADMIN_EMPLOYEE_CODE
    employee.first_name = "Administrador"
    employee.last_name = "del Sistema"
    employee.position = "Administración de plataforma ERP"
    employee.department_id = technology_department.id
    employee.user_id = user.id
    employee.status = "activo"
    employee.deleted_at = None


def _schedule(branch: BranchSeed) -> list[dict[str, str | None]]:
    schedule = [
        {"day": day, "open": branch.opening, "close": branch.closing}
        for day in ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado")
    ]
    schedule.append(
        {
            "day": "Domingo",
            "open": branch.sunday_opening or branch.opening,
            "close": branch.sunday_closing or branch.closing,
        }
    )
    return schedule


async def seed() -> None:  # noqa: C901 - explicit orchestration keeps the seed transaction atomic
    from app.core.security import hash_password
    from app.infrastructure.models.audit import AuditLog
    from app.infrastructure.models.employee import (
        Department,
        DepartmentBranchAssignment,
        Employee,
        EmployeeBranchAssignment,
    )
    from app.infrastructure.models.organization import (
        Branch,
        Company,
        District,
        Location,
        Municipality,
        UserBranch,
        UserCompany,
        Warehouse,
        WarehouseCategory,
    )
    from app.infrastructure.models.rbac import Permission, Role, RolePermission, UserRole
    from app.infrastructure.models.user import User

    validate_seed_data()
    factory = _session_factory()
    async with factory() as session:
        roles = await _seed_rbac(session)
        superadmin = await _ensure_superadmin(session, roles)
        superadmin_id = superadmin.id

        # Remove only unused automated test roles. System and assigned roles stay intact.
        used_role_ids = select(UserRole.role_id)
        await session.execute(
            delete(Role).where(
                Role.id.not_in(used_role_ids),
                Role.is_system.is_(False),
                Role.name.op("~")(r"^(CUSTOM_|PERM_)[0-9A-Fa-f]+$"),
            )
        )

        permissions = {
            item.code: item for item in (await session.execute(select(Permission))).scalars().all()
        }
        for role_name, (description, permission_codes) in ROLE_PERMISSIONS.items():
            role = roles.get(role_name)
            if role is None:
                role = Role(name=role_name, description=description, is_system=False)
                session.add(role)
                await session.flush()
                roles[role_name] = role
            else:
                role.description = description
            await session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
            for code in permission_codes:
                permission = permissions.get(code)
                if permission is None:
                    raise RuntimeError(f"No existe el permiso requerido: {code}")
                session.add(RolePermission(role_id=role.id, permission_id=permission.id))

        district_rows = (
            await session.execute(
                select(District, Municipality)
                .join(Municipality, Municipality.id == District.municipality_id)
                .where(District.name.in_({branch.district for branch in BRANCHES} | {"San Miguel"}))
            )
        ).all()
        geography = {
            district.name: (district, municipality) for district, municipality in district_rows
        }
        missing_districts = {branch.district for branch in BRANCHES} - geography.keys()
        if missing_districts:
            raise RuntimeError(f"Faltan distritos oficiales: {sorted(missing_districts)}")

        headquarters_district, headquarters_municipality = geography["San Miguel"]
        company = (
            await session.execute(select(Company).where(Company.nit == COMPANY_NIT))
        ).scalar_one_or_none()
        company_created = company is None
        if company is None:
            company = Company(nit=COMPANY_NIT)
            session.add(company)
        company.name = "Grupo Lorena, S.A. de C.V."
        company.commercial_name = "Grupo Lorena"
        company.nrc = "Pendiente de verificación"
        company.commercial_line_1 = "Panadería y pastelería"
        company.commercial_line_2 = "Servicios de alimentos y bebidas"
        company.commercial_line_3 = "Restaurantes y hospitalidad"
        company.address = "3.ª Calle Poniente No. 21, colonia Ciudad Jardín, San Miguel"
        company.department_id = headquarters_municipality.department_id
        company.municipality_id = headquarters_municipality.id
        company.district_id = headquarters_district.id
        company.phone = "+503 2660-8900"
        company.email = None
        company.web_site = "https://grupolorena.com.sv/"
        company.description = (
            "Empresa salvadoreña de alimentos y bebidas fundada en San Miguel el 16 de diciembre "
            "de 1981. Matrícula de empresa 2002037095."
        )
        company.is_active = True
        await session.flush()

        if company_created:
            session.add(
                AuditLog(
                    user_id=superadmin_id,
                    company_id=company.id,
                    action="CREATE",
                    resource_type="companies",
                    resource_id=str(company.id),
                    after_state={"name": company.name, "commercial_name": company.commercial_name},
                    status="success",
                    metadata_={"source": "seed_grupo_lorena", "facts": "publicly_researched"},
                )
            )

        departments: dict[str, Department] = {}
        for name, _parent, description in DEPARTMENTS:
            department = (
                await session.execute(
                    select(Department).where(
                        Department.company_id == company.id, Department.name == name
                    )
                )
            ).scalar_one_or_none()
            if department is None:
                department = Department(company_id=company.id, name=name, description=description)
                session.add(department)
                await session.flush()
                session.add(
                    AuditLog(
                        user_id=superadmin_id,
                        company_id=company.id,
                        action="CREATE",
                        resource_type="departments",
                        resource_id=str(department.id),
                        after_state={"name": name},
                        status="success",
                        metadata_={"source": "seed_grupo_lorena"},
                    )
                )
            else:
                department.description = description
            departments[name] = department
        for name, parent_name, _description in DEPARTMENTS:
            departments[name].parent_department_id = (
                departments[parent_name].id if parent_name else None
            )

        branches: dict[str, Branch] = {}
        for branch_seed in BRANCHES:
            district, municipality = geography[branch_seed.district]
            branch = (
                await session.execute(
                    select(Branch).where(
                        Branch.company_id == company.id, Branch.code == branch_seed.code
                    )
                )
            ).scalar_one_or_none()
            branch_created = branch is None
            if branch is None:
                branch = Branch(company_id=company.id, code=branch_seed.code)
                session.add(branch)
            branch.name = branch_seed.name
            branch.address = branch_seed.address
            branch.department_id = municipality.department_id
            branch.municipality_id = municipality.id
            branch.district_id = district.id
            branch.phone = branch_seed.phone
            branch.email = None
            branch.latitude = branch_seed.latitude
            branch.longitude = branch_seed.longitude
            branch.operational_status = "active"
            branch.description = "Sucursal de atención, cafetería y venta de productos Lorena."
            branch.schedule = _schedule(branch_seed)
            branch.zone = "Zona oriental"
            branch.services = ["Venta en tienda", "Cafetería", "Pedidos para llevar"]
            branch.facilities = ["Área de atención", "Vitrina refrigerada", "Bodega de tienda"]
            branch.accessibility = ["Acceso a nivel"]
            branch.property_type = "alquilado"
            branch.building_condition = "bueno"
            branch.internet_type = "fibra"
            branch.water_source = "red_publica"
            branch.ac_system = "mini_split"
            branch.lighting = "led"
            branch.access_control = "sin_control"
            branch.fire_system = ["Extintores", "Señalización de evacuación"]
            branch.has_alarm = True
            branch.floor_material = "porcelanato"
            branch.exterior_material = "mixta"
            branch.is_active = True
            await session.flush()
            branches[branch_seed.code] = branch
            if branch_created:
                session.add(
                    AuditLog(
                        user_id=superadmin_id,
                        company_id=company.id,
                        branch_id=branch.id,
                        action="CREATE",
                        resource_type="branches",
                        resource_id=str(branch.id),
                        after_state={"code": branch.code, "name": branch.name},
                        status="success",
                        metadata_={"source": "seed_grupo_lorena", "location": "public_listing"},
                    )
                )

        await _attach_superadmin_to_company(
            session,
            user=superadmin,
            company=company,
            technology_department=departments["Tecnología"],
            headquarters_branch=branches["LOR-SM-01"],
        )

        category_specs = {
            "Inventario de tienda": "Productos e insumos disponibles para operación diaria de la sucursal.",
            "Producto terminado": "Panadería, pastelería y alimentos listos para distribución o venta.",
            "Materia prima": "Harinas, azúcar, lácteos y demás insumos de producción.",
            "Empaque y suministros": "Cajas, bolsas, etiquetas y materiales de servicio.",
        }
        categories: dict[str, WarehouseCategory] = {}
        for name, description in category_specs.items():
            category = (
                await session.execute(
                    select(WarehouseCategory).where(
                        WarehouseCategory.company_id == company.id, WarehouseCategory.name == name
                    )
                )
            ).scalar_one_or_none()
            if category is None:
                category = WarehouseCategory(
                    company_id=company.id, name=name, description=description
                )
                session.add(category)
                await session.flush()
                session.add(
                    AuditLog(
                        user_id=superadmin_id,
                        company_id=company.id,
                        action="CREATE",
                        resource_type="warehouse_categories",
                        resource_id=str(category.id),
                        after_state={"name": name},
                        status="success",
                        metadata_={"source": "seed_grupo_lorena"},
                    )
                )
            else:
                category.description = description
                category.is_active = True
            categories[name] = category

        employees: dict[str, Employee] = {}
        random_password_hash = hash_password(secrets.token_urlsafe(48))
        for employee_seed in EMPLOYEES:
            code = str(employee_seed["code"])
            employee = (
                await session.execute(
                    select(Employee).where(
                        Employee.company_id == company.id, Employee.employee_code == code
                    )
                )
            ).scalar_one_or_none()
            employee_created = employee is None
            if employee is None:
                employee = Employee(company_id=company.id, employee_code=code)
                session.add(employee)
            employee.first_name = str(employee_seed["first"])
            employee.last_name = str(employee_seed["last"])
            employee.department_id = departments[str(employee_seed["department"])].id
            employee.position = str(employee_seed["position"])
            employee.hire_date = date(
                2022 + (int(code[-2:]) % 4), ((int(code[-2:]) - 1) % 12) + 1, 1
            )
            employee.status = "activo"
            employee.deleted_at = None
            await session.flush()
            employees[code] = employee

            username = employee_seed.get("username")
            if username:
                username = str(username)
                user = (
                    await session.execute(select(User).where(User.username == username))
                ).scalar_one_or_none()
                if user is None:
                    user = User(
                        username=username,
                        email=f"{username}@grupo-lorena.example",
                        password_hash=random_password_hash,
                        is_active=True,
                        is_superuser=False,
                    )
                    session.add(user)
                    await session.flush()
                    session.add(
                        AuditLog(
                            user_id=superadmin_id,
                            company_id=company.id,
                            action="CREATE",
                            resource_type="users",
                            resource_id=str(user.id),
                            after_state={"username": username, "employee_code": code},
                            status="success",
                            metadata_={
                                "source": "seed_grupo_lorena",
                                "password_reset_required": True,
                            },
                        )
                    )
                employee.user_id = user.id
                membership = await session.get(UserCompany, (user.id, company.id))
                if membership is None:
                    membership = UserCompany(
                        user_id=user.id, company_id=company.id, is_default=True
                    )
                    session.add(membership)
                membership.access_all_branches = bool(employee_seed.get("all_branches", False))
                membership.last_branch_id = branches[str(employee_seed["branch"])].id
                role = roles.get(str(employee_seed["role"]))
                if role is None:
                    raise RuntimeError(f"No existe el rol requerido: {employee_seed['role']}")
                if await session.get(UserRole, (user.id, role.id)) is None:
                    session.add(
                        UserRole(user_id=user.id, role_id=role.id, assigned_by=superadmin_id)
                    )
                if not membership.access_all_branches:
                    branch = branches[str(employee_seed["branch"])]
                    user_branch = await session.get(UserBranch, (user.id, branch.id))
                    if user_branch is None:
                        session.add(
                            UserBranch(
                                user_id=user.id,
                                company_id=company.id,
                                branch_id=branch.id,
                                assigned_by=superadmin_id,
                                is_default=True,
                                is_active=True,
                            )
                        )

            if employee_created:
                session.add(
                    AuditLog(
                        user_id=superadmin_id,
                        company_id=company.id,
                        branch_id=branches[str(employee_seed["branch"])].id,
                        action="CREATE",
                        resource_type="employees",
                        resource_id=str(employee.id),
                        after_state={
                            "employee_code": code,
                            "name": f"{employee.first_name} {employee.last_name}",
                            "position": employee.position,
                        },
                        status="success",
                        metadata_={"source": "seed_grupo_lorena", "identity": "fictional"},
                    )
                )

        for employee_seed in EMPLOYEES:
            employee = employees[str(employee_seed["code"])]
            branch = branches[str(employee_seed["branch"])]
            assignment = (
                await session.execute(
                    select(EmployeeBranchAssignment).where(
                        EmployeeBranchAssignment.employee_id == employee.id,
                        EmployeeBranchAssignment.branch_id == branch.id,
                    )
                )
            ).scalar_one_or_none()
            if assignment is None:
                assignment = EmployeeBranchAssignment(employee_id=employee.id, branch_id=branch.id)
                session.add(assignment)
            assignment.is_primary = True
            assignment.position = employee.position
            assignment.shift = "mañana"
            assignment.is_active = True

        manager_by_branch = {
            str(employee["branch"]): employees[str(employee["code"])]
            for employee in EMPLOYEES
            if employee.get("position") == "Gerente de Sucursal"
        }
        for branch_code, manager in manager_by_branch.items():
            branch = branches[branch_code]
            branch.manager_employee_id = manager.id
            for department_name in ("Operaciones", "Comercial y Mercadeo", "Servicio al Cliente"):
                department = departments[department_name]
                assignment = (
                    await session.execute(
                        select(DepartmentBranchAssignment).where(
                            DepartmentBranchAssignment.department_id == department.id,
                            DepartmentBranchAssignment.branch_id == branch.id,
                        )
                    )
                ).scalar_one_or_none()
                if assignment is None:
                    assignment = DepartmentBranchAssignment(
                        department_id=department.id, branch_id=branch.id
                    )
                    session.add(assignment)
                assignment.manager_employee_id = manager.id
                assignment.is_active = True

        warehouses: dict[str, Warehouse] = {}
        for index, branch_seed in enumerate(BRANCHES, start=1):
            branch = branches[branch_seed.code]
            warehouse_code = f"BOD-{branch_seed.code.removeprefix('LOR-')}"
            warehouse = (
                await session.execute(
                    select(Warehouse).where(
                        Warehouse.branch_id == branch.id, Warehouse.code == warehouse_code
                    )
                )
            ).scalar_one_or_none()
            warehouse_created = warehouse is None
            if warehouse is None:
                warehouse = Warehouse(
                    branch_id=branch.id,
                    code=warehouse_code,
                    warehouse_category_id=categories["Inventario de tienda"].id,
                )
                session.add(warehouse)
            warehouse.name = f"Bodega de tienda {branch_seed.district}"
            warehouse.warehouse_category_id = categories["Inventario de tienda"].id
            warehouse.warehouse_type = "general"
            warehouse.operational_status = "active"
            warehouse.physical_location = "Área posterior de la sucursal"
            warehouse.manager_employee_id = manager_by_branch[branch_seed.code].id
            warehouse.area = 45 + index * 3
            warehouse.height = 3.2
            warehouse.shelves_total = 18 + index
            warehouse.capacity = 900 + index * 100
            warehouse.shifts = ["mañana", "tarde"]
            warehouse.cameras = 2
            warehouse.access_control = "teclado"
            warehouse.has_alarm = True
            warehouse.fire_system = ["Extintores", "Detectores de humo"]
            warehouse.temperature_range = "18 °C a 26 °C"
            warehouse.humidity_range = "40 % a 65 %"
            warehouse.cooling = "mixto"
            warehouse.has_ventilation = True
            warehouse.description = (
                "Resguardo de productos terminados, empaques e insumos de atención diaria."
            )
            warehouse.is_active = True
            await session.flush()
            warehouses[warehouse_code] = warehouse
            if warehouse_created:
                session.add(
                    AuditLog(
                        user_id=superadmin_id,
                        company_id=company.id,
                        branch_id=branch.id,
                        action="CREATE",
                        resource_type="warehouses",
                        resource_id=str(warehouse.id),
                        after_state={"code": warehouse.code, "name": warehouse.name},
                        status="success",
                        metadata_={"source": "seed_grupo_lorena"},
                    )
                )

            for location_index, (label, aisle, capacity) in enumerate(
                (("Recepción", "REC", 200), ("Seco", "SEC", 500), ("Empaque", "EMP", 300)), start=1
            ):
                location_code = f"{aisle}-{location_index:02d}"
                location = (
                    await session.execute(
                        select(Location).where(
                            Location.warehouse_id == warehouse.id, Location.code == location_code
                        )
                    )
                ).scalar_one_or_none()
                if location is None:
                    session.add(
                        Location(
                            warehouse_id=warehouse.id,
                            code=location_code,
                            aisle=aisle,
                            rack="R01",
                            level="N01",
                            position=f"P{location_index:02d}",
                            capacity=capacity,
                            notes=f"Zona de {label.lower()} de la bodega.",
                            is_active=True,
                        )
                    )

        await session.commit()
        print(
            f"Grupo Lorena listo: {len(BRANCHES)} sucursales, {len(DEPARTMENTS)} departamentos, "
            f"{len(warehouses)} almacenes y {len(EMPLOYEES)} empleados."
        )


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
