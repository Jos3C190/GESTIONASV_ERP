"""SQLAlchemy repository for purchase-order expense document links."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.purchase_order import PurchaseOrderStatus
from app.domain.entities.purchase_order_expense_document import PurchaseOrderExpenseDocument
from app.domain.ports.purchase_order_expense_document_repository import (
    PurchaseOrderExpenseReference,
)
from app.infrastructure.models.purchase_order import (
    PurchaseOrderExpenseDocumentModel,
    PurchaseOrderExpenseModel,
    PurchaseOrderModel,
)


def _to_entity(model: PurchaseOrderExpenseDocumentModel) -> PurchaseOrderExpenseDocument:
    return PurchaseOrderExpenseDocument(
        id=model.id,
        company_id=model.company_id,
        purchase_order_expense_id=model.purchase_order_expense_id,
        document_id=model.document_id,
        file_name=model.file_name,
        file_type=model.file_type,
        uploaded_at=model.uploaded_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyPurchaseOrderExpenseDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_expense_reference(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
    ) -> PurchaseOrderExpenseReference | None:
        row = (
            await self._session.execute(
                select(
                    PurchaseOrderExpenseModel.id,
                    PurchaseOrderExpenseModel.purchase_order_id,
                    PurchaseOrderModel.status,
                )
                .join(
                    PurchaseOrderModel,
                    and_(
                        PurchaseOrderModel.id == PurchaseOrderExpenseModel.purchase_order_id,
                        PurchaseOrderModel.company_id == PurchaseOrderExpenseModel.company_id,
                    ),
                )
                .where(
                    PurchaseOrderExpenseModel.company_id == company_id,
                    PurchaseOrderExpenseModel.id == expense_id,
                    PurchaseOrderExpenseModel.purchase_order_id == order_id,
                    PurchaseOrderModel.company_id == company_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        stored_expense_id, stored_order_id, status = row
        return PurchaseOrderExpenseReference(
            order_id=stored_order_id,
            expense_id=stored_expense_id,
            status=PurchaseOrderStatus(status),
        )

    async def add_document(
        self,
        attachment: PurchaseOrderExpenseDocument,
    ) -> PurchaseOrderExpenseDocument:
        model = PurchaseOrderExpenseDocumentModel(
            id=attachment.id,
            company_id=attachment.company_id,
            purchase_order_expense_id=attachment.purchase_order_expense_id,
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
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> PurchaseOrderExpenseDocument | None:
        result = await self._session.execute(
            self._scoped_statement(company_id, order_id, expense_id).where(
                PurchaseOrderExpenseDocumentModel.document_id == document_id
            )
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model is not None else None

    async def list_documents(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
    ) -> Sequence[PurchaseOrderExpenseDocument]:
        result = await self._session.execute(
            self._scoped_statement(company_id, order_id, expense_id).order_by(
                PurchaseOrderExpenseDocumentModel.created_at,
                PurchaseOrderExpenseDocumentModel.id,
            )
        )
        return tuple(_to_entity(model) for model in result.scalars().all())

    async def mark_uploaded(
        self,
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
        document_id: uuid.UUID,
        *,
        file_type: str,
        uploaded_at: datetime,
    ) -> PurchaseOrderExpenseDocument | None:
        result = await self._session.execute(
            self._scoped_statement(company_id, order_id, expense_id)
            .where(PurchaseOrderExpenseDocumentModel.document_id == document_id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        model.file_type = file_type
        model.uploaded_at = uploaded_at
        await self._session.flush()
        return _to_entity(model)

    @staticmethod
    def _scoped_statement(
        company_id: uuid.UUID,
        order_id: uuid.UUID,
        expense_id: uuid.UUID,
    ) -> Select[tuple[PurchaseOrderExpenseDocumentModel]]:
        return (
            select(PurchaseOrderExpenseDocumentModel)
            .join(
                PurchaseOrderExpenseModel,
                and_(
                    PurchaseOrderExpenseModel.id
                    == PurchaseOrderExpenseDocumentModel.purchase_order_expense_id,
                    PurchaseOrderExpenseModel.company_id
                    == PurchaseOrderExpenseDocumentModel.company_id,
                ),
            )
            .where(
                PurchaseOrderExpenseDocumentModel.company_id == company_id,
                PurchaseOrderExpenseDocumentModel.purchase_order_expense_id == expense_id,
                PurchaseOrderExpenseModel.purchase_order_id == order_id,
            )
        )
