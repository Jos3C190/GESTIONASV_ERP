"""Employee/Department DTOs."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.common import ORMOut, Page, PageMeta


class DepartmentOut(ORMOut):
    id: uuid.UUID
    name: str
    description: str | None = None
    parent_department_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


class EmployeeOut(ORMOut):
    id: uuid.UUID
    employee_code: str
    first_name: str
    last_name: str
    user_id: uuid.UUID | None = None
    document_id: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    address: str | None = None
    department_id: uuid.UUID | None = None
    position: str | None = None
    hire_date: date | None = None
    termination_date: date | None = None
    status: str
    photo_url: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class EmployeeStatsOut(BaseModel):
    """Aggregate employee counts — computed via a single SQL GROUP BY query."""
    total: int
    active: int
    inactive: int
    on_leave: int
    terminated: int
    linked_to_user: int


class CreateDepartmentRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: str | None = None
    parent_department_id: uuid.UUID | None = None


class UpdateDepartmentRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    description: str | None = None
    parent_department_id: uuid.UUID | None = None


class CreateEmployeeRequest(BaseModel):
    employee_code: str = Field(..., min_length=2, max_length=32)
    first_name: str = Field(..., min_length=2, max_length=120)
    last_name: str = Field(..., min_length=2, max_length=120)
    user_id: uuid.UUID | None = None
    document_id: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    address: str | None = None
    department_id: uuid.UUID | None = None
    position: str | None = None
    hire_date: date | None = None
    status: str = "activo"
    photo_url: str | None = Field(None, max_length=2048)


class UpdateEmployeeRequest(BaseModel):
    first_name: str | None = Field(None, min_length=2, max_length=120)
    last_name: str | None = Field(None, min_length=2, max_length=120)
    document_id: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    address: str | None = None
    department_id: uuid.UUID | None = None
    position: str | None = None
    hire_date: date | None = None
    termination_date: date | None = None
    status: str | None = None
    photo_url: str | None = Field(None, max_length=2048)


class LinkUserRequest(BaseModel):
    user_id: uuid.UUID


__all__ = [
    "DepartmentOut",
    "EmployeeOut",
    "CreateDepartmentRequest",
    "UpdateDepartmentRequest",
    "CreateEmployeeRequest",
    "UpdateEmployeeRequest",
    "LinkUserRequest",
    "Page",
    "PageMeta",
]