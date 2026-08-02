"""Domain entities: Department, Employee."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class EmployeeStatus(StrEnum):
    ACTIVO = "activo"
    INACTIVO = "inactivo"
    VACACIONES = "vacaciones"
    BAJA = "baja"


@dataclass(frozen=True, slots=True)
class Department:
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    description: str | None = None
    parent_department_id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Employee:
    id: uuid.UUID
    company_id: uuid.UUID
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
    status: EmployeeStatus = EmployeeStatus.ACTIVO
    photo_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
