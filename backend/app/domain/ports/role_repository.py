"""Port: RoleRepository."""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Protocol

from app.domain.entities.rbac import Permission, Role


class RoleRepository(Protocol):
    async def get_by_id(self, role_id: uuid.UUID, *, load_permissions: bool = False) -> Role | None: ...

    async def get_by_name(self, name: str, *, load_permissions: bool = False) -> Role | None: ...

    async def list_all(self, *, load_permissions: bool = False) -> Sequence[Role]: ...

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        is_system: bool | None = None,
        module: str | None = None,
        load_permissions: bool = False,
    ) -> tuple[Sequence[Role], int]: ...

    async def add(self, role: Role) -> Role: ...

    async def update(self, role: Role) -> Role: ...

    async def delete(self, role_id: uuid.UUID) -> bool: ...

    async def is_assigned(self, role_id: uuid.UUID) -> bool: ...

    async def set_permissions(self, role_id: uuid.UUID, permission_ids: set[uuid.UUID]) -> None: ...

    async def get_permissions_for_role(self, role_id: uuid.UUID) -> Sequence[Permission]: ...

    async def get_effective_permissions_for_user(self, user_id: uuid.UUID) -> Sequence[Permission]: ...

    async def get_roles_for_user(self, user_id: uuid.UUID) -> Sequence[Role]: ...

    async def get_roles_for_users(
        self, user_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, Sequence[Role]]: ...

    async def assign_role_to_user(
        self, user_id: uuid.UUID, role_id: uuid.UUID, assigned_by: uuid.UUID
    ) -> bool: ...

    async def revoke_role_from_user(self, user_id: uuid.UUID, role_id: uuid.UUID) -> bool: ...

    async def list_user_role_assignments(self, user_id: uuid.UUID) -> Sequence[object]: ...
