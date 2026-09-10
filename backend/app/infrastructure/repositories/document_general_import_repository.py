from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.document_general_import import (
    DocumentGeneralImport,
    DocumentGeneralImportItem,
    GeneralImportItemKind,
    GeneralImportItemStatus,
    GeneralImportStatus,
)
from app.infrastructure.models.document_general_import import (
    DocumentGeneralImportItemModel,
    DocumentGeneralImportModel,
)


def _import_to_domain(model: DocumentGeneralImportModel) -> DocumentGeneralImport:
    if model.actor_id is None:
        raise ValueError("Document general import actor is missing")

    return DocumentGeneralImport(
        id=model.id,
        company_id=model.company_id,
        actor_id=model.actor_id,
        parent_id=model.parent_id,
        root_entry_id=model.root_entry_id,
        status=cast(GeneralImportStatus, model.status),
        total_files=model.total_files,
        total_folders=model.total_folders,
        total_entries=model.total_entries,
        total_bytes=model.total_bytes,
        metadata=dict(model.metadata_json or {}),
        completed_files=model.completed_files,
        skipped_files=model.skipped_files,
        failed_files=model.failed_files,
        created_at=model.created_at,
        updated_at=model.updated_at,
        completed_at=model.completed_at,
        expires_at=model.expires_at,
    )


def _item_to_domain(model: DocumentGeneralImportItemModel) -> DocumentGeneralImportItem:
    return DocumentGeneralImportItem(
        id=model.id,
        import_id=model.import_id,
        kind=cast(GeneralImportItemKind, model.kind),
        source_path=model.source_path,
        source_name=model.source_name,
        resolved_path=model.resolved_path,
        resolved_name=model.resolved_name,
        parent_folder_id=model.parent_folder_id,
        entry_id=model.entry_id,
        document_id=model.document_id,
        size_bytes=model.size_bytes,
        content_type=model.content_type,
        extension=model.extension,
        status=cast(GeneralImportItemStatus, model.status),
        failure_code=model.failure_code,
        failure_message=model.failure_message,
        attempts=model.attempts,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _copy_import(source: DocumentGeneralImport, target: DocumentGeneralImportModel) -> None:
    for field in (
        "company_id",
        "actor_id",
        "parent_id",
        "root_entry_id",
        "status",
        "metadata",
        "total_files",
        "total_folders",
        "total_entries",
        "total_bytes",
        "completed_files",
        "skipped_files",
        "failed_files",
        "completed_at",
        "expires_at",
    ):
        setattr(target, "metadata_json" if field == "metadata" else field, getattr(source, field))


def _copy_item(source: DocumentGeneralImportItem, target: DocumentGeneralImportItemModel) -> None:
    for field in (
        "import_id",
        "kind",
        "source_path",
        "source_name",
        "resolved_path",
        "resolved_name",
        "parent_folder_id",
        "entry_id",
        "document_id",
        "size_bytes",
        "content_type",
        "extension",
        "status",
        "failure_code",
        "failure_message",
        "attempts",
    ):
        setattr(target, field, getattr(source, field))


class SqlAlchemyDocumentGeneralImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_import(self, item: DocumentGeneralImport) -> DocumentGeneralImport:
        model = DocumentGeneralImportModel(id=item.id)
        _copy_import(item, model)
        self._session.add(model)
        await self._session.flush()
        return _import_to_domain(model)

    async def save_import(self, item: DocumentGeneralImport) -> DocumentGeneralImport:
        model = await self._session.get(DocumentGeneralImportModel, item.id)
        if model is None or model.company_id != item.company_id:
            raise LookupError("Document general import not found")
        _copy_import(item, model)
        await self._session.flush()
        return _import_to_domain(model)

    async def get_import(
        self, company_id: uuid.UUID, import_id: uuid.UUID
    ) -> DocumentGeneralImport | None:
        model = await self._session.scalar(
            select(DocumentGeneralImportModel).where(
                DocumentGeneralImportModel.company_id == company_id,
                DocumentGeneralImportModel.id == import_id,
            )
        )
        return _import_to_domain(model) if model else None

    async def add_item(self, item: DocumentGeneralImportItem) -> DocumentGeneralImportItem:
        model = DocumentGeneralImportItemModel(id=item.id)
        _copy_item(item, model)
        self._session.add(model)
        await self._session.flush()
        return _item_to_domain(model)

    async def save_item(self, item: DocumentGeneralImportItem) -> DocumentGeneralImportItem:
        model = await self._session.get(DocumentGeneralImportItemModel, item.id)
        if model is None:
            raise LookupError("Document general import item not found")
        _copy_item(item, model)
        await self._session.flush()
        return _item_to_domain(model)

    async def get_item(
        self, company_id: uuid.UUID, import_id: uuid.UUID, item_id: uuid.UUID
    ) -> DocumentGeneralImportItem | None:
        model = await self._session.scalar(
            select(DocumentGeneralImportItemModel)
            .join(
                DocumentGeneralImportModel,
                DocumentGeneralImportModel.id == DocumentGeneralImportItemModel.import_id,
            )
            .where(
                DocumentGeneralImportModel.company_id == company_id,
                DocumentGeneralImportItemModel.import_id == import_id,
                DocumentGeneralImportItemModel.id == item_id,
            )
        )
        return _item_to_domain(model) if model else None

    async def list_items(
        self, company_id: uuid.UUID, import_id: uuid.UUID, *, page: int, size: int
    ) -> Sequence[DocumentGeneralImportItem]:
        statement = (
            select(DocumentGeneralImportItemModel)
            .join(
                DocumentGeneralImportModel,
                DocumentGeneralImportModel.id == DocumentGeneralImportItemModel.import_id,
            )
            .where(
                DocumentGeneralImportModel.company_id == company_id,
                DocumentGeneralImportItemModel.import_id == import_id,
            )
            .order_by(DocumentGeneralImportItemModel.source_path)
            .offset((page - 1) * size)
            .limit(size)
        )
        return [_item_to_domain(row) for row in (await self._session.scalars(statement)).all()]

    async def count_items(self, company_id: uuid.UUID, import_id: uuid.UUID) -> int:
        statement = (
            select(func.count(DocumentGeneralImportItemModel.id))
            .join(
                DocumentGeneralImportModel,
                DocumentGeneralImportModel.id == DocumentGeneralImportItemModel.import_id,
            )
            .where(
                DocumentGeneralImportModel.company_id == company_id,
                DocumentGeneralImportItemModel.import_id == import_id,
            )
        )
        return int(await self._session.scalar(statement) or 0)


__all__ = ["SqlAlchemyDocumentGeneralImportRepository"]
