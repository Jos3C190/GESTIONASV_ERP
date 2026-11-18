"""Responsable de contingencias de la empresa (bloque V4a)."""

from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.fiscal_contingency import ContingencyResponsible
from app.infrastructure.models.fiscal import CompanyContingencyResponsibleModel


class SqlAlchemyContingencyResponsibleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, company_id: uuid.UUID) -> ContingencyResponsible | None:
        model = await self._session.get(CompanyContingencyResponsibleModel, company_id)
        if model is None:
            return None
        return ContingencyResponsible(model.name, model.document_type, model.document_number)

    async def save(
        self, company_id: uuid.UUID, responsible: ContingencyResponsible, actor_id: uuid.UUID
    ) -> ContingencyResponsible:
        values = {
            "name": responsible.name,
            "document_type": responsible.document_type,
            "document_number": responsible.document_number,
            "updated_by": actor_id,
        }
        await self._session.execute(
            insert(CompanyContingencyResponsibleModel)
            .values(company_id=company_id, **values)
            .on_conflict_do_update(
                index_elements=[CompanyContingencyResponsibleModel.company_id],
                set_={**values, "updated_at": func.now()},
            )
        )
        await self._session.flush()
        return responsible
