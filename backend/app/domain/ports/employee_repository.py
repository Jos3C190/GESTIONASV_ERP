"""Port: EmployeeRepository."""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.domain.entities.employee import Employee


@dataclass(frozen=True, slots=True)
class EmployeeStats:
    """Aggregate counts computed directly in the database."""
    total: int
    active: int
    inactive: int
    on_leave: int       # vacaciones
    terminated: int     # baja
    linked_to_user: int


class EmployeeRepository(Protocol):
    async def get_by_id(self, emp_id: uuid.UUID) -> Employee | None: ...

    async def get_by_code(self, code: str) -> Employee | None: ...

    async def get_by_user_id(self, user_id: uuid.UUID) -> Employee | None: ...

    async def list_active(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
        department_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> tuple[Sequence[Employee], int]:
        """Return (employees, total_count)."""

    async def get_stats(self) -> EmployeeStats:
        """Return aggregate employee counts via a single DB query."""

    async def add(self, emp: Employee) -> Employee: ...

    async def update(self, emp: Employee) -> Employee: ...

    async def soft_delete(self, emp_id: uuid.UUID) -> bool: ...

    async def link_to_user(self, emp_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...

    async def unlink_from_user(self, emp_id: uuid.UUID) -> bool: ...