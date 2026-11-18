"""Envíos por correo del documento fiscal en PostgreSQL (bloque V3c)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.sales_fiscal_email import EmailOrigin, EmailStatus
from app.domain.ports.sales_fiscal_repository import FiscalDocumentEmail
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.sales_fiscal import SalesFiscalDocumentEmailModel
from app.infrastructure.models.user import User

_MUTABLE = ("attempts", "error_code", "error_message", "message_id", "sent_at")


def _query() -> Select[Any]:
    return (
        select(
            SalesFiscalDocumentEmailModel,
            User.username,
            Employee.first_name,
            Employee.last_name,
        )
        .outerjoin(User, User.id == SalesFiscalDocumentEmailModel.requested_by_id)
        .outerjoin(Employee, (Employee.user_id == User.id) & Employee.deleted_at.is_(None))
    )


def _entity(row: Any) -> FiscalDocumentEmail:
    model, username, first, last = row
    full = f"{first or ''} {last or ''}".strip()
    return FiscalDocumentEmail(
        id=model.id,
        company_id=model.company_id,
        document_id=model.document_id,
        recipients=tuple(model.recipients),
        origin=model.origin,
        status=model.status,
        attempts=model.attempts,
        error_code=model.error_code,
        error_message=model.error_message,
        message_id=model.message_id,
        requested_by_id=model.requested_by_id,
        requested_by_name=full or username,
        invalidation_id=model.invalidation_id,
        sent_at=model.sent_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemySalesFiscalEmailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get(self, email_id: uuid.UUID) -> FiscalDocumentEmail:
        row = (
            await self._session.execute(
                _query().where(SalesFiscalDocumentEmailModel.id == email_id)
            )
        ).one()
        return _entity(row)

    async def create(self, email: FiscalDocumentEmail) -> FiscalDocumentEmail:
        self._session.add(
            SalesFiscalDocumentEmailModel(
                id=email.id,
                company_id=email.company_id,
                document_id=email.document_id,
                recipients=list(email.recipients),
                origin=email.origin,
                status=email.status,
                requested_by_id=email.requested_by_id,
                invalidation_id=email.invalidation_id,
            )
        )
        await self._session.flush()
        return await self._get(email.id)

    async def auto_exists(self, company_id: uuid.UUID, document_id: uuid.UUID) -> bool:
        found = await self._session.scalar(
            select(SalesFiscalDocumentEmailModel.id).where(
                SalesFiscalDocumentEmailModel.company_id == company_id,
                SalesFiscalDocumentEmailModel.document_id == document_id,
                SalesFiscalDocumentEmailModel.origin == EmailOrigin.AUTO.value,
                SalesFiscalDocumentEmailModel.invalidation_id.is_(None),
            )
        )
        return found is not None

    async def invalidation_email_exists(
        self, company_id: uuid.UUID, invalidation_id: uuid.UUID
    ) -> bool:
        found = await self._session.scalar(
            select(SalesFiscalDocumentEmailModel.id).where(
                SalesFiscalDocumentEmailModel.company_id == company_id,
                SalesFiscalDocumentEmailModel.invalidation_id == invalidation_id,
                SalesFiscalDocumentEmailModel.origin == EmailOrigin.AUTO.value,
            )
        )
        return found is not None

    async def list_for_document(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[FiscalDocumentEmail]:
        rows = await self._session.execute(
            _query()
            .where(
                SalesFiscalDocumentEmailModel.company_id == company_id,
                SalesFiscalDocumentEmailModel.document_id == document_id,
            )
            .order_by(SalesFiscalDocumentEmailModel.created_at.desc())
        )
        return [_entity(row) for row in rows.all()]

    async def claim(self, email_id: uuid.UUID) -> FiscalDocumentEmail | None:
        model = await self._session.scalar(
            select(SalesFiscalDocumentEmailModel)
            .where(
                SalesFiscalDocumentEmailModel.id == email_id,
                SalesFiscalDocumentEmailModel.status == EmailStatus.PENDING.value,
            )
            .with_for_update(skip_locked=True)
        )
        if model is None:
            return None
        model.attempts += 1
        await self._session.flush()
        return await self._get(model.id)

    async def save(self, email: FiscalDocumentEmail) -> FiscalDocumentEmail:
        await self._session.execute(
            update(SalesFiscalDocumentEmailModel)
            .where(
                SalesFiscalDocumentEmailModel.company_id == email.company_id,
                SalesFiscalDocumentEmailModel.id == email.id,
            )
            .values(
                status=email.status,
                updated_at=func.now(),
                **{name: getattr(email, name) for name in _MUTABLE},
            )
        )
        return await self._get(email.id)

    async def pending_ids(self, updated_before: datetime, limit: int) -> list[uuid.UUID]:
        rows = await self._session.scalars(
            select(SalesFiscalDocumentEmailModel.id)
            .where(
                SalesFiscalDocumentEmailModel.status == EmailStatus.PENDING.value,
                SalesFiscalDocumentEmailModel.updated_at < updated_before,
            )
            .order_by(SalesFiscalDocumentEmailModel.updated_at)
            .limit(limit)
        )
        return list(rows)
