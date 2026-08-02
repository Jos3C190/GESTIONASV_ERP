"""Strict API DTOs for operational company and branch scope."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, model_validator


class AccessibleBranchOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    code: str | None = None
    is_active: bool


class OperationalContextOut(BaseModel):
    company_id: uuid.UUID
    access_all_branches: bool
    last_branch_id: uuid.UUID | None = None
    branches: list[AccessibleBranchOut]


class ContextPreferenceIn(BaseModel):
    branch_id: uuid.UUID | None = None


class UserBranchAccessIn(BaseModel):
    access_all_branches: bool = False
    branch_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    default_branch_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> UserBranchAccessIn:
        if len(self.branch_ids) != len(set(self.branch_ids)):
            raise ValueError("No se permiten sucursales duplicadas.")
        if not self.access_all_branches and not self.branch_ids:
            raise ValueError("Debe asignar al menos una sucursal.")
        if (
            not self.access_all_branches
            and self.default_branch_id is not None
            and self.default_branch_id not in self.branch_ids
        ):
            raise ValueError("La sucursal predeterminada debe estar asignada.")
        return self
