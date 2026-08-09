"""Domain entities: Role, Permission."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Permission:
    id: uuid.UUID
    code: str
    description: str | None = None
    module: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Role:
    id: uuid.UUID
    name: str
    company_id: uuid.UUID | None = None
    description: str | None = None
    is_system: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    permissions: tuple[Permission, ...] = ()

    def with_permissions(self, perms: tuple[Permission, ...]) -> Role:
        return Role(
            id=self.id,
            name=self.name,
            company_id=self.company_id,
            description=self.description,
            is_system=self.is_system,
            created_at=self.created_at,
            updated_at=self.updated_at,
            permissions=perms,
        )


@dataclass(frozen=True, slots=True)
class UserRoleAssignment:
    user_id: uuid.UUID
    role_id: uuid.UUID
    company_id: uuid.UUID
    assigned_by: uuid.UUID | None
    assigned_at: datetime | None = None
