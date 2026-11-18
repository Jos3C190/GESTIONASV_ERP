"""Puerto del responsable de contingencias de la empresa (bloque V4a)."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.domain.entities.fiscal_contingency import ContingencyResponsible


class ContingencyResponsibleRepository(Protocol):
    async def get(self, company_id: uuid.UUID) -> ContingencyResponsible | None: ...

    async def save(
        self, company_id: uuid.UUID, responsible: ContingencyResponsible, actor_id: uuid.UUID
    ) -> ContingencyResponsible: ...
