"""Persistence port for explicit user-to-branch authorization."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.domain.entities.operational_context import OperationalContext


class OperationalContextRepository(Protocol):
    async def get_context(
        self, *, user_id: uuid.UUID, company_id: uuid.UUID, is_superuser: bool
    ) -> OperationalContext | None: ...

    async def save_preference(
        self,
        *,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        is_superuser: bool,
    ) -> None: ...

    async def replace_branch_access(
        self,
        *,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        branch_ids: set[uuid.UUID],
        access_all_branches: bool,
        default_branch_id: uuid.UUID | None,
        assigned_by: uuid.UUID,
    ) -> OperationalContext: ...
