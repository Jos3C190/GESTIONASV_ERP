"""Domain values for company and branch operational scope."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccessibleBranch:
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    code: str | None
    is_active: bool


@dataclass(frozen=True, slots=True)
class OperationalContext:
    company_id: uuid.UUID
    access_all_branches: bool
    last_branch_id: uuid.UUID | None
    branches: tuple[AccessibleBranch, ...]

    def can_access(self, branch_id: uuid.UUID) -> bool:
        return any(branch.id == branch_id for branch in self.branches)
