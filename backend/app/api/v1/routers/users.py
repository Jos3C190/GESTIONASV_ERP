"""Users router — admin CRUD for user management.

Phase 2: guarded by `require_permission` (dynamic RBAC). Superusers pass
automatically via the CheckPermissionUseCase shortcut.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_register_user_use_case,
    get_role_repository,
    require_permission,
)
from app.api.v1.schemas.common import MessageOut
from app.api.v1.schemas.users import (
    CreateUserRequest,
    ForcePasswordResetRequest,
    Page,
    PageMeta,
    UpdateUserRequest,
    UserOut,
)
from app.application.audit.audit_service import AuditService, user_to_audit_state
from app.application.auth.register_user import (
    RegisterUserInput,
    RegisterUserUseCase,
)
from app.application.employees.employee_crud import (
    CreateEmployeeInput,
    CreateEmployeeUseCase,
    LinkUserInput,
    LinkUserUseCase,
)
from app.application.rbac.role_assignment import AssignRoleInput, AssignRoleUseCase
from app.application.users.admin_actions import (
    DeactivateUserUseCase,
    ForcePasswordResetInput,
    ForcePasswordResetUseCase,
    UnlockAccountUseCase,
)
from app.application.users.get_user import GetUserUseCase
from app.application.users.list_users import ListUsersInput, ListUsersUseCase
from app.application.users.update_user import UpdateUserInput, UpdateUserUseCase
from app.domain.ports.department_repository import DepartmentRepository
from app.domain.ports.employee_repository import EmployeeRepository
from app.domain.ports.role_repository import RoleRepository
from app.domain.ports.user_repository import UserRepository

router = APIRouter(prefix="/users", tags=["users"])


def _get_user_repo(session: SessionDep) -> UserRepository:
    from app.infrastructure.repositories import SqlAlchemyUserRepository

    return SqlAlchemyUserRepository(session)


def _get_employee_repo(session: SessionDep) -> EmployeeRepository:
    from app.infrastructure.repositories import SqlAlchemyEmployeeRepository

    return SqlAlchemyEmployeeRepository(session)


def _get_department_repo(session: SessionDep) -> DepartmentRepository:
    from app.infrastructure.repositories import SqlAlchemyDepartmentRepository

    return SqlAlchemyDepartmentRepository(session)


@router.get(
    "",
    response_model=Page[UserOut],
    status_code=status.HTTP_200_OK,
    summary="Listar usuarios (paginado)",
    dependencies=[Depends(require_permission("users:read"))],
)
async def list_users(
    repo: UserRepository = Depends(_get_user_repo),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
) -> Page[UserOut]:
    uc = ListUsersUseCase(repo)
    result = await uc.execute(ListUsersInput(page=page, size=size, search=search))
    return Page[UserOut](
        items=[UserOut.model_validate(u, from_attributes=True) for u in result.items],
        meta=PageMeta(page=result.page, size=result.size, total=result.total, pages=result.pages),
    )


@router.get(
    "/{user_id}",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener usuario por id",
    dependencies=[Depends(require_permission("users:read"))],
)
async def get_user(
    user_id: uuid.UUID,
    repo: UserRepository = Depends(_get_user_repo),
) -> UserOut:
    uc = GetUserUseCase(repo)
    result = await uc.execute(user_id)
    return UserOut.model_validate(result.user, from_attributes=True)


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario",
    dependencies=[Depends(require_permission("users:create"))],
)
async def create_user(
    body: CreateUserRequest,
    current: CurrentUser,
    register_uc: RegisterUserUseCase = Depends(get_register_user_use_case),
    employee_repo: EmployeeRepository = Depends(_get_employee_repo),
    department_repo: DepartmentRepository = Depends(_get_department_repo),
    role_repo: RoleRepository = Depends(get_role_repository),
    user_repo: UserRepository = Depends(_get_user_repo),
    audit: AuditService = Depends(get_audit_service),
) -> UserOut:
    created = await register_uc.execute(
        RegisterUserInput(
            username=body.username,
            email=body.email,
            password=body.password,
            is_active=True,
            is_superuser=body.is_superuser,
        )
    )
    if body.employee_id is not None:
        await LinkUserUseCase(employee_repo).execute(
            LinkUserInput(emp_id=body.employee_id, user_id=created.id)
        )
    else:
        await CreateEmployeeUseCase(employee_repo, department_repo).execute(
            CreateEmployeeInput(
                employee_code=f"USR-{str(created.id)[:8].upper()}",
                first_name=body.username,
                last_name="Usuario",
                user_id=created.id,
            )
        )

    requested_role_ids = body.role_ids
    if not requested_role_ids:
        default_role = await role_repo.get_by_name("EMPLEADO")
        if default_role is None:
            from app.core.exceptions import BusinessRuleError

            raise BusinessRuleError(
                "No existe el rol predeterminado EMPLEADO.",
                code="default_role_missing",
            )
        requested_role_ids = [default_role.id]
    role_assignment = AssignRoleUseCase(user_repo, role_repo)
    for role_id in requested_role_ids:
        await role_assignment.execute(
            AssignRoleInput(
                user_id=created.id,
                role_id=role_id,
                assigned_by=current.id,
            )
        )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        resource_type="users",
        resource_id=str(created.id),
        after_state=user_to_audit_state(created),
    )
    return UserOut.model_validate(created, from_attributes=True)


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    summary="Actualizar usuario (activo / superadmin)",
    dependencies=[Depends(require_permission("users:update"))],
)
async def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    current: CurrentUser,
    repo: UserRepository = Depends(_get_user_repo),
    audit: AuditService = Depends(get_audit_service),
) -> UserOut:
    before = await GetUserUseCase(repo).execute(user_id)
    uc = UpdateUserUseCase(repo)
    updated = await uc.execute(
        UpdateUserInput(
            target_id=user_id,
            actor_id=current.id,
            is_active=body.is_active,
            is_superuser=body.is_superuser,
        )
    )
    await audit.record(
        action="UPDATE",
        user_id=current.id,
        resource_type="users",
        resource_id=str(user_id),
        before_state=user_to_audit_state(before.user),
        after_state=user_to_audit_state(updated),
    )
    return UserOut.model_validate(updated, from_attributes=True)


@router.post(
    "/{user_id}/force-password-reset",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Forzar cambio de contraseña",
    dependencies=[Depends(require_permission("users:force_password_reset"))],
)
async def force_password_reset(
    user_id: uuid.UUID,
    body: ForcePasswordResetRequest,
    current: CurrentUser,
    repo: UserRepository = Depends(_get_user_repo),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    uc = ForcePasswordResetUseCase(repo)
    await uc.execute(
        ForcePasswordResetInput(
            target_id=user_id, actor_id=current.id, new_password=body.new_password
        )
    )
    await audit.record(
        action="PASSWORD_RESET",
        user_id=current.id,
        resource_type="users",
        resource_id=str(user_id),
        metadata={"password_fields_omitted": True},
    )
    return MessageOut(message="Contraseña actualizada.", code="password_reset")


@router.post(
    "/{user_id}/unlock",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Desbloquear cuenta",
    dependencies=[Depends(require_permission("users:unlock"))],
)
async def unlock_account(
    user_id: uuid.UUID,
    current: CurrentUser,
    repo: UserRepository = Depends(_get_user_repo),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    uc = UnlockAccountUseCase(repo)
    await uc.execute(user_id)
    await audit.record(
        action="UNLOCK",
        user_id=current.id,
        resource_type="users",
        resource_id=str(user_id),
    )
    return MessageOut(message="Cuenta desbloqueada.", code="account_unlocked")


@router.delete(
    "/{user_id}",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Desactivar usuario (soft delete)",
    dependencies=[Depends(require_permission("users:deactivate"))],
)
async def deactivate_user(
    user_id: uuid.UUID,
    current: CurrentUser,
    repo: UserRepository = Depends(_get_user_repo),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    before = await GetUserUseCase(repo).execute(user_id)
    uc = DeactivateUserUseCase(repo)
    await uc.execute(user_id, current.id)
    await audit.record(
        action="LOGICAL_DELETE",
        user_id=current.id,
        resource_type="users",
        resource_id=str(user_id),
        before_state=user_to_audit_state(before.user),
        after_state={**user_to_audit_state(before.user), "is_active": False},
    )
    return MessageOut(message="Usuario desactivado.", code="user_deactivated")
