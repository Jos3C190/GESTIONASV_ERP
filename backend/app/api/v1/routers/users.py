"""Users router — admin CRUD for user management.

Phase 2: guarded by `require_permission` (dynamic RBAC). Superusers pass
automatically via the CheckPermissionUseCase shortcut.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import or_, select

from app.api.v1.company_access import resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_register_user_use_case,
    get_role_repository,
    require_permission,
)
from app.api.v1.schemas.common import MessageOut
from app.api.v1.schemas.rbac import RoleOut
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
from app.infrastructure.models.organization import UserBranch, UserCompany
from app.infrastructure.models.user import User as ORMUser

router = APIRouter(prefix="/users", tags=["users"])


def _status_action(before_active: bool, after_active: bool) -> str:
    if before_active == after_active:
        return "UPDATE"
    return "ACTIVATE" if after_active else "DEACTIVATE"


def _get_user_repo(session: SessionDep) -> UserRepository:
    from app.infrastructure.repositories import SqlAlchemyUserRepository

    return SqlAlchemyUserRepository(session)


def _get_employee_repo(session: SessionDep) -> EmployeeRepository:
    from app.infrastructure.repositories import SqlAlchemyEmployeeRepository

    return SqlAlchemyEmployeeRepository(session)


def _get_department_repo(session: SessionDep) -> DepartmentRepository:
    from app.infrastructure.repositories import SqlAlchemyDepartmentRepository

    return SqlAlchemyDepartmentRepository(session)


async def _require_target_scope(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    target_id: uuid.UUID,
) -> uuid.UUID | None:
    raw_company = request.headers.get("X-Company-ID")
    if not raw_company:
        if current.is_superuser:
            return None
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError("Debe indicar la empresa.", code="company_context_required")
    try:
        company_id = uuid.UUID(raw_company)
        branch_id = (
            uuid.UUID(request.headers["X-Branch-ID"])
            if request.headers.get("X-Branch-ID")
            else None
        )
    except ValueError as exc:
        from app.core.exceptions import ValidationError

        raise ValidationError("El contexto operativo no es válido.") from exc

    await resolve_branch_scope(session, current, company_id, branch_id)
    target = await session.get(ORMUser, target_id)
    if target is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Usuario no encontrado.", code="user_not_found")
    if target.is_superuser and not current.is_superuser:
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError("No puede administrar a un superadministrador.", code="forbidden")
    stmt = select(UserCompany.user_id).where(
        UserCompany.user_id == target_id,
        UserCompany.company_id == company_id,
    )
    if branch_id is not None and not target.is_superuser:
        stmt = stmt.outerjoin(
            UserBranch,
            (UserBranch.user_id == UserCompany.user_id)
            & (UserBranch.company_id == company_id)
            & (UserBranch.branch_id == branch_id)
            & UserBranch.is_active.is_(True),
        ).where(
            or_(
                UserCompany.access_all_branches.is_(True),
                UserBranch.branch_id.is_not(None),
            )
        )
    if await session.scalar(stmt) is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Usuario no encontrado.", code="user_not_found")
    return company_id


@router.get(
    "",
    response_model=Page[UserOut],
    status_code=status.HTTP_200_OK,
    summary="Listar usuarios (paginado)",
    dependencies=[Depends(require_permission("users:read"))],
)
async def list_users(
    session: SessionDep,
    current: CurrentUser,
    repo: UserRepository = Depends(_get_user_repo),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
    status_filter: str | None = Query(
        None, alias="status", pattern="^(active|inactive|superuser)$"
    ),
    company_id: uuid.UUID | None = Query(None),
    branch_id: uuid.UUID | None = Query(None),
) -> Page[UserOut]:
    if company_id is not None:
        await resolve_branch_scope(session, current, company_id, branch_id)
    elif not current.is_superuser:
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError("Debe indicar la empresa.", code="company_context_required")
    uc = ListUsersUseCase(repo)
    result = await uc.execute(
        ListUsersInput(
            page=page,
            size=size,
            search=search,
            status_filter=status_filter,
            company_id=company_id,
            branch_id=branch_id,
        )
    )
    return Page[UserOut](
        items=[UserOut.model_validate(u, from_attributes=True) for u in result.items],
        meta=PageMeta(page=result.page, size=result.size, total=result.total, pages=result.pages),
    )


@router.get(
    "/batch/roles",
    response_model=dict[uuid.UUID, list[RoleOut]],
    status_code=status.HTTP_200_OK,
    summary="Obtener roles de varios usuarios",
    dependencies=[
        Depends(require_permission("users:read")),
        Depends(require_permission("roles:read")),
    ],
)
async def get_users_roles_batch(
    session: SessionDep,
    current: CurrentUser,
    role_repo: RoleRepository = Depends(get_role_repository),
    user_ids: list[uuid.UUID] = Query(..., min_length=1, max_length=100),
    company_id: uuid.UUID = Query(...),
    branch_id: uuid.UUID | None = Query(None),
) -> dict[uuid.UUID, list[RoleOut]]:
    """Return role summaries for the visible users in one database roundtrip."""
    await resolve_branch_scope(session, current, company_id, branch_id)
    allowed = (
        select(ORMUser.id)
        .join(UserCompany, UserCompany.user_id == ORMUser.id)
        .where(
            ORMUser.id.in_(user_ids),
            ORMUser.deleted_at.is_(None),
            UserCompany.company_id == company_id,
        )
    )
    if branch_id is not None:
        join_condition = (
            (UserBranch.user_id == ORMUser.id)
            & (UserBranch.company_id == company_id)
            & (UserBranch.branch_id == branch_id)
            & UserBranch.is_active.is_(True)
        )
        allowed = allowed.outerjoin(UserBranch, join_condition).where(
            or_(
                ORMUser.is_superuser.is_(True),
                UserCompany.access_all_branches.is_(True),
                UserBranch.branch_id.is_not(None),
            )
        )
    allowed_ids = list((await session.execute(allowed)).scalars().all())
    roles_by_user = await role_repo.get_roles_for_users(allowed_ids, company_id)
    return {
        user_id: [RoleOut.model_validate(role, from_attributes=True) for role in roles]
        for user_id, roles in roles_by_user.items()
    }


@router.get(
    "/{user_id}",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener usuario por id",
    dependencies=[Depends(require_permission("users:read"))],
)
async def get_user(
    user_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: UserRepository = Depends(_get_user_repo),
) -> UserOut:
    await _require_target_scope(request, session, current, user_id)
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
    session: SessionDep,
    register_uc: RegisterUserUseCase = Depends(get_register_user_use_case),
    employee_repo: EmployeeRepository = Depends(_get_employee_repo),
    department_repo: DepartmentRepository = Depends(_get_department_repo),
    role_repo: RoleRepository = Depends(get_role_repository),
    user_repo: UserRepository = Depends(_get_user_repo),
    audit: AuditService = Depends(get_audit_service),
) -> UserOut:
    from app.api.v1.company_access import require_company_access
    from app.infrastructure.models.organization import UserCompany

    await require_company_access(session, current, body.company_id, require_active=True)
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
        employee = await employee_repo.get_by_id(body.employee_id)
        if employee is None or employee.company_id != body.company_id:
            from app.core.exceptions import BusinessRuleError

            raise BusinessRuleError(
                "El empleado no pertenece a la empresa seleccionada.",
                code="employee_company_mismatch",
            )
        await LinkUserUseCase(employee_repo).execute(
            LinkUserInput(emp_id=body.employee_id, user_id=created.id)
        )
    else:
        await CreateEmployeeUseCase(employee_repo, department_repo).execute(
            CreateEmployeeInput(
                company_id=body.company_id,
                employee_code=f"USR-{str(created.id)[:8].upper()}",
                first_name=body.username,
                last_name="Usuario",
                user_id=created.id,
            )
        )
    session.add(UserCompany(user_id=created.id, company_id=body.company_id, is_default=True))
    await session.flush()

    requested_role_ids = body.role_ids
    if not requested_role_ids:
        default_role = await role_repo.get_by_name(body.company_id, "EMPLEADO")
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
                company_id=body.company_id,
                role_id=role_id,
                assigned_by=current.id,
            )
        )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=body.company_id,
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
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: UserRepository = Depends(_get_user_repo),
    audit: AuditService = Depends(get_audit_service),
) -> UserOut:
    company_id = await _require_target_scope(request, session, current, user_id)
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
        action=_status_action(before.user.is_active, updated.is_active),
        user_id=current.id,
        company_id=company_id,
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
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: UserRepository = Depends(_get_user_repo),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    company_id = await _require_target_scope(request, session, current, user_id)
    uc = ForcePasswordResetUseCase(repo)
    await uc.execute(
        ForcePasswordResetInput(
            target_id=user_id, actor_id=current.id, new_password=body.new_password
        )
    )
    await audit.record(
        action="PASSWORD_RESET",
        user_id=current.id,
        company_id=company_id,
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
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: UserRepository = Depends(_get_user_repo),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    company_id = await _require_target_scope(request, session, current, user_id)
    uc = UnlockAccountUseCase(repo)
    await uc.execute(user_id)
    await audit.record(
        action="UNLOCK",
        user_id=current.id,
        company_id=company_id,
        resource_type="users",
        resource_id=str(user_id),
    )
    return MessageOut(message="Cuenta desbloqueada.", code="account_unlocked")


@router.delete(
    "/{user_id}",
    response_model=MessageOut,
    status_code=status.HTTP_200_OK,
    summary="Desactivar usuario (compatibilidad; no envía a papelera)",
    deprecated=True,
    dependencies=[Depends(require_permission("users:deactivate"))],
)
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    repo: UserRepository = Depends(_get_user_repo),
    audit: AuditService = Depends(get_audit_service),
) -> MessageOut:
    company_id = await _require_target_scope(request, session, current, user_id)
    before = await GetUserUseCase(repo).execute(user_id)
    uc = DeactivateUserUseCase(repo)
    changed = await uc.execute(user_id, current.id)
    if changed:
        await audit.record(
            action="DEACTIVATE",
            user_id=current.id,
            company_id=company_id,
            resource_type="users",
            resource_id=str(user_id),
            before_state=user_to_audit_state(before.user),
            after_state={**user_to_audit_state(before.user), "is_active": False},
        )
    return MessageOut(
        message="Usuario desactivado." if changed else "El usuario ya estaba desactivado.",
        code="user_deactivated" if changed else "user_already_inactive",
    )
