"""Eventos de retorno sobre facturas (revisión 0138, bloque V4d2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.fiscal_contingency import ContingencyResponsible
from app.domain.entities.sales_fiscal_notes import Nature
from app.domain.entities.sales_fiscal_returns import (
    VIGENT_STATUSES,
    AnnulStatus,
    PriorReturnLine,
    ReturnStatus,
)
from app.domain.ports.sales_fiscal_return_repository import FiscalReturn, ReturnLineRecord
from app.infrastructure.models.sales_fiscal import (
    SalesFiscalReturnLineModel,
    SalesFiscalReturnModel,
)

#: Lo que cambia después de crear el retorno.
_MUTABLE = (
    "attempts",
    "generation_code",
    "seal",
    "dte_json",
    "json_object_key",
    "pdf_object_key",
    "error_code",
    "error_message",
    "issued_at",
    "annul_idempotency_key",
    "annul_attempts",
    "annul_generation_code",
    "annul_seal",
    "annul_error_code",
    "annul_error_message",
    "annul_requested_by_id",
    "annul_requested_at",
    "annulled_at",
)


def _person(
    name: str | None, kind: str | None, number: str | None
) -> ContingencyResponsible | None:
    return ContingencyResponsible(name, kind or "", number or "") if name else None


def _entity(model: SalesFiscalReturnModel, lines: list[SalesFiscalReturnLineModel]) -> FiscalReturn:
    return FiscalReturn(
        id=model.id,
        company_id=model.company_id,
        document_id=model.document_id,
        reason=model.reason,
        status=ReturnStatus(model.status),
        idempotency_key=model.idempotency_key,
        request_payload=model.request_payload,
        total=model.total,
        created_by_id=model.created_by_id,
        lines=tuple(
            ReturnLineRecord(
                line_number=line.line_number,
                invoice_line_number=line.invoice_line_number,
                nature=Nature(line.nature),
                description=line.description,
                quantity=line.quantity,
                amount=line.amount,
                vat=line.vat,
            )
            for line in sorted(lines, key=lambda item: item.line_number)
        ),
        attempts=model.attempts,
        generation_code=model.generation_code,
        seal=model.seal,
        dte_json=model.dte_json,
        json_object_key=model.json_object_key,
        pdf_object_key=model.pdf_object_key,
        error_code=model.error_code,
        error_message=model.error_message,
        issued_at=model.issued_at,
        annul_status=AnnulStatus(model.annul_status) if model.annul_status else None,
        annul_idempotency_key=model.annul_idempotency_key,
        annul_attempts=model.annul_attempts,
        annul_requester=_person(
            model.annul_requester_name,
            model.annul_requester_document_type,
            model.annul_requester_document_number,
        ),
        annul_responsible=_person(
            model.annul_responsible_name,
            model.annul_responsible_document_type,
            model.annul_responsible_document_number,
        ),
        annul_generation_code=model.annul_generation_code,
        annul_seal=model.annul_seal,
        annul_error_code=model.annul_error_code,
        annul_error_message=model.annul_error_message,
        annul_requested_by_id=model.annul_requested_by_id,
        annul_requested_at=model.annul_requested_at,
        annulled_at=model.annulled_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemySalesFiscalReturnRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _lines(
        self, company_id: uuid.UUID, return_id: uuid.UUID
    ) -> list[SalesFiscalReturnLineModel]:
        rows = await self._session.scalars(
            select(SalesFiscalReturnLineModel).where(
                SalesFiscalReturnLineModel.company_id == company_id,
                SalesFiscalReturnLineModel.return_id == return_id,
            )
        )
        return list(rows)

    async def _entity(self, model: SalesFiscalReturnModel) -> FiscalReturn:
        return _entity(model, await self._lines(model.company_id, model.id))

    async def create(self, item: FiscalReturn) -> FiscalReturn:
        model = SalesFiscalReturnModel(
            id=item.id,
            company_id=item.company_id,
            document_id=item.document_id,
            reason=item.reason,
            status=item.status.value,
            idempotency_key=item.idempotency_key,
            request_payload=item.request_payload,
            total=item.total,
            created_by_id=item.created_by_id,
        )
        self._session.add(model)
        await self._session.flush()
        self._session.add_all(
            [
                SalesFiscalReturnLineModel(
                    company_id=item.company_id,
                    return_id=item.id,
                    line_number=line.line_number,
                    invoice_line_number=line.invoice_line_number,
                    nature=line.nature.value,
                    description=line.description,
                    quantity=line.quantity,
                    amount=line.amount,
                    vat=line.vat,
                )
                for line in item.lines
            ]
        )
        await self._session.flush()
        await self._session.refresh(model)
        return await self._entity(model)

    async def get(
        self, company_id: uuid.UUID, return_id: uuid.UUID, *, lock: bool = False
    ) -> FiscalReturn | None:
        statement = select(SalesFiscalReturnModel).where(
            SalesFiscalReturnModel.company_id == company_id,
            SalesFiscalReturnModel.id == return_id,
        )
        if lock:
            statement = statement.with_for_update()
        model = await self._session.scalar(statement)
        return await self._entity(model) if model else None

    async def by_id(self, return_id: uuid.UUID) -> FiscalReturn | None:
        model = await self._session.get(SalesFiscalReturnModel, return_id)
        return await self._entity(model) if model else None

    async def for_document(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[FiscalReturn]:
        rows = await self._session.scalars(
            select(SalesFiscalReturnModel)
            .where(
                SalesFiscalReturnModel.company_id == company_id,
                SalesFiscalReturnModel.document_id == document_id,
            )
            .order_by(SalesFiscalReturnModel.created_at.desc())
        )
        return [await self._entity(model) for model in rows]

    async def prior_lines(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[PriorReturnLine]:
        rows = await self._session.execute(
            select(
                SalesFiscalReturnLineModel.invoice_line_number,
                SalesFiscalReturnLineModel.quantity,
                SalesFiscalReturnLineModel.amount,
            )
            .join(
                SalesFiscalReturnModel,
                (SalesFiscalReturnModel.company_id == SalesFiscalReturnLineModel.company_id)
                & (SalesFiscalReturnModel.id == SalesFiscalReturnLineModel.return_id),
            )
            .where(
                SalesFiscalReturnModel.company_id == company_id,
                SalesFiscalReturnModel.document_id == document_id,
                SalesFiscalReturnModel.status.in_([s.value for s in VIGENT_STATUSES]),
            )
        )
        return [PriorReturnLine(number, quantity, amount) for number, quantity, amount in rows]

    async def vigent_count(self, company_id: uuid.UUID, document_id: uuid.UUID) -> int:
        count = await self._session.scalar(
            select(func.count()).where(
                SalesFiscalReturnModel.company_id == company_id,
                SalesFiscalReturnModel.document_id == document_id,
                SalesFiscalReturnModel.status.in_([s.value for s in VIGENT_STATUSES]),
            )
        )
        return int(count or 0)

    async def save(self, item: FiscalReturn) -> FiscalReturn:
        model = await self._session.get(SalesFiscalReturnModel, item.id)
        assert model is not None
        model.status = item.status.value
        model.annul_status = item.annul_status.value if item.annul_status else None
        requester, responsible = item.annul_requester, item.annul_responsible
        model.annul_requester_name = requester.name if requester else None
        model.annul_requester_document_type = requester.document_type if requester else None
        model.annul_requester_document_number = requester.document_number if requester else None
        model.annul_responsible_name = responsible.name if responsible else None
        model.annul_responsible_document_type = responsible.document_type if responsible else None
        model.annul_responsible_document_number = (
            responsible.document_number if responsible else None
        )
        for name in _MUTABLE:
            setattr(model, name, getattr(item, name))
        await self._session.flush()
        await self._session.refresh(model)
        return await self._entity(model)

    async def claim(self, return_id: uuid.UUID) -> FiscalReturn | None:
        """Toma un retorno pendiente de emitir y cuenta el intento."""

        model = await self._session.scalar(
            select(SalesFiscalReturnModel)
            .where(
                SalesFiscalReturnModel.id == return_id,
                SalesFiscalReturnModel.status == ReturnStatus.PENDING.value,
            )
            .with_for_update(skip_locked=True)
        )
        if model is None:
            return None
        model.attempts += 1
        await self._session.flush()
        await self._session.refresh(model)
        return await self._entity(model)

    async def claim_annulment(self, return_id: uuid.UUID) -> FiscalReturn | None:
        """Toma la anulación pendiente de un retorno y cuenta el intento."""

        model = await self._session.scalar(
            select(SalesFiscalReturnModel)
            .where(
                SalesFiscalReturnModel.id == return_id,
                SalesFiscalReturnModel.annul_status == AnnulStatus.PENDING.value,
            )
            .with_for_update(skip_locked=True)
        )
        if model is None:
            return None
        model.annul_attempts += 1
        await self._session.flush()
        await self._session.refresh(model)
        return await self._entity(model)

    async def pending_ids(self, stale_before: datetime, limit: int) -> list[tuple[uuid.UUID, bool]]:
        """Retornos con emisión o anulación pendiente y sin movimiento reciente: (id, anulación)."""

        rows = await self._session.execute(
            select(SalesFiscalReturnModel.id, SalesFiscalReturnModel.annul_status)
            .where(
                or_(
                    SalesFiscalReturnModel.status == ReturnStatus.PENDING.value,
                    SalesFiscalReturnModel.annul_status == AnnulStatus.PENDING.value,
                ),
                SalesFiscalReturnModel.updated_at < stale_before,
            )
            .order_by(SalesFiscalReturnModel.updated_at)
            .limit(limit)
        )
        return [
            (return_id, annul_status == AnnulStatus.PENDING.value)
            for return_id, annul_status in rows
        ]
