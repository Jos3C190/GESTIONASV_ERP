"""SQLAlchemy persistence for original supplier quotation documents."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.purchase_quotation import PurchaseQuotationStatus
from app.domain.entities.purchase_quotation_document import PurchaseQuotationDocument
from app.domain.ports.purchase_quotation_document_repository import (
    PurchaseQuotationDocumentReference,
)
from app.infrastructure.models.purchase_quotation import (
    PurchaseQuotationDocumentModel,
    PurchaseQuotationModel,
)


def _to_entity(model: PurchaseQuotationDocumentModel) -> PurchaseQuotationDocument:
    return PurchaseQuotationDocument(
        id=model.id,
        company_id=model.company_id,
        purchase_quotation_id=model.purchase_quotation_id,
        document_id=model.document_id,
        file_name=model.file_name,
        file_type=model.file_type,
        uploaded_at=model.uploaded_at,
        deleted_at=model.deleted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyPurchaseQuotationDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_quotation_reference(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID
    ) -> PurchaseQuotationDocumentReference | None:
        row = await self._session.execute(
            select(PurchaseQuotationModel.id, PurchaseQuotationModel.status).where(
                PurchaseQuotationModel.company_id == company_id,
                PurchaseQuotationModel.id == quotation_id,
            )
        )
        result = row.one_or_none()
        if result is None:
            return None
        stored_id, status = result
        return PurchaseQuotationDocumentReference(
            quotation_id=stored_id,
            status=PurchaseQuotationStatus(status),
        )

    async def add_document(
        self, attachment: PurchaseQuotationDocument
    ) -> PurchaseQuotationDocument:
        model = PurchaseQuotationDocumentModel(
            id=attachment.id,
            company_id=attachment.company_id,
            purchase_quotation_id=attachment.purchase_quotation_id,
            document_id=attachment.document_id,
            file_name=attachment.file_name,
            file_type=attachment.file_type,
            uploaded_at=attachment.uploaded_at,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)

    async def get_document(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> PurchaseQuotationDocument | None:
        result = await self._session.execute(
            self._scoped_statement(company_id, quotation_id).where(
                PurchaseQuotationDocumentModel.document_id == document_id
            )
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def list_documents(
        self, company_id: uuid.UUID, quotation_id: uuid.UUID
    ) -> Sequence[PurchaseQuotationDocument]:
        result = await self._session.execute(
            self._scoped_statement(company_id, quotation_id).order_by(
                PurchaseQuotationDocumentModel.created_at,
                PurchaseQuotationDocumentModel.id,
            )
        )
        return tuple(_to_entity(model) for model in result.scalars().all())

    async def mark_uploaded(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        file_type: str,
        uploaded_at: datetime,
    ) -> PurchaseQuotationDocument | None:
        result = await self._session.execute(
            self._scoped_statement(company_id, quotation_id)
            .where(PurchaseQuotationDocumentModel.document_id == document_id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        model.file_type = file_type
        model.uploaded_at = uploaded_at
        await self._session.flush()
        return _to_entity(model)

    async def detach_document(
        self,
        company_id: uuid.UUID,
        quotation_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        deleted_at: datetime,
    ) -> PurchaseQuotationDocument | None:
        result = await self._session.execute(
            self._scoped_statement(company_id, quotation_id)
            .where(PurchaseQuotationDocumentModel.document_id == document_id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        model.deleted_at = deleted_at
        await self._session.flush()
        return _to_entity(model)

    @staticmethod
    def _scoped_statement(
        company_id: uuid.UUID, quotation_id: uuid.UUID
    ) -> Select[tuple[PurchaseQuotationDocumentModel]]:
        return (
            select(PurchaseQuotationDocumentModel)
            .join(
                PurchaseQuotationModel,
                and_(
                    PurchaseQuotationModel.id
                    == PurchaseQuotationDocumentModel.purchase_quotation_id,
                    PurchaseQuotationModel.company_id == PurchaseQuotationDocumentModel.company_id,
                ),
            )
            .where(
                PurchaseQuotationDocumentModel.company_id == company_id,
                PurchaseQuotationDocumentModel.purchase_quotation_id == quotation_id,
                PurchaseQuotationDocumentModel.deleted_at.is_(None),
                PurchaseQuotationModel.company_id == company_id,
            )
        )
