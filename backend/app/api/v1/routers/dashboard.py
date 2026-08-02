"""Branch-aware operational dashboard aggregates."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter
from sqlalchemy import func, or_, select

from app.api.v1.company_access import resolve_branch_scope
from app.api.v1.deps import CurrentUser, SessionDep
from app.api.v1.schemas.dashboard import (
    ActivitySeriesPointOut,
    DashboardPersonOut,
    DashboardSummaryOut,
    DepartmentDistributionOut,
    RecentUserOut,
)
from app.infrastructure.models.audit import AuditLog
from app.infrastructure.models.employee import (
    Department,
    Employee,
    EmployeeBranchAssignment,
)
from app.infrastructure.models.organization import (
    Branch,
    UserBranch,
    UserCompany,
    Warehouse,
)
from app.infrastructure.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _person_name(first_name: str | None, last_name: str | None, fallback: str) -> str:
    full_name = " ".join(part for part in (first_name, last_name) if part).strip()
    return full_name or fallback


def _initials(name: str) -> str:
    parts = [part for part in name.split() if part]
    return "".join(part[0] for part in parts[:2]).upper() or "?"


@router.get(
    "/summary",
    response_model=DashboardSummaryOut,
)
async def get_dashboard_summary(
    company_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    branch_id: uuid.UUID | None = None,
) -> DashboardSummaryOut:
    context = await resolve_branch_scope(session, current, company_id, branch_id)

    employee_stmt = select(func.count(Employee.id)).where(
        Employee.company_id == company_id, Employee.deleted_at.is_(None)
    )
    warehouse_stmt = (
        select(func.count(Warehouse.id))
        .join(Branch)
        .where(Branch.company_id == company_id, Warehouse.is_active.is_(True))
    )
    distribution_stmt = (
        select(Department.name, func.count(Employee.id))
        .join(Employee, Employee.department_id == Department.id)
        .where(
            Department.company_id == company_id,
            Employee.deleted_at.is_(None),
        )
        .group_by(Department.name)
        .order_by(func.count(Employee.id).desc())
    )
    completed_profiles_count = func.count(Employee.id).filter(
        Employee.document_id.is_not(None),
        Employee.department_id.is_not(None),
        Employee.position.is_not(None),
        Employee.hire_date.is_not(None),
    )
    profile_stats_stmt = select(
        func.count(Employee.id),
        completed_profiles_count,
    ).where(
        Employee.company_id == company_id,
        Employee.deleted_at.is_(None),
        Employee.status == "activo",
    )
    team_stmt = select(
        Employee.id,
        Employee.first_name,
        Employee.last_name,
        Employee.document_id,
        Employee.department_id,
        Employee.position,
        Employee.hire_date,
        Department.name,
    ).outerjoin(Department, Employee.department_id == Department.id).where(
        Employee.company_id == company_id,
        Employee.deleted_at.is_(None),
        Employee.status == "activo",
    ).order_by(Employee.created_at.desc()).limit(8)
    if branch_id is not None:
        employee_stmt = employee_stmt.join(EmployeeBranchAssignment).where(
            EmployeeBranchAssignment.branch_id == branch_id,
            EmployeeBranchAssignment.is_active.is_(True),
        )
        warehouse_stmt = warehouse_stmt.where(Warehouse.branch_id == branch_id)
        distribution_stmt = distribution_stmt.join(EmployeeBranchAssignment).where(
            EmployeeBranchAssignment.branch_id == branch_id,
            EmployeeBranchAssignment.is_active.is_(True),
        )
        profile_stats_stmt = profile_stats_stmt.join(
            EmployeeBranchAssignment,
            EmployeeBranchAssignment.employee_id == Employee.id,
        ).where(
            EmployeeBranchAssignment.branch_id == branch_id,
            EmployeeBranchAssignment.is_active.is_(True),
        )
        team_stmt = team_stmt.join(
            EmployeeBranchAssignment,
            EmployeeBranchAssignment.employee_id == Employee.id,
        ).where(
            EmployeeBranchAssignment.branch_id == branch_id,
            EmployeeBranchAssignment.is_active.is_(True),
        )

    user_stmt = (
        select(func.count(func.distinct(User.id)))
        .join(UserCompany, UserCompany.user_id == User.id)
        .where(
            UserCompany.company_id == company_id,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    if branch_id is not None:
        user_stmt = user_stmt.outerjoin(
            UserBranch,
            (UserBranch.user_id == User.id)
            & (UserBranch.company_id == company_id)
            & (UserBranch.branch_id == branch_id)
            & UserBranch.is_active.is_(True),
        ).where(
            or_(
                User.is_superuser.is_(True),
                UserCompany.access_all_branches.is_(True),
                UserBranch.branch_id.is_not(None),
            )
        )

    recent_users_stmt = (
        select(
            User.id,
            User.username,
            User.is_active,
            User.locked_until,
            User.created_at,
            Employee.first_name,
            Employee.last_name,
            Department.name,
        )
        .join(UserCompany, UserCompany.user_id == User.id)
        .outerjoin(Employee, (Employee.user_id == User.id) & (Employee.deleted_at.is_(None)))
        .outerjoin(Department, Employee.department_id == Department.id)
        .where(UserCompany.company_id == company_id, User.deleted_at.is_(None))
        .order_by(User.created_at.desc())
        .limit(10)
    )
    if branch_id is not None:
        recent_users_stmt = recent_users_stmt.outerjoin(
            UserBranch,
            (UserBranch.user_id == User.id)
            & (UserBranch.company_id == company_id)
            & (UserBranch.branch_id == branch_id)
            & UserBranch.is_active.is_(True),
        ).where(
            or_(
                User.is_superuser.is_(True),
                UserCompany.access_all_branches.is_(True),
                UserBranch.branch_id.is_not(None),
            )
        )

    today = datetime.now(UTC).date()
    today_start = datetime.combine(today, time.min, tzinfo=UTC)
    tomorrow_start = today_start + timedelta(days=1)
    audit_stmt = select(func.count(AuditLog.id)).where(
        AuditLog.company_id == company_id,
        AuditLog.created_at >= today_start,
        AuditLog.created_at < tomorrow_start,
    )
    if branch_id is not None:
        audit_stmt = audit_stmt.where(AuditLog.branch_id == branch_id)

    series_start = today - timedelta(days=89)
    series_start_ts = datetime.combine(series_start, time.min, tzinfo=UTC)
    activity_stmt = (
        select(func.date(AuditLog.created_at), func.count(AuditLog.id))
        .where(
            AuditLog.company_id == company_id,
            AuditLog.created_at >= series_start_ts,
            AuditLog.created_at < tomorrow_start,
        )
        .group_by(func.date(AuditLog.created_at))
    )
    if branch_id is not None:
        activity_stmt = activity_stmt.where(AuditLog.branch_id == branch_id)

    distribution = (await session.execute(distribution_stmt)).all()
    profile_total, completed_profiles = (await session.execute(profile_stats_stmt)).one()
    profile_rows = (await session.execute(team_stmt)).all()
    activity_by_date = {
        day: int(count) for day, count in (await session.execute(activity_stmt)).all()
    }
    recent_rows = (await session.execute(recent_users_stmt)).all()
    onboarding_progress = (
        round(int(completed_profiles or 0) * 100 / int(profile_total)) if profile_total else 0
    )
    team = []
    for row in profile_rows[:8]:
        name = _person_name(row.first_name, row.last_name, "Empleado")
        team.append(
            DashboardPersonOut(
                id=row.id,
                name=name,
                initials=_initials(name),
                department=row.name or "Sin departamento",
            )
        )
    now = datetime.now(UTC)
    recent_users = []
    for row in recent_rows:
        name = _person_name(row.first_name, row.last_name, row.username)
        if row.locked_until and row.locked_until > now:
            user_status = "locked"
        else:
            user_status = "active" if row.is_active else "inactive"
        recent_users.append(
            RecentUserOut(
                id=row.id,
                name=name,
                initials=_initials(name),
                department=row.name or "Sin departamento",
                status=user_status,
                created_at=row.created_at,
            )
        )
    counts = (
        await session.execute(
            select(
                user_stmt.scalar_subquery().label("active_users"),
                employee_stmt.scalar_subquery().label("employees"),
                warehouse_stmt.scalar_subquery().label("warehouses"),
                audit_stmt.scalar_subquery().label("events_today"),
            )
        )
    ).one()
    return DashboardSummaryOut(
        active_users=int(counts.active_users or 0),
        employees=int(counts.employees or 0),
        warehouses=int(counts.warehouses or 0),
        events_today=int(counts.events_today or 0),
        branches=1 if branch_id else len(context.branches),
        onboarding_progress=onboarding_progress,
        department_distribution=[
            DepartmentDistributionOut(label=name, value=int(count))
            for name, count in distribution
        ],
        activity_series=[
            ActivitySeriesPointOut(
                date=series_start + timedelta(days=offset),
                value=activity_by_date.get(series_start + timedelta(days=offset), 0),
            )
            for offset in range(90)
        ],
        team=team,
        recent_users=recent_users,
    )
