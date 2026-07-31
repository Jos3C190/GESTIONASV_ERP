"""RBAC DTOs — roles, permissions, assignments."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.api.v1.schemas.common import ORMOut


class PermissionOut(ORMOut):
    id: uuid.UUID
    code: str
    description: str | None = None
    module: str | None = None


class CreatePermissionRequest(BaseModel):
    code: str = Field(..., min_length=3, max_length=120)
    description: str | None = None
    module: str | None = Field(None, max_length=64)


class UpdatePermissionRequest(BaseModel):
    code: str | None = Field(None, min_length=3, max_length=120)
    description: str | None = None
    module: str | None = Field(None, max_length=64)


class RoleOut(ORMOut):
    id: uuid.UUID
    name: str
    description: str | None = None
    is_system: bool
    created_at: datetime
    updated_at: datetime | None = None


class RoleWithPermissionsOut(RoleOut):
    permissions: list[PermissionOut] = Field(default_factory=list)


class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    description: str | None = None


class UpdateRoleRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=80)
    description: str | None = None


class DuplicateRoleRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    description: str | None = None


class SetRolePermissionsRequest(BaseModel):
    permission_codes: list[str] = Field(default_factory=list)


class AssignRoleRequest(BaseModel):
    user_id: uuid.UUID
    role_id: uuid.UUID


class RevokeRoleRequest(BaseModel):
    user_id: uuid.UUID
    role_id: uuid.UUID


class UserRoleAssignmentOut(BaseModel):
    user_id: uuid.UUID
    role_id: uuid.UUID
    assigned_by: uuid.UUID | None = None
    assigned_at: datetime | None = None


class EffectivePermissionsOut(BaseModel):
    permissions: list[str]
    is_superuser: bool
