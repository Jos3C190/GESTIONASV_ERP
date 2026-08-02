"""Phase 1 seed.

Idempotent: safe to re-run. Seeds:
- The SUPER_ADMIN user (credentials documented in README).
- A handful of demo users generated with Faker for pagination/search testing.

Permission catalogue and roles arrive in Phase 2 (RBAC). For now we only need
the super-admin so login works end-to-end.
"""

from __future__ import annotations

import asyncio
import os
import sys

import typer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure backend imports work when run via `python -m seed.seed_data`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = typer.Typer(add_completion=False, no_args_is_help=False)

SUPER_ADMIN_USERNAME = os.environ.get("SUPER_ADMIN_USERNAME", "superadmin")
SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "superadmin@erp-system.dev")
SUPER_ADMIN_PASSWORD = os.environ.get(
    "SUPER_ADMIN_PASSWORD",
    "Cambio!Seguro2026",  # documented in README; must be rotated in prod
)


def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    """Build a fresh engine + session factory bound to the current event loop.
    Avoids 'attached to a different loop' errors when the global factory was
    created during app startup in a different loop.
    """
    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def _seed_permissions_and_roles() -> None:
    """Seed the permission catalogue and base roles (idempotent)."""
    from app.application.rbac.catalogue import BASE_ROLES, PERMISSION_CATALOGUE
    from app.core.logging import configure_logging, get_logger
    from app.infrastructure.models.rbac import (
        Permission as ORMPermission,
    )
    from app.infrastructure.models.rbac import (
        Role as ORMRole,
    )
    from app.infrastructure.models.rbac import (
        RolePermission,
    )
    from sqlalchemy import select

    configure_logging()
    log = get_logger("seed")
    factory = _make_session_factory()

    async with factory() as session:
        # 1) Permissions — insert missing codes, skip existing.
        existing_perm_codes = {
            p.code for p in (await session.execute(select(ORMPermission))).scalars().all()
        }
        new_perms = [
            ORMPermission(code=s.code, description=s.description, module=s.module)
            for s in PERMISSION_CATALOGUE
            if s.code not in existing_perm_codes
        ]
        if new_perms:
            session.add_all(new_perms)
            await session.flush()
            log.info("seed_permissions_created", count=len(new_perms))
        else:
            log.info("seed_permissions_skip")

        # Map all codes -> ids for role assignment.
        perm_map: dict[str, object] = {
            p.code: p.id for p in (await session.execute(select(ORMPermission))).scalars().all()
        }

        # 2) Roles — insert missing, assign permissions.
        existing_roles = {
            r.name: r for r in (await session.execute(select(ORMRole))).scalars().all()
        }
        for name, desc, is_system, perm_codes in BASE_ROLES:
            role = existing_roles.get(name)
            if role is None:
                role = ORMRole(name=name, description=desc, is_system=is_system)
                session.add(role)
                await session.flush()
                log.info("seed_role_created", name=name)
            # Assign permissions (clear + set).
            await session.execute(
                __import__("sqlalchemy")
                .delete(RolePermission)
                .where(RolePermission.role_id == role.id)
            )
            for code in perm_codes:
                if code in perm_map:
                    session.add(RolePermission(role_id=role.id, permission_id=perm_map[code]))
        await session.commit()
        log.info("seed_roles_done")


async def _seed_geographic_catalogues() -> None:
    """Seed a minimal valid El Salvador hierarchy for development/testing.

    The catalogues remain read-only through the ERP API. Production deployments
    can replace or extend this data from the authoritative national catalogue.
    """
    from app.infrastructure.models.organization import (
        District,
        GeographicDepartment,
        Municipality,
    )
    from sqlalchemy import select

    factory = _make_session_factory()
    async with factory() as session:
        department = (
            await session.execute(
                select(GeographicDepartment).where(GeographicDepartment.name == "San Salvador")
            )
        ).scalar_one_or_none()
        if department is None:
            department = GeographicDepartment(name="San Salvador")
            session.add(department)
            await session.flush()

        municipality = (
            await session.execute(
                select(Municipality).where(
                    Municipality.department_id == department.id,
                    Municipality.name == "San Salvador Centro",
                )
            )
        ).scalar_one_or_none()
        if municipality is None:
            municipality = Municipality(department_id=department.id, name="San Salvador Centro")
            session.add(municipality)
            await session.flush()

        district = (
            await session.execute(
                select(District).where(
                    District.municipality_id == municipality.id,
                    District.name == "San Salvador",
                )
            )
        ).scalar_one_or_none()
        if district is None:
            session.add(
                District(
                    municipality_id=municipality.id,
                    name="San Salvador",
                )
            )
        await session.commit()


