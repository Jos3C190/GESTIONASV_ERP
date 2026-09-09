from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.document_general_entry import DocumentGeneralEntry, GeneralDeletionBatch
from app.infrastructure.models.document import DocumentAssetModel
from app.infrastructure.models.document_general_entry import (
    DocumentGeneralDeletionBatchModel,
    DocumentGeneralEntryModel,
)
from app.infrastructure.models.document_record import DocumentCategoryModel, DocumentRecordModel


def _to_domain(
    model: DocumentGeneralEntryModel,
    record: DocumentRecordModel | None = None,
    asset: DocumentAssetModel | None = None,
    category: DocumentCategoryModel | None = None,
) -> DocumentGeneralEntry:
    business_status: str | None = None
    if record is not None and asset is not None:
        if asset.deleted_at is not None:
            business_status = "deleted"
        elif asset.status in {"pending_upload", "pending_scan", "scanning"}:
            business_status = "processing"
        elif asset.status in {"quarantined", "rejected"}:
            business_status = asset.status
        elif asset.status == "active":
            business_status = "current" if record.is_current else "replaced"
        else:
            business_status = asset.status
    return DocumentGeneralEntry(
        id=model.id,
        company_id=model.company_id,
        parent_id=model.parent_id,
        kind=model.kind,  # type: ignore[arg-type]
        document_id=model.document_id,
        name=model.name,
        normalized_name=model.normalized_name,
        created_by=model.created_by,
        updated_by=model.updated_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
        deletion_batch_id=model.deletion_batch_id,
        document_title=record.title if record is not None else None,
        original_filename=asset.original_filename if asset is not None else None,
        extension=asset.extension if asset is not None else None,
        content_type=(
            asset.detected_content_type or asset.declared_content_type
            if asset is not None
            else None
        ),
        size_bytes=asset.size_bytes if asset is not None else None,
        technical_status=asset.status if asset is not None else None,
        category_id=record.category_id if record is not None else None,
        category_name=category.name if category is not None else None,
        business_status=business_status,
        version_number=record.version_number if record is not None else None,
        is_current=record.is_current if record is not None else None,
    )


def _copy(entry: DocumentGeneralEntry, model: DocumentGeneralEntryModel) -> None:
    for field in (
        "company_id",
        "parent_id",
        "kind",
        "document_id",
        "name",
        "normalized_name",
        "created_by",
        "updated_by",
        "deleted_at",
        "deletion_batch_id",
    ):
        setattr(model, field, getattr(entry, field))


class SqlAlchemyDocumentGeneralRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _select(*, include_deleted: bool = False) -> Any:
        statement = select(DocumentGeneralEntryModel)
        if include_deleted:
            statement = statement.execution_options(include_deleted=True)
        else:
            statement = statement.where(DocumentGeneralEntryModel.deleted_at.is_(None))
        return statement

    async def add(self, entry: DocumentGeneralEntry) -> DocumentGeneralEntry:
        model = DocumentGeneralEntryModel(id=entry.id)
        _copy(entry, model)
        self._session.add(model)
        await self._session.flush()
        return _to_domain(model)

    async def get(
        self, company_id: uuid.UUID, entry_id: uuid.UUID, *, include_deleted: bool = False
    ) -> DocumentGeneralEntry | None:
        row = await self._session.scalar(
            self._select(include_deleted=include_deleted).where(
                DocumentGeneralEntryModel.company_id == company_id,
                DocumentGeneralEntryModel.id == entry_id,
            )
        )
        return _to_domain(row) if row is not None else None

    async def get_by_document(
        self, company_id: uuid.UUID, document_id: uuid.UUID, *, include_deleted: bool = False
    ) -> DocumentGeneralEntry | None:
        row = await self._session.scalar(
            self._select(include_deleted=include_deleted)
            .where(
                DocumentGeneralEntryModel.company_id == company_id,
                DocumentGeneralEntryModel.document_id == document_id,
            )
            .order_by(DocumentGeneralEntryModel.created_at.desc())
            .limit(1)
        )
        return _to_domain(row) if row is not None else None

    async def save(self, entry: DocumentGeneralEntry) -> DocumentGeneralEntry:
        model = await self._session.get(
            DocumentGeneralEntryModel,
            entry.id,
            execution_options={"include_deleted": True},
        )
        if model is None or model.company_id != entry.company_id:
            raise LookupError("Document general entry not found")
        _copy(entry, model)
        await self._session.flush()
        return _to_domain(model)

    async def sibling_exists(
        self,
        company_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        normalized_name: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        conditions = [
            DocumentGeneralEntryModel.company_id == company_id,
            DocumentGeneralEntryModel.parent_id.is_(None)
            if parent_id is None
            else DocumentGeneralEntryModel.parent_id == parent_id,
            DocumentGeneralEntryModel.normalized_name == normalized_name,
            DocumentGeneralEntryModel.deleted_at.is_(None),
        ]
        if exclude_id is not None:
            conditions.append(DocumentGeneralEntryModel.id != exclude_id)
        row = await self._session.scalar(
            select(DocumentGeneralEntryModel.id).where(*conditions).limit(1)
        )
        return row is not None

    async def list_contents(
        self,
        company_id: uuid.UUID,
        *,
        parent_id: uuid.UUID | None,
        search: str | None = None,
        category_id: uuid.UUID | None = None,
        status: str | None = None,
        sort: str = "name",
        descending: bool = False,
        page: int = 1,
        size: int = 50,
    ) -> tuple[Sequence[DocumentGeneralEntry], int]:
        parent_condition = (
            DocumentGeneralEntryModel.parent_id.is_(None)
            if parent_id is None
            else DocumentGeneralEntryModel.parent_id == parent_id
        )
        conditions: list[Any] = [
            DocumentGeneralEntryModel.company_id == company_id,
            parent_condition,
        ]
        if search:
            needle = " ".join(search.split()).casefold()
            conditions.append(DocumentGeneralEntryModel.normalized_name.ilike(f"%{needle}%"))
        if category_id is not None:
            conditions.extend(
                [
                    DocumentGeneralEntryModel.kind == "file",
                    DocumentRecordModel.category_id == category_id,
                ]
            )
        if status is not None:
            conditions.append(DocumentGeneralEntryModel.kind == "file")
            today = func.current_date()
            status_filters: dict[str, Any] = {
                "processing": DocumentAssetModel.status.in_(
                    ("pending_upload", "pending_scan", "scanning")
                ),
                "active": and_(
                    DocumentAssetModel.status == "active", DocumentRecordModel.is_current.is_(True)
                ),
                "current": and_(
                    DocumentAssetModel.status == "active", DocumentRecordModel.is_current.is_(True)
                ),
                "replaced": and_(
                    DocumentAssetModel.status == "active", DocumentRecordModel.is_current.is_(False)
                ),
                "quarantined": DocumentAssetModel.status == "quarantined",
                "rejected": DocumentAssetModel.status == "rejected",
                "deleted": DocumentAssetModel.deleted_at.is_not(None),
                "expired": and_(
                    DocumentAssetModel.status == "active",
                    DocumentRecordModel.is_current.is_(True),
                    DocumentRecordModel.expires_on < today,
                ),
                "expiring": and_(
                    DocumentAssetModel.status == "active",
                    DocumentRecordModel.is_current.is_(True),
                    DocumentRecordModel.expires_on >= today,
                    DocumentRecordModel.expires_on <= today + 30,
                ),
            }
            if status not in status_filters:
                return [], 0
            conditions.append(status_filters[status])
        conditions.append(DocumentGeneralEntryModel.deleted_at.is_(None))
        statement = (
            select(
                DocumentGeneralEntryModel,
                DocumentRecordModel,
                DocumentAssetModel,
                DocumentCategoryModel,
            )
            .outerjoin(
                DocumentRecordModel,
                and_(
                    DocumentRecordModel.id == DocumentGeneralEntryModel.document_id,
                    DocumentRecordModel.module == "general",
                ),
            )
            .outerjoin(DocumentAssetModel, DocumentAssetModel.id == DocumentRecordModel.id)
            .outerjoin(
                DocumentCategoryModel, DocumentCategoryModel.id == DocumentRecordModel.category_id
            )
            .where(*conditions)
        )
        count_statement = (
            select(func.count(DocumentGeneralEntryModel.id))
            .select_from(DocumentGeneralEntryModel)
            .outerjoin(
                DocumentRecordModel,
                and_(
                    DocumentRecordModel.id == DocumentGeneralEntryModel.document_id,
                    DocumentRecordModel.module == "general",
                ),
            )
            .outerjoin(DocumentAssetModel, DocumentAssetModel.id == DocumentRecordModel.id)
            .where(*conditions)
        )
        if status == "deleted":
            statement = statement.execution_options(include_deleted=True)
            count_statement = count_statement.execution_options(include_deleted=True)
        total = int(await self._session.scalar(count_statement) or 0)
        order_column = {
            "created_at": DocumentGeneralEntryModel.created_at,
            "updated_at": DocumentGeneralEntryModel.updated_at,
            "size": DocumentAssetModel.size_bytes,
        }.get(sort, DocumentGeneralEntryModel.normalized_name)
        statement = statement.order_by(order_column.desc() if descending else order_column.asc())
        statement = statement.offset((page - 1) * size).limit(size)
        rows = (await self._session.execute(statement)).all()
        return [
            _to_domain(entry, record, asset, category) for entry, record, asset, category in rows
        ], total

    async def list_tree(
        self, company_id: uuid.UUID, *, include_deleted: bool = False
    ) -> Sequence[DocumentGeneralEntry]:
        rows = (
            await self._session.scalars(
                self._select(include_deleted=include_deleted)
                .where(DocumentGeneralEntryModel.company_id == company_id)
                .order_by(DocumentGeneralEntryModel.normalized_name)
            )
        ).all()
        return [_to_domain(row) for row in rows]

    async def descendants(
        self, company_id: uuid.UUID, entry_id: uuid.UUID, *, include_deleted: bool = False
    ) -> Sequence[DocumentGeneralEntry]:
        root = await self.get(company_id, entry_id, include_deleted=include_deleted)
        if root is None:
            return []
        result = [root]
        frontier = [root.id]
        while frontier:
            statement = self._select(include_deleted=include_deleted).where(
                DocumentGeneralEntryModel.company_id == company_id,
                DocumentGeneralEntryModel.parent_id.in_(frontier),
            )
            rows = (await self._session.scalars(statement)).all()
            result.extend(_to_domain(row) for row in rows)
            frontier = [row.id for row in rows]
        return result

    async def list_deletion_batches(
        self,
        company_id: uuid.UUID,
        *,
        search: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[Sequence[GeneralDeletionBatch], int]:
        batches = (
            await self._session.scalars(
                select(DocumentGeneralDeletionBatchModel)
                .where(DocumentGeneralDeletionBatchModel.company_id == company_id)
                .order_by(DocumentGeneralDeletionBatchModel.created_at.desc())
            )
        ).all()
        if not batches:
            return [], 0

        batch_ids = [batch.id for batch in batches]
        entries = (
            await self._session.scalars(
                select(DocumentGeneralEntryModel)
                .execution_options(include_deleted=True)
                .where(
                    DocumentGeneralEntryModel.company_id == company_id,
                    DocumentGeneralEntryModel.deletion_batch_id.in_(batch_ids),
                    DocumentGeneralEntryModel.deleted_at.is_not(None),
                )
            )
        ).all()
        grouped: dict[uuid.UUID, list[DocumentGeneralEntryModel]] = {}
        for entry in entries:
            if entry.deletion_batch_id is not None:
                grouped.setdefault(entry.deletion_batch_id, []).append(entry)

        result: list[GeneralDeletionBatch] = []
        for batch in batches:
            batch_entries = grouped.get(batch.id, [])
            if not batch_entries:
                continue
            ids = {entry.id for entry in batch_entries}
            roots = [
                entry
                for entry in batch_entries
                if entry.kind == "folder" and entry.parent_id not in ids
            ]
            root = (
                roots[0]
                if roots
                else next((entry for entry in batch_entries if entry.kind == "folder"), None)
            )
            if root is None:
                continue
            result.append(
                GeneralDeletionBatch(
                    id=batch.id,
                    company_id=batch.company_id,
                    root_folder_id=root.id,
                    label=root.name,
                    entry_count=len(batch_entries),
                    created_at=batch.created_at,
                    actor_id=batch.actor_id,
                )
            )

        if search:
            needle = " ".join(search.split()).casefold()
            result = [batch for batch in result if needle in batch.label.casefold()]
        total = len(result)
        start = (page - 1) * size
        return result[start : start + size], total

    async def create_deletion_batch(self, company_id: uuid.UUID, actor_id: uuid.UUID) -> uuid.UUID:
        batch = DocumentGeneralDeletionBatchModel(company_id=company_id, actor_id=actor_id)
        self._session.add(batch)
        await self._session.flush()
        return batch.id

    async def soft_delete_batch(
        self,
        company_id: uuid.UUID,
        entry_ids: Sequence[uuid.UUID],
        batch_id: uuid.UUID,
        actor_id: uuid.UUID,
        deleted_at: datetime,
    ) -> None:
        await self._session.execute(
            update(DocumentGeneralEntryModel)
            .where(
                DocumentGeneralEntryModel.company_id == company_id,
                DocumentGeneralEntryModel.id.in_(entry_ids),
            )
            .values(
                deleted_at=deleted_at,
                deletion_batch_id=batch_id,
                updated_by=actor_id,
                updated_at=func.now(),
            )
        )
        await self._session.flush()

    async def restore_batch(
        self, company_id: uuid.UUID, batch_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        await self._session.execute(
            update(DocumentGeneralEntryModel)
            .where(
                DocumentGeneralEntryModel.company_id == company_id,
                DocumentGeneralEntryModel.deletion_batch_id == batch_id,
                DocumentGeneralEntryModel.deleted_at.is_not(None),
            )
            .values(
                deleted_at=None,
                deletion_batch_id=None,
                updated_by=actor_id,
                updated_at=func.now(),
            )
        )
        await self._session.flush()


__all__ = ["SqlAlchemyDocumentGeneralRepository"]
