"""Port: DepartmentRepository."""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Protocol

from app.domain.entities.employee import Department


class DepartmentRepository(Protocol):
    async def get_by_id(self, dept_id: uuid.UUID) -> Department | None: ...

    async def get_by_name(self, company_id: uuid.UUID, name: str) -> Department | None: ...

    async def list_all(self, company_id: uuid.UUID) -> Sequence[Department]: ...

    async def list_page(
        self,
        company_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        level: str | None = None,
    ) -> tuple[Sequence[Department], int]: ...

    async def list_children(self, parent_id: uuid.UUID) -> Sequence[Department]: ...

    async def get_ancestor_chain(self, dept_id: uuid.UUID) -> Sequence[Department]:
        """Return the chain from the dept up to the root (for cycle detection)."""

    async def add(self, dept: Department) -> Department: ...

    async def update(self, dept: Department) -> Department: ...

    async def delete(self, dept_id: uuid.UUID) -> bool: ...

    async def has_employees(self, dept_id: uuid.UUID) -> bool: ...
