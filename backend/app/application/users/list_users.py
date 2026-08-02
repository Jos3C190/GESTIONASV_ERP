"""Use case: ListUsers — paginated list with optional search."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.entities.user import User
from app.domain.ports.user_repository import UserRepository


@dataclass(frozen=True, slots=True)
class ListUsersInput:
    page: int = 1
    size: int = 20
    search: str | None = None
    status_filter: str | None = None
    company_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ListUsersResult:
    items: Sequence[User]
    total: int
    page: int
    size: int
    pages: int


class ListUsersUseCase:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, inp: ListUsersInput) -> ListUsersResult:
        page = max(inp.page, 1)
        size = max(min(inp.size, 100), 1)
        offset = (page - 1) * size
        if inp.company_id is None and inp.branch_id is None:
            items, total = await self._users.list_active(
                offset=offset, limit=size, search=inp.search, status_filter=inp.status_filter
            )
        else:
            items, total = await self._users.list_active(
                offset=offset,
                limit=size,
                search=inp.search,
                status_filter=inp.status_filter,
                company_id=inp.company_id,
                branch_id=inp.branch_id,
            )
        pages = (total + size - 1) // size if total else 1
        return ListUsersResult(items=items, total=total, page=page, size=size, pages=pages)
