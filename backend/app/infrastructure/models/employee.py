"""ORM models: Department, Employee."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class Department(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "departments"
    __table_args__ = ({"comment": "Departments (self-referencing hierarchy)."},)

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    parent_department_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        default=None,
    )
    __table_args__ = (
        Index(
            "uq_departments_company_name_visible",
            "company_id",
            func.lower(name),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_departments_company_deleted_at", "company_id", "deleted_at"),
        {"comment": "Departments scoped to a company."},
    )


class Employee(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "employees"
    __table_args__ = ({"comment": "Employee profiles (optionally linked to a user account)."},)

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    employee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    document_id: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)
    address: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        default=None,
    )
    position: Mapped[str | None] = mapped_column(String(120), nullable=True, default=None)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="activo", default="activo"
    )
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    __table_args__ = (
        Index(
            "uq_employees_company_code_visible",
            "company_id",
            func.lower(employee_code),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_employees_user_visible",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL AND deleted_at IS NULL"),
            sqlite_where=text("user_id IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index("ix_employees_company_deleted_at", "company_id", "deleted_at"),
        {"comment": "Employee profiles scoped to a company."},
    )


class DepartmentBranchAssignment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "department_branch_assignments"
    department_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    manager_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("employees.id", ondelete="SET NULL")
    )
    opened_at: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    closed_at: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    __table_args__ = (UniqueConstraint("department_id", "branch_id", name="uq_department_branch"),)


class EmployeeBranchAssignment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "employee_branch_assignments"
    employee_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    assigned_from: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    assigned_until: Mapped[date | None] = mapped_column(Date)
    position: Mapped[str | None] = mapped_column(String(120))
    shift: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
