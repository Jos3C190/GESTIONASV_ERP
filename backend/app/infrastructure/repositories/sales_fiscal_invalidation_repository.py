"""Invalidaciones de documentos fiscales (revisión 0131, bloque V4b)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.fiscal_contingency import ContingencyResponsible
from app.domain.entities.sales_fiscal_invalidation import (
    FiscalInvalidation,
    InvalidationKind,
    InvalidationStatus,
)
from app.infrastructure.models.sales_fiscal import SalesFiscalInvalidationModel

#: Lo que cambia después de crear la solicitud.
_MUTABLE = (
    "attempts",
    "event_generation_code",
    "event_seal",
    "error_code",
    "error_message",
    "resolved_at",
)


def _entity(model: SalesFiscalInvalidationModel) -> FiscalInvalidation:
    responsible = (
        ContingencyResponsible(
            model.responsible_name,
            model.responsible_document_type or "",
            model.responsible_document_number or "",
        )
        if model.responsible_name
        else None
    )
    return FiscalInvalidation(
        id=model.id,
        company_id=model.company_id,
        document_id=model.document_id,
        kind=InvalidationKind(model.kind),
        reason=model.reason,
        requester=ContingencyResponsible(
            model.requester_name, model.requester_document_type, model.requester_document_number
        ),
        requested_by_id=model.requested_by_id,
        idempotency_key=model.idempotency_key,
        status=InvalidationStatus(model.status),
        responsible=responsible,
        replacement_document_id=model.replacement_document_id,
        cancel_order=model.cancel_order,
        attempts=model.attempts,
        event_generation_code=model.event_generation_code,
        event_seal=model.event_seal,
        error_code=model.error_code,
        error_message=model.error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
        resolved_at=model.resolved_at,
    )


class SqlAlchemySalesFiscalInvalidationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, invalidation: FiscalInvalidation) -> FiscalInvalidation:
        responsible = invalidation.responsible
        model = SalesFiscalInvalidationModel(
            id=invalidation.id,
            company_id=invalidation.company_id,
            document_id=invalidation.document_id,
            kind=int(invalidation.kind),
            reason=invalidation.reason,
            requester_name=invalidation.requester.name,
            requester_document_type=invalidation.requester.document_type,
            requester_document_number=invalidation.requester.document_number,
            responsible_name=responsible.name if responsible else None,
            responsible_document_type=responsible.document_type if responsible else None,
            responsible_document_number=responsible.document_number if responsible else None,
            replacement_document_id=invalidation.replacement_document_id,
            cancel_order=invalidation.cancel_order,
            status=invalidation.status.value,
            idempotency_key=invalidation.idempotency_key,
            requested_by_id=invalidation.requested_by_id,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _entity(model)

    async def get(
        self, company_id: uuid.UUID, invalidation_id: uuid.UUID
    ) -> FiscalInvalidation | None:
        model = await self._session.scalar(
            select(SalesFiscalInvalidationModel).where(
                SalesFiscalInvalidationModel.company_id == company_id,
                SalesFiscalInvalidationModel.id == invalidation_id,
            )
        )
        return _entity(model) if model else None

    async def by_key(
        self, company_id: uuid.UUID, idempotency_key: str
    ) -> FiscalInvalidation | None:
        model = await self._session.scalar(
            select(SalesFiscalInvalidationModel).where(
                SalesFiscalInvalidationModel.company_id == company_id,
                SalesFiscalInvalidationModel.idempotency_key == idempotency_key,
            )
        )
        return _entity(model) if model else None

    async def pending_for_document(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> FiscalInvalidation | None:
        model = await self._session.scalar(
            select(SalesFiscalInvalidationModel).where(
                SalesFiscalInvalidationModel.company_id == company_id,
                SalesFiscalInvalidationModel.document_id == document_id,
                SalesFiscalInvalidationModel.status == InvalidationStatus.PENDING.value,
            )
        )
        return _entity(model) if model else None

    async def for_document(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[FiscalInvalidation]:
        rows = await self._session.scalars(
            select(SalesFiscalInvalidationModel)
            .where(
                SalesFiscalInvalidationModel.company_id == company_id,
                SalesFiscalInvalidationModel.document_id == document_id,
            )
            .order_by(SalesFiscalInvalidationModel.created_at.desc())
        )
        return [_entity(model) for model in rows]

    async def save(self, invalidation: FiscalInvalidation) -> FiscalInvalidation:
        model = await self._session.get(SalesFiscalInvalidationModel, invalidation.id)
        assert model is not None
        model.status = invalidation.status.value
        for name in _MUTABLE:
            setattr(model, name, getattr(invalidation, name))
        await self._session.flush()
        await self._session.refresh(model)
        return _entity(model)

    async def claim(self, invalidation_id: uuid.UUID) -> FiscalInvalidation | None:
        model = await self._session.scalar(
            select(SalesFiscalInvalidationModel)
            .where(
                SalesFiscalInvalidationModel.id == invalidation_id,
                SalesFiscalInvalidationModel.status == InvalidationStatus.PENDING.value,
            )
            .with_for_update(skip_locked=True)
        )
        if model is None:
            return None
        model.attempts += 1
        await self._session.flush()
        await self._session.refresh(model)
        return _entity(model)

    async def pending_ids(self, updated_before: datetime, limit: int) -> list[uuid.UUID]:
        rows = await self._session.scalars(
            select(SalesFiscalInvalidationModel.id)
            .where(
                SalesFiscalInvalidationModel.status == InvalidationStatus.PENDING.value,
                SalesFiscalInvalidationModel.updated_at < updated_before,
            )
            .order_by(SalesFiscalInvalidationModel.updated_at)
            .limit(limit)
        )
        return list(rows)
