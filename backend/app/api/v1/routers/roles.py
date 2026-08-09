"""Roles router — CRUD + permission matrix + user-role assignment.

All endpoints require `permissions:read` or `roles:*` permissions via
`require_permission`. Superusers pass automatically.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.v1.company_access import (
    request_company_id,
    request_company_id_or_default,
    require_company_access,
    require_company_wide_scope,
)
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_permission_repository,
    get_role_repository,
    get_user_repository,
    require_permission,
)
from app.api.v1.schemas.common import MessageOut, Page, PageMeta
from app.api.v1.schemas.rbac import (
    AssignRoleRequest,
    CreatePermissionRequest,
    CreateRoleRequest,
    DuplicateRoleRequest,
    EffectivePermissionsOut,
    PermissionOut,
    RevokeRoleRequest,
    RoleOut,
    RoleWithPermissionsOut,
    SetRolePermissionsRequest,
    UpdatePermissionRequest,
    UpdateRoleRequest,
)
from app.application.audit.audit_service import AuditService, role_to_audit_state
from app.application.rbac.check_permission import GetEffectivePermissionsUseCase
from app.application.rbac.role_assignment import (
    AssignRoleInput,
    AssignRoleUseCase,
    GetUserRolesUseCase,
    RevokeRoleInput,
    RevokeRoleUseCase,
)
from app.application.rbac.role_crud import (
    CreatePermissionInput,
    CreatePermissionUseCase,
    CreateRoleInput,
    CreateRoleUseCase,
    DeletePermissionUseCase,
    DeleteRoleUseCase,
    GetRoleUseCase,
    ListPermissionsUseCase,
    ListRolesUseCase,
    SetRolePermissionsInput,
    SetRolePermissionsUseCase,
    UpdatePermissionInput,
    UpdatePermissionUseCase,
    UpdateRoleInput,
    UpdateRoleUseCase,
)
from app.domain.entities.rbac import Role
from app.domain.ports.permission_repository import PermissionRepository
from app.domain.ports.role_repository import RoleRepository
from app.domain.ports.user_repository import UserRepository
from app.infrastructure.models.organization import UserCompany

router = APIRouter(prefix="/roles", tags=["roles"])


def _role_out(role: Role) -> RoleWithPermissionsOut:
    return RoleWithPermissionsOut(
        id=role.id,
        company_id=role.company_id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        created_at=role.created_at or datetime.now(UTC),
        updated_at=role.updated_at,
        permissions=[
            PermissionOut(id=p.id, code=p.code, description=p.description, module=p.module)
            for p in role.permissions
        ],
    )


@router.get(
    "",
    response_model=Page[RoleWithPermissionsOut],
    status_code=status.HTTP_200_OK,
    summary="Listar roles paginados (con permisos)",
    dependencies=[Depends(require_permission("roles:read"))],
)
async def list_roles(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: RoleRepository = Depends(get_role_repository),
    page: int = Query(1, ge=1),
    size: int = Query(12, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
    is_system: bool | None = Query(None),
    module: str | None = Query(None, max_length=64),
) -> Page[RoleWithPermissionsOut]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    uc = ListRolesUseCase(repo)
    roles, total = await uc.execute_page(
        company_id,
        page=page,
        size=size,
        search=search,
        is_system=is_system,
        module=module,
        load_permissions=True,
    )
    return Page(
        items=[_role_out(role) for role in roles],
        meta=PageMeta(
            page=page,
            size=size,
            total=total,
            pages=(total + size - 1) // size if total else 1,
        ),
    )


@router.get(
    "/catalogue",
    response_model=list[RoleWithPermissionsOut],
    status_code=status.HTTP_200_OK,
    summary="Catálogo completo de roles",
    dependencies=[Depends(require_permission("roles:read"))],
)
async def role_catalogue(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: RoleRepository = Depends(get_role_repository),
) -> list[RoleWithPermissionsOut]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    roles = await ListRolesUseCase(repo).execute(company_id, load_permissions=True)
    return [_role_out(role) for role in roles]


@router.get(
    "/permissions",
    response_model=list[PermissionOut],
    status_code=status.HTTP_200_OK,
    summary="Catálogo de permisos",
    dependencies=[Depends(require_permission("permissions:read"))],
)
async def list_permissions(
    repo: PermissionRepository = Depends(get_permission_repository),
) -> list[PermissionOut]:
    uc = ListPermissionsUseCase(repo)
    perms = await uc.execute()
    return [
        PermissionOut(id=p.id, code=p.code, description=p.description, module=p.module)
        for p in perms
    ]


@router.post(
    "/permissions",
    response_model=PermissionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("permissions:manage"))],
)
async def create_permission(
    body: CreatePermissionRequest,
    current: CurrentUser,
    repo: PermissionRepository = Depends(get_permission_repository),
    audit: AuditService = Depends(get_audit_service),
) -> PermissionOut:
    if not current.is_superuser:
        raise HTTPException(403, "El catálogo global de permisos solo puede modificarlo un superadministrador.")
    permission = await CreatePermissionUseCase(repo).execute(
        CreatePermissionInput(
            code=body.code,
            description=body.description,
            module=body.module,
        )
    )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        resource_type="permissions",
        resource_id=str(permission.id),
        after_state={"code": permission.code, "module": permission.module},
    )
    return PermissionOut.model_validate(permission, from_attributes=True)


@router.patch(
    "/permissions/{permission_id}",
    response_model=PermissionOut,
    dependencies=[Depends(require_permission("permissions:manage"))],
)
async def update_permission(
    permission_id: uuid.UUID,
    body: UpdatePermissionRequest,
    current: CurrentUser,
    repo: PermissionRepository = Depends(get_permission_repository),
    audit: AuditService = Depends(get_audit_service),
) -> PermissionOut:
    if not current.is_superuser:
        raise HTTPException(403, "El catálogo global de permisos solo puede modificarlo un superadministrador.")
    before = await repo.get_by_id(permission_id)
    permission = await UpdatePermissionUseCase(repo).execute(
        UpdatePermissionInput(
            permission_id=permission_id,
            code=body.code,
            description=body.description,
            module=body.module,
        )
    )
    await audit.record(
        action="UPDATE",
        user_id=current.id,
        resource_type="permissions",
        resource_id=str(permission.id),
        before_state=(
            {"code": before.code, "module": before.module} if before else None
        ),
        after_state={"code": permission.code, "module": permission.module},
    )
    return PermissionOut.model_validate(permission, from_attributes=True)


@router.delete(
    "/permissions/{permission_id}",
    response_model=MessageOut,
    dependencies=[Depends(require_permission("permissions:manage"))],
)
async def delete_permission(
    permission_id: uuid.UUID,
    current: CurrentUser,
    repo: PermissionRepository = Depends(get_permission_repository),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    if not current.is_superuser:
        raise HTTPException(403, "El catálogo global de permisos solo puede modificarlo un superadministrador.")
    before = await repo.get_by_id(permission_id)
    await DeletePermissionUseCase(repo).execute(permission_id)
    await audit.record(
        action="DELETE",
        user_id=current.id,
        resource_type="permissions",
        resource_id=str(permission_id),
        before_state=(
            {"code": before.code, "module": before.module} if before else None
        ),
    )
    return MessageOut(message="Permiso eliminado.", code="permission_deleted")


@router.get(
    "/{role_id}",
    response_model=RoleWithPermissionsOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener rol por id (con permisos)",
    dependencies=[Depends(require_permission("roles:read"))],
)
async def get_role(
    role_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: RoleRepository = Depends(get_role_repository),
) -> RoleWithPermissionsOut:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    uc = GetRoleUseCase(repo)
    r = await uc.execute(company_id, role_id)
    return RoleWithPermissionsOut(
        id=r.id,
        company_id=r.company_id,
        name=r.name,
        description=r.description,
        is_system=r.is_system,
        created_at=r.created_at or __import__("datetime").datetime.now(),
        updated_at=r.updated_at,
        permissions=[
            PermissionOut(id=p.id, code=p.code, description=p.description, module=p.module)
            for p in r.permissions
        ],
    )


@router.post(
    "",
    response_model=RoleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear rol",
    dependencies=[Depends(require_permission("roles:create"))],
)
async def create_role(
    body: CreateRoleRequest,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: RoleRepository = Depends(get_role_repository),
    audit: AuditService = Depends(get_audit_service),
) -> RoleOut:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    uc = CreateRoleUseCase(repo)
    r = await uc.execute(CreateRoleInput(company_id=company_id, name=body.name, description=body.description))
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="roles",
        resource_id=str(r.id),
        after_state=role_to_audit_state(r),
    )
    return RoleOut(
        id=r.id,
        company_id=r.company_id,
        name=r.name,
        description=r.description,
        is_system=r.is_system,
        created_at=r.created_at or __import__("datetime").datetime.now(),
        updated_at=r.updated_at,
    )


@router.patch(
    "/{role_id}",
    response_model=RoleOut,
    status_code=status.HTTP_200_OK,
    summary="Actualizar rol",
    dependencies=[Depends(require_permission("roles:update"))],
)
async def update_role(
    role_id: uuid.UUID,
    body: UpdateRoleRequest,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: RoleRepository = Depends(get_role_repository),
    audit: AuditService = Depends(get_audit_service),
) -> RoleOut:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    before = await repo.get_by_id(company_id, role_id)
    if before and before.company_id is None:
        raise HTTPException(403, "Los roles de sistema son plantillas protegidas.")
    uc = UpdateRoleUseCase(repo)
    r = await uc.execute(
        UpdateRoleInput(company_id=company_id, role_id=role_id, name=body.name, description=body.description)
    )
    await audit.record(
        action="UPDATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="roles",
        resource_id=str(r.id),
        before_state=role_to_audit_state(before),
        after_state=role_to_audit_state(r),
    )
    return RoleOut(
        id=r.id,
        company_id=r.company_id,
        name=r.name,
        description=r.description,
        is_system=r.is_system,
        created_at=r.created_at or __import__("datetime").datetime.now(),
        updated_at=r.updated_at,
    )


@router.delete(
    "/{role_id}",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Eliminar rol (no sistema)",
    dependencies=[Depends(require_permission("roles:delete"))],
)
async def delete_role(
    role_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: RoleRepository = Depends(get_role_repository),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    before = await repo.get_by_id(company_id, role_id)
    uc = DeleteRoleUseCase(repo)
    await uc.execute(company_id, role_id)
    await audit.record(
        action="DELETE",
        user_id=current.id,
        company_id=company_id,
        resource_type="roles",
        resource_id=str(role_id),
        before_state=role_to_audit_state(before),
    )
    return MessageOut(message="Rol eliminado.", code="role_deleted")


@router.post(
    "/{role_id}/duplicate",
    response_model=RoleWithPermissionsOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("roles:create"))],
)
async def duplicate_role(
    role_id: uuid.UUID,
    body: DuplicateRoleRequest,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: RoleRepository = Depends(get_role_repository),
    perm_repo: PermissionRepository = Depends(get_permission_repository),
    audit: AuditService = Depends(get_audit_service),
) -> RoleWithPermissionsOut:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    source = await GetRoleUseCase(repo).execute(company_id, role_id)
    created = await CreateRoleUseCase(repo).execute(
        CreateRoleInput(
            company_id=company_id,
            name=body.name,
            description=body.description or source.description,
        )
    )
    duplicated = await SetRolePermissionsUseCase(repo, perm_repo).execute(
        SetRolePermissionsInput(
            company_id=company_id,
            role_id=created.id,
            permission_codes=tuple(permission.code for permission in source.permissions),
        )
    )
    await audit.record(
        action="DUPLICATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="roles",
        resource_id=str(duplicated.id),
        after_state={
            **role_to_audit_state(duplicated),
            "source_role_id": str(role_id),
            "permission_codes": [p.code for p in duplicated.permissions],
        },
    )
    return RoleWithPermissionsOut(
        id=duplicated.id,
        company_id=duplicated.company_id,
        name=duplicated.name,
        description=duplicated.description,
        is_system=duplicated.is_system,
        created_at=duplicated.created_at or __import__("datetime").datetime.now(),
        updated_at=duplicated.updated_at,
        permissions=[
            PermissionOut(
                id=permission.id,
                code=permission.code,
                description=permission.description,
                module=permission.module,
            )
            for permission in duplicated.permissions
        ],
    )


@router.put(
    "/{role_id}/permissions",
    response_model=RoleWithPermissionsOut,
    status_code=status.HTTP_200_OK,
    summary="Asignar permisos a un rol (matriz)",
    dependencies=[Depends(require_permission("permissions:manage"))],
)
async def set_role_permissions(
    role_id: uuid.UUID,
    body: SetRolePermissionsRequest,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: RoleRepository = Depends(get_role_repository),
    perm_repo: PermissionRepository = Depends(get_permission_repository),
    audit: AuditService = Depends(get_audit_service),
) -> RoleWithPermissionsOut:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    role = await repo.get_by_id(company_id, role_id)
    if role and role.company_id is None:
        raise HTTPException(403, "Los permisos de las plantillas del sistema están protegidos.")
    uc = SetRolePermissionsUseCase(repo, perm_repo)
    r = await uc.execute(
        SetRolePermissionsInput(company_id=company_id, role_id=role_id, permission_codes=tuple(body.permission_codes))
    )
    await audit.record(
        action="SET_PERMISSIONS",
        user_id=current.id,
        company_id=company_id,
        resource_type="roles",
        resource_id=str(role_id),
        after_state={"permission_codes": [p.code for p in r.permissions]},
    )
    return RoleWithPermissionsOut(
        id=r.id,
        company_id=r.company_id,
        name=r.name,
        description=r.description,
        is_system=r.is_system,
        created_at=r.created_at or __import__("datetime").datetime.now(),
        updated_at=r.updated_at,
        permissions=[
            PermissionOut(id=p.id, code=p.code, description=p.description, module=p.module)
            for p in r.permissions
        ],
    )


@router.post(
    "/assign",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Asignar rol a usuario",
    dependencies=[Depends(require_permission("roles:assign"))],
)
async def assign_role(
    body: AssignRoleRequest,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: RoleRepository = Depends(get_role_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    if await session.get(UserCompany, (body.user_id, company_id)) is None:
        raise HTTPException(404, "Usuario no encontrado en la empresa seleccionada.")
    uc = AssignRoleUseCase(user_repo, repo)
    created = await uc.execute(
        AssignRoleInput(user_id=body.user_id, company_id=company_id, role_id=body.role_id, assigned_by=current.id)
    )
    if created:
        await audit.record(
            action="ASSIGN_ROLE",
            user_id=current.id,
            company_id=company_id,
            resource_type="users",
            resource_id=str(body.user_id),
            after_state={"role_id": str(body.role_id)},
        )
    return MessageOut(
        message="Rol asignado." if created else "El usuario ya tenía ese rol.",
        code="role_assigned" if created else "role_already_assigned",
    )


@router.post(
    "/revoke",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Revocar rol de usuario",
    dependencies=[Depends(require_permission("roles:revoke"))],
)
async def revoke_role(
    body: RevokeRoleRequest,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: RoleRepository = Depends(get_role_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    company_id = request_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    if await session.get(UserCompany, (body.user_id, company_id)) is None:
        raise HTTPException(404, "Usuario no encontrado en la empresa seleccionada.")
    uc = RevokeRoleUseCase(user_repo, repo)
    ok = await uc.execute(
        RevokeRoleInput(user_id=body.user_id, company_id=company_id, role_id=body.role_id, actor_id=current.id)
    )
    if ok:
        await audit.record(
            action="REVOKE_ROLE",
            user_id=current.id,
            company_id=company_id,
            resource_type="users",
            resource_id=str(body.user_id),
            before_state={"role_id": str(body.role_id)},
        )
    return MessageOut(
        message="Rol revocado." if ok else "El usuario no tenía ese rol.",
        code="role_revoked" if ok else "role_not_assigned",
    )


@router.get(
    "/users/{user_id}/roles",
    response_model=list[RoleOut],
    status_code=status.HTTP_200_OK,
    summary="Roles asignados a un usuario",
    dependencies=[Depends(require_permission("roles:read"))],
)
async def get_user_roles(
    user_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: RoleRepository = Depends(get_role_repository),
) -> list[RoleOut]:
    company_id = request_company_id(request)
    await require_company_access(session, current, company_id)
    if await session.get(UserCompany, (user_id, company_id)) is None:
        raise HTTPException(404, "Usuario no encontrado en la empresa seleccionada.")
    uc = GetUserRolesUseCase(repo)
    roles = await uc.execute(user_id, company_id)
    return [
        RoleOut(
            id=r.id,
            company_id=r.company_id,
            name=r.name,
            description=r.description,
            is_system=r.is_system,
            created_at=r.created_at or __import__("datetime").datetime.now(),
            updated_at=r.updated_at,
        )
        for r in roles
    ]


# Separate router mounted at /auth/me/permissions to keep the path natural.
me_router = APIRouter(prefix="/auth", tags=["auth"])


@me_router.get(
    "/me/permissions",
    response_model=EffectivePermissionsOut,
    status_code=status.HTTP_200_OK,
    summary="Permisos efectivos del usuario actual",
)
async def my_permissions(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    user_repo: UserRepository = Depends(get_user_repository),
    role_repo: RoleRepository = Depends(get_role_repository),
) -> EffectivePermissionsOut:
    company_id = await request_company_id_or_default(request, session, current)
    await require_company_access(session, current, company_id)
    uc = GetEffectivePermissionsUseCase(user_repo, role_repo)
    perms = await uc.execute(current.id, company_id)
    if perms == ("*",):
        from app.application.rbac.catalogue import ALL_PERMISSION_CODES

        return EffectivePermissionsOut(permissions=sorted(ALL_PERMISSION_CODES), is_superuser=True)
    return EffectivePermissionsOut(permissions=list(perms), is_superuser=False)
