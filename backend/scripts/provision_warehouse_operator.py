"""Provision an explicitly requested warehouse employee with scoped operational access.

Credentials are generated locally and written only to the requested private file.
Existing identities and roles with different permissions are never overwritten.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.security import hash_password
from app.infrastructure.db.session import async_engine
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.employee import Employee, EmployeeBranchAssignment
from app.infrastructure.models.organization import (
    Branch,
    Company,
    UserBranch,
    UserCompany,
    UserWarehouseAccess,
    Warehouse,
)
from app.infrastructure.models.rbac import Permission, Role, RolePermission, UserRole
from app.infrastructure.models.user import User
from pydantic import EmailStr, TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

OPERATOR_PERMISSIONS = (
    "companies.view",
    "branches.view",
    "warehouses.view",
    "locations.view",
    "locations.create",
    "locations.update",
    "locations.labels",
    "inventory:read",
    "inventory:receive",
    "inventory:move",
    "inventory:capacity",
    "inventory:warehouse_receipts",
)


def operator_email(username: str, email: str | None = None) -> str:
    """Use a validated address; example.com is a documentation-only fallback.

    Reserved .invalid addresses cannot be serialized by the auth profile DTO.
    Accept a real address explicitly when provisioning an operational account.
    """
    return str(TypeAdapter(EmailStr).validate_python(email or f"{username}@example.com"))


async def _load_scope(session, args):
    company_id, warehouse_id = uuid.UUID(args.company_id), uuid.UUID(args.warehouse_id)
    warehouse = await session.scalar(
        select(Warehouse).where(
            Warehouse.id == warehouse_id,
            Warehouse.company_id == company_id,
            Warehouse.is_central.is_(True),
            Warehouse.deleted_at.is_(None),
        )
    )
    company = await session.get(Company, company_id)
    if warehouse is None or company is None or warehouse.branch_id is None:
        raise ValueError("Seleccione una bodega matriz con sucursal asignada.")
    branch = await session.get(Branch, warehouse.branch_id)
    if branch is None or not branch.is_headquarters or not branch.is_active:
        raise ValueError("La bodega debe pertenecer a una sucursal matriz activa.")
    actor = await session.scalar(
        select(User).where(
            User.username == args.actor_username,
            User.is_superuser.is_(True),
            User.deleted_at.is_(None),
        )
    )
    if actor is None:
        raise ValueError("No se encontró el actor administrador solicitado.")
    existing = await session.scalar(
        select(User.id).where(
            func.lower(User.username) == args.username.casefold(), User.deleted_at.is_(None)
        )
    )
    if existing is not None:
        raise ValueError("El usuario ya existe. No se modificó su acceso ni su contraseña.")
    return company_id, warehouse, company, branch, actor


async def _operator_role(session, company_id):
    permissions = list(
        await session.scalars(
            select(Permission).where(
                Permission.code.in_(OPERATOR_PERMISSIONS), Permission.deleted_at.is_(None)
            )
        )
    )
    if {permission.code for permission in permissions} != set(OPERATOR_PERMISSIONS):
        raise ValueError(
            "Faltan permisos del catálogo. Aplique las migraciones antes de crear el usuario."
        )
    role = await session.scalar(
        select(Role).where(
            Role.company_id == company_id,
            Role.name == "BODEGUERO PRINCIPAL",
            Role.deleted_at.is_(None),
        )
    )
    if role is None:
        role = Role(
            company_id=company_id,
            name="BODEGUERO PRINCIPAL",
            description="Recepción, medidas, etiquetas y colocación en bodegas expresamente asignadas.",
            is_system=False,
        )
        session.add(role)
        await session.flush()
        session.add_all(
            RolePermission(role_id=role.id, permission_id=permission.id)
            for permission in permissions
        )
    else:
        granted = set(
            await session.scalars(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role.id)
            )
        )
        if granted != set(OPERATOR_PERMISSIONS):
            raise ValueError(
                "El rol existente tiene otros permisos; se requiere una revisión explícita."
            )
    return role


async def _employee_code(session, args, company_id):
    employee_code = args.employee_code
    if await session.scalar(
        select(Employee.id).where(
            Employee.company_id == company_id,
            Employee.employee_code == employee_code,
            Employee.deleted_at.is_(None),
        )
    ):
        raise ValueError("El código del empleado ya existe. No se modificó el empleado anterior.")
    return employee_code


async def provision(args) -> None:
    email = operator_email(args.username, getattr(args, "email", None))
    private_path = Path(args.credentials_file)
    if private_path.exists():
        raise ValueError("El archivo privado de credenciales ya existe; no se sobrescribirá.")
    generated_password = secrets.token_urlsafe(24)
    credential_written = False
    try:
        async with AsyncSession(async_engine, expire_on_commit=False) as session, session.begin():
            company_id, warehouse, company, branch, actor = await _load_scope(session, args)
            role = await _operator_role(session, company_id)
            employee_code = await _employee_code(session, args, company_id)
            user = User(
                username=args.username,
                email=email,
                password_hash=hash_password(generated_password),
                is_active=True,
                is_superuser=False,
            )
            session.add(user)
            await session.flush()
            membership = UserCompany(
                user_id=user.id,
                company_id=company_id,
                is_default=True,
                access_all_branches=False,
                warehouse_restricted=True,
                last_branch_id=branch.id,
            )
            session.add(membership)
            await session.flush()
            session.add_all(
                [
                    UserRole(
                        user_id=user.id,
                        company_id=company_id,
                        role_id=role.id,
                        assigned_by=actor.id,
                    ),
                    UserBranch(
                        user_id=user.id,
                        company_id=company_id,
                        branch_id=branch.id,
                        assigned_by=actor.id,
                        is_default=True,
                        is_active=True,
                    ),
                    UserWarehouseAccess(
                        user_id=user.id, company_id=company_id, warehouse_id=warehouse.id
                    ),
                ]
            )
            today = datetime.now(ZoneInfo("America/El_Salvador")).date()
            employee = Employee(
                company_id=company_id,
                user_id=user.id,
                employee_code=employee_code,
                first_name=args.first_name,
                last_name=args.last_name,
                position="Bodeguero principal",
                hire_date=today,
                status="activo",
            )
            session.add(employee)
            await session.flush()
            session.add(
                EmployeeBranchAssignment(
                    employee_id=employee.id,
                    branch_id=branch.id,
                    is_primary=True,
                    assigned_from=today,
                    position="Bodeguero principal",
                    is_active=True,
                )
            )
            for resource_type, resource_id, state in (
                ("users", user.id, {"username": user.username, "is_superuser": False}),
                (
                    "employees",
                    employee.id,
                    {"name": f"{args.first_name} {args.last_name}", "employee_code": employee_code},
                ),
                (
                    "user_roles",
                    user.id,
                    {
                        "role_id": str(role.id),
                        "permissions": list(OPERATOR_PERMISSIONS),
                        "warehouse_ids": [str(warehouse.id)],
                        "warehouse_restricted": True,
                    },
                ),
            ):
                session.add(
                    AuditLog(
                        user_id=actor.id,
                        company_id=company_id,
                        branch_id=branch.id,
                        action="CREATE",
                        resource_type=resource_type,
                        resource_id=str(resource_id),
                        after_state=state,
                        status="success",
                        metadata_={
                            "source": "provision_warehouse_operator",
                            "authorization": "explicit_user_request",
                        },
                    )
                )
            descriptor = os.open(private_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
                destination.write(
                    f"GestionaSV · Acceso operativo de bodega\nNombre: {args.first_name} {args.last_name}\nUsuario: {args.username}\nContraseña: {generated_password}\nEmpresa: {company.commercial_name}\nBodega: {warehouse.name}\nAcceso: http://localhost:5173/inventory\n"
                )
            credential_written = True
        sys.stdout.write(
            json.dumps(
                {
                    "created_user": args.username,
                    "user_id": str(user.id),
                    "employee_code": employee_code,
                    "warehouse": warehouse.name,
                    "credentials_written": True,
                }
            )
            + "\n"
        )
    except Exception:
        if credential_written:
            private_path.unlink(missing_ok=True)
        raise
    finally:
        await async_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in (
        "company-id",
        "warehouse-id",
        "actor-username",
        "username",
        "first-name",
        "last-name",
        "employee-code",
        "credentials-file",
    ):
        parser.add_argument(f"--{argument}", required=True)
    parser.add_argument("--apply", action="store_true", required=True)
    parser.add_argument(
        "--email", help="Correo del empleado; sin este dato se usa example.com para demostración."
    )
    asyncio.run(provision(parser.parse_args()))


if __name__ == "__main__":
    main()