async def _seed_super_admin() -> None:
    from app.core.logging import configure_logging, get_logger
    from app.core.security import hash_password
    from app.infrastructure.models.employee import Employee
    from app.infrastructure.models.organization import Company, UserCompany
    from app.infrastructure.models.user import User as ORMUser
    from sqlalchemy import select

    configure_logging()
    log = get_logger("seed")
    factory = _make_session_factory()

    async with factory() as session:
        existing = (
            await session.execute(select(ORMUser).where(ORMUser.username == SUPER_ADMIN_USERNAME))
        ).scalar_one_or_none()

        if existing is not None:
            log.info("seed_super_admin_exists", username=SUPER_ADMIN_USERNAME)
            return

        orm = ORMUser(
            username=SUPER_ADMIN_USERNAME,
            email=SUPER_ADMIN_EMAIL,
            password_hash=hash_password(SUPER_ADMIN_PASSWORD),
            is_active=True,
            is_superuser=True,
        )
        session.add(orm)
        await session.flush()
        company = (
            await session.execute(
                select(Company).where(Company.is_active.is_(True)).order_by(Company.created_at)
            )
        ).scalars().first()
        if company is None:
            raise RuntimeError("Debe crear la empresa demo antes de sembrar usuarios.")
        session.add(
            UserCompany(
                user_id=orm.id,
                company_id=company.id,
                is_default=True,
                access_all_branches=True,
            )
        )
        session.add(
            Employee(
                company_id=company.id,
                employee_code=f"USR-{orm.id.hex[:12].upper()}",
                first_name="Superadmin",
                last_name="Sistema",
                user_id=orm.id,
                status="activo",
            )
        )
        await session.commit()
        log.info(
            "seed_super_admin_created",
            username=SUPER_ADMIN_USERNAME,
            email=SUPER_ADMIN_EMAIL,
        )


async def _seed_demo_users() -> None:
    """Generate demo users with Faker for pagination/search testing."""
    from app.core.logging import configure_logging, get_logger
    from app.core.security import hash_password
    from app.infrastructure.models.employee import Employee
    from app.infrastructure.models.organization import Company, UserCompany
    from app.infrastructure.models.user import User as ORMUser
    from sqlalchemy import select

    configure_logging()
    log = get_logger("seed")
    fake = __import__("faker").Faker(["es_ES"])
    fake.seed_instance(42)
    password = hash_password("Demo!Usuario2026")
    factory = _make_session_factory()

    async with factory() as session:
        company = (
            await session.execute(
                select(Company).where(Company.is_active.is_(True)).order_by(Company.created_at)
            )
        ).scalars().first()
        if company is None:
            raise RuntimeError("Debe crear la empresa demo antes de sembrar usuarios.")
        existing = (
            (await session.execute(select(ORMUser).where(ORMUser.is_superuser.is_(False))))
            .scalars()
            .all()
        )
        if len(existing) >= 25:
            log.info("seed_demo_users_skip", count=len(existing))
            return

        created = 0
        for _ in range(25):
            username = fake.unique.user_name()
            email = fake.unique.email()
            orm = ORMUser(
                username=username,
                email=email,
                password_hash=password,
                is_active=True,
                is_superuser=False,
            )
            session.add(orm)
            await session.flush()
            session.add(
                UserCompany(
                    user_id=orm.id,
                    company_id=company.id,
                    is_default=True,
                    access_all_branches=True,
                )
            )
            session.add(
                Employee(
                    company_id=company.id,
                    employee_code=f"USR-{orm.id.hex[:12].upper()}",
                    first_name=username,
                    last_name="Usuario demo",
                    user_id=orm.id,
                    status="activo",
                )
            )
            created += 1
        await session.commit()
        log.info("seed_demo_users_created", count=created)


