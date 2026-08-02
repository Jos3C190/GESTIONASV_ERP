"""In-memory fakes for RBAC ports, used by unit tests."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from app.domain.entities.rbac import Permission, Role, UserRoleAssignment


class InMemoryPermissionRepository:
    def __init__(self) -> None:
        self._by_id: dict[uuid.UUID, Permission] = {}
        self._by_code: dict[str, Permission] = {}

    async def get_by_id(self, permission_id: uuid.UUID) -> Permission | None:
        return self._by_id.get(permission_id)

    async def get_by_code(self, code: str) -> Permission | None:
        return self._by_code.get(code)

    async def list_all(self) -> Sequence[Permission]:
        return list(self._by_id.values())

    async def list_by_module(self, module: str) -> Sequence[Permission]:
        return [p for p in self._by_id.values() if p.module == module]

    async def add(self, permission: Permission) -> Permission:
        pid = uuid.uuid4()
        p = Permission(
            id=pid,
            code=permission.code,
            description=permission.description,
            module=permission.module,
            created_at=datetime.now(UTC),
        )
        self._by_id[pid] = p
        self._by_code[p.code] = p
        return p

    async def update(self, permission: Permission) -> Permission:
        previous = self._by_id.get(permission.id)
        if previous is not None:
            self._by_code.pop(previous.code, None)
        self._by_id[permission.id] = permission
        self._by_code[permission.code] = permission
        return permission

    async def is_assigned(self, permission_id: uuid.UUID) -> bool:
        return False

    async def delete(self, permission_id: uuid.UUID) -> bool:
        permission = self._by_id.pop(permission_id, None)
        if permission is None:
            return False
        self._by_code.pop(permission.code, None)
        return True

    async def bulk_add(self, permissions: Sequence[Permission]) -> int:
        for p in permissions:
            await self.add(p)
        return len(permissions)


class InMemoryRoleRepository:
    def __init__(self) -> None:
        self._roles_by_id: dict[uuid.UUID, Role] = {}
        # role_id -> list of Permission objects (not just ids)
        self._role_perms: dict[uuid.UUID, list[Permission]] = {}
        self._user_roles: dict[uuid.UUID, set[uuid.UUID]] = {}
        self._assignments: list[UserRoleAssignment] = []
        self._all_perms: list[Permission] = []

    def register_perms(self, perms: list[Permission]) -> None:
        self._all_perms = perms

    async def get_by_id(self, role_id: uuid.UUID, *, load_permissions: bool = False) -> Role | None:
        r = self._roles_by_id.get(role_id)
        if r is None:
            return None
        if load_permissions:
            perms = tuple(self._role_perms.get(role_id, []))
            return Role(
                id=r.id,
                name=r.name,
                description=r.description,
                is_system=r.is_system,
                created_at=r.created_at,
                updated_at=r.updated_at,
                permissions=perms,
            )
        return r

    async def get_by_name(self, name: str, *, load_permissions: bool = False) -> Role | None:
        for r in self._roles_by_id.values():
            if r.name == name:
                return await self.get_by_id(r.id, load_permissions=load_permissions)
        return None

    async def list_all(self, *, load_permissions: bool = False) -> Sequence[Role]:
        if not load_permissions:
            return list(self._roles_by_id.values())
        out = []
        for rid in self._roles_by_id:
            r = await self.get_by_id(rid, load_permissions=True)
            if r:
                out.append(r)
        return out

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        is_system: bool | None = None,
        module: str | None = None,
        load_permissions: bool = False,
    ) -> tuple[Sequence[Role], int]:
        roles = list(await self.list_all(load_permissions=load_permissions))
        if search:
            query = search.casefold()
            roles = [
                role
                for role in roles
                if query in role.name.casefold()
                or query in (role.description or "").casefold()
                or any(query in permission.code.casefold() for permission in role.permissions)
            ]
        if is_system is not None:
            roles = [role for role in roles if role.is_system is is_system]
        if module:
            roles = [
                role
                for role in roles
                if any(permission.module == module for permission in role.permissions)
            ]
        roles.sort(key=lambda role: (role.name, role.id))
        return roles[offset : offset + limit], len(roles)

    async def add(self, role: Role) -> Role:
        rid = uuid.uuid4()
        r = Role(
            id=rid,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._roles_by_id[rid] = r
        self._role_perms[rid] = []
        return r

    async def update(self, role: Role) -> Role:
        if role.id not in self._roles_by_id:
            raise LookupError(f"Role {role.id} not found")
        self._roles_by_id[role.id] = role
        return role

    async def delete(self, role_id: uuid.UUID) -> bool:
        r = self._roles_by_id.get(role_id)
        if r is None or r.is_system:
            return False
        del self._roles_by_id[role_id]
        self._role_perms.pop(role_id, None)
        return True

    async def is_assigned(self, role_id: uuid.UUID) -> bool:
        return any(role_id in roles for roles in self._user_roles.values())

    async def set_permissions(self, role_id: uuid.UUID, permission_ids: set[uuid.UUID]) -> None:
        # Convert ids back to Permission objects using the catalog we keep.
        all_perms = {p.id: p for p in self._all_perms}
        self._role_perms[role_id] = [all_perms[pid] for pid in permission_ids if pid in all_perms]

    async def get_permissions_for_role(self, role_id: uuid.UUID) -> Sequence[Permission]:
        return list(self._role_perms.get(role_id, []))

    async def get_effective_permissions_for_user(self, user_id: uuid.UUID) -> Sequence[Permission]:
        role_ids = self._user_roles.get(user_id, set())
        seen: dict[uuid.UUID, Permission] = {}
        for rid in role_ids:
            for p in self._role_perms.get(rid, []):
                seen[p.id] = p
        return list(seen.values())

    async def get_roles_for_user(self, user_id: uuid.UUID) -> Sequence[Role]:
        role_ids = self._user_roles.get(user_id, set())
        return [self._roles_by_id[rid] for rid in role_ids if rid in self._roles_by_id]

    async def assign_role_to_user(
        self, user_id: uuid.UUID, role_id: uuid.UUID, assigned_by: uuid.UUID
    ) -> bool:
        if role_id not in self._roles_by_id:
            return False
        roles = self._user_roles.setdefault(user_id, set())
        if role_id in roles:
            return False
        roles.add(role_id)
        self._assignments.append(
            UserRoleAssignment(
                user_id=user_id,
                role_id=role_id,
                assigned_by=assigned_by,
                assigned_at=datetime.now(UTC),
            )
        )
        return True

    async def revoke_role_from_user(self, user_id: uuid.UUID, role_id: uuid.UUID) -> bool:
        roles = self._user_roles.get(user_id, set())
        if role_id not in roles:
            return False
        roles.discard(role_id)
        return True

    async def list_user_role_assignments(self, user_id: uuid.UUID) -> Sequence[UserRoleAssignment]:
        return [a for a in self._assignments if a.user_id == user_id]