async def _seed_organization_demo() -> None:
    """Seed a usable company context and real Salvadoran map coordinates."""
    from app.infrastructure.models.organization import (
        Branch,
        Company,
        District,
        GeographicDepartment,
        Municipality,
        UserCompany,
        Warehouse,
        WarehouseCategory,
    )
    from app.infrastructure.models.user import User as ORMUser
    from sqlalchemy import select

    factory = _make_session_factory()
    async with factory() as session:
        department = (
            await session.execute(
                select(GeographicDepartment).where(GeographicDepartment.name == "San Salvador")
            )
        ).scalar_one()
        municipality = (
            (
                await session.execute(
                    select(Municipality).where(Municipality.department_id == department.id)
                )
            )
            .scalars()
            .first()
        )
        district = (
            (
                await session.execute(
                    select(District).where(District.municipality_id == municipality.id)
                )
            )
            .scalars()
            .first()
        )
        company = (
            await session.execute(select(Company).where(Company.nit == "0614-010101-001-0"))
        ).scalar_one_or_none()
        if company is None:
            company = Company(
                name="ERP System, S.A. de C.V.",
                commercial_name="ERP System",
                nit="0614-010101-001-0",
                nrc="123456-7",
                commercial_line_1="Servicios de tecnología",
                address="Colonia Escalón, San Salvador",
                department_id=department.id,
                municipality_id=municipality.id,
                district_id=district.id,
                phone="+503 2200-0000",
                email="info@erp-system.dev",
                web_site="https://erp-system.dev",
                description="Empresa demostrativa del entorno local.",
            )
            session.add(company)
            await session.flush()

        users = (await session.execute(select(ORMUser))).scalars().all()
        for user in users:
            if await session.get(UserCompany, (user.id, company.id)) is None:
                session.add(UserCompany(user_id=user.id, company_id=company.id, is_default=True))

        branches = (
            ("SAL-01", "Matriz Central", "Colonia Escalón, San Salvador", 13.6989, -89.1914),
            ("SMA-01", "Sucursal San Miguel", "Centro de San Miguel", 13.4833, -88.1833),
            ("STA-01", "Sucursal Santa Ana", "Centro de Santa Ana", 13.9942, -89.5597),
        )
        created_branches: list[Branch] = []
        for code, name, address, latitude, longitude in branches:
            branch = (
                await session.execute(
                    select(Branch).where(Branch.company_id == company.id, Branch.code == code)
                )
            ).scalar_one_or_none()
            if branch is None:
                branch = Branch(
                    company_id=company.id,
                    code=code,
                    name=name,
                    address=address,
                    department_id=department.id,
                    municipality_id=municipality.id,
                    district_id=district.id,
                    latitude=latitude,
                    longitude=longitude,
                    operational_status="active",
                    zone="El Salvador",
                    description=f"Sede operativa {name}.",
                )
                session.add(branch)
                await session.flush()
            created_branches.append(branch)

        category = (
            await session.execute(
                select(WarehouseCategory).where(WarehouseCategory.name == "Producto Terminado")
            )
        ).scalar_one_or_none()
        if category is None:
            category = WarehouseCategory(
                name="Producto Terminado", description="Productos disponibles para despacho"
            )
            session.add(category)
            await session.flush()
        for index, branch in enumerate(created_branches, start=1):
            code = f"ALM-{index:02d}"
            if (
                await session.execute(
                    select(Warehouse).where(
                        Warehouse.branch_id == branch.id, Warehouse.code == code
                    )
                )
            ).scalar_one_or_none() is None:
                session.add(
                    Warehouse(
                        branch_id=branch.id,
                        warehouse_category_id=category.id,
                        code=code,
                        name=f"Almacén {branch.name}",
                        warehouse_type="general",
                        operational_status="active",
                        physical_location="Bodega principal",
                        capacity=1000,
                    )
                )
        await session.commit()


@app.command()
def run(phase0: bool = typer.Option(False, "--phase0", help="Phase 0 placeholder mode.")) -> None:
    if phase0:
        typer.secho("[seed] Phase 0 — no seed data yet.", fg=typer.colors.CYAN)
        return

    typer.secho(
        "[seed] Phase 2 — seeding permissions, roles, super-admin, demo users...",
        fg=typer.colors.CYAN,
    )
    asyncio.run(_seed_permissions_and_roles())
    asyncio.run(_seed_geographic_catalogues())
    asyncio.run(_seed_organization_demo())
    asyncio.run(_seed_super_admin())
    asyncio.run(_seed_demo_users())
    asyncio.run(_seed_organization_demo())
    typer.secho(
        f"[seed] Done. SUPER_ADMIN = {SUPER_ADMIN_USERNAME} / {SUPER_ADMIN_PASSWORD}",
        fg=typer.colors.GREEN,
    )


if __name__ == "__main__":
    app()
