from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.document import DocumentAsset
from app.infrastructure.models.document import DocumentAssetModel


def _to_domain(model: DocumentAssetModel) -> DocumentAsset:
    return DocumentAsset(
        id=model.id,
        company_id=model.company_id,
        original_filename=model.original_filename,
        extension=model.extension,
        declared_content_type=model.declared_content_type,
        detected_content_type=model.detected_content_type,
        size_bytes=model.size_bytes,
        checksum_sha256=model.checksum_sha256,
        bucket=model.bucket,
        object_key=model.object_key,
        etag=model.etag,
        status=model.status,
        failure_code=model.failure_code,
        malware_name=model.malware_name,
        upload_expires_at=model.upload_expires_at,
        scan_started_at=model.scan_started_at,
        scanned_at=model.scanned_at,
        object_deleted_at=model.object_deleted_at,
        uploaded_by=model.uploaded_by,
        deleted_at=model.deleted_at,
        deleted_by=model.deleted_by,
        deletion_reason=model.deletion_reason,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _copy_to_model(document: DocumentAsset, model: DocumentAssetModel) -> None:
    for name in (
        "original_filename",
        "extension",
        "declared_content_type",
        "detected_content_type",
        "size_bytes",
        "checksum_sha256",
        "bucket",
        "object_key",
        "etag",
        "status",
        "failure_code",
        "malware_name",
        "upload_expires_at",
        "scan_started_at",
        "scanned_at",
        "object_deleted_at",
        "uploaded_by",
        "deleted_at",
        "deleted_by",
        "deletion_reason",
    ):
        setattr(model, name, getattr(document, name))


class SqlAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: DocumentAsset) -> DocumentAsset:
        model = DocumentAssetModel(id=document.id, company_id=document.company_id)
        _copy_to_model(document, model)
        self._session.add(model)
        await self._session.flush()
        return _to_domain(model)

    async def get(
        self, document_id: uuid.UUID, *, include_deleted: bool = False
    ) -> DocumentAsset | None:
        statement = select(DocumentAssetModel).where(DocumentAssetModel.id == document_id)
        if include_deleted:
            statement = statement.execution_options(include_deleted=True)
        model = (await self._session.execute(statement)).scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    async def save(self, document: DocumentAsset) -> DocumentAsset:
        model = await self._session.get(DocumentAssetModel, document.id)
        if model is None:
            raise LookupError("Document not found")
        _copy_to_model(document, model)
        await self._session.flush()
        return _to_domain(model)

    async def list(
        self,
        company_id: uuid.UUID,
        *,
        page: int,
        size: int,
        search: str | None,
        status: str | None,
    ) -> tuple[Sequence[DocumentAsset], int]:
        conditions = [DocumentAssetModel.company_id == company_id]
        if status:
            conditions.append(DocumentAssetModel.status == status)
        if search:
            token = f"%{search.strip()}%"
            conditions.append(DocumentAssetModel.original_filename.ilike(token))
        total = int(
            await self._session.scalar(select(func.count(DocumentAssetModel.id)).where(*conditions))
            or 0
        )
        rows = (
            (
                await self._session.execute(
                    select(DocumentAssetModel)
                    .where(*conditions)
                    .order_by(DocumentAssetModel.created_at.desc(), DocumentAssetModel.id.desc())
                    .offset((page - 1) * size)
                    .limit(size)
                )
            )
            .scalars()
            .all()
        )
        return [_to_domain(row) for row in rows], total

    async def count_pending(self, user_id: uuid.UUID) -> int:
        # Serialize the count+insert sequence per user. The transaction-level
        # lock is released when the request commits, preventing concurrent
        # upload initiations from exceeding the configured pending limit.
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"documents.pending:{user_id}"},
        )
        return int(
            await self._session.scalar(
                select(func.count(DocumentAssetModel.id)).where(
                    DocumentAssetModel.uploaded_by == user_id,
                    DocumentAssetModel.status.in_(("pending_upload", "pending_scan", "scanning")),
                )
            )
            or 0
        )

    async def claim_for_scan(self, document_id: uuid.UUID, now: datetime) -> DocumentAsset | None:
        statement = (
            update(DocumentAssetModel)
            .where(
                DocumentAssetModel.id == document_id,
                DocumentAssetModel.status.in_(("pending_upload", "pending_scan")),
            )
            .values(status="scanning", scan_started_at=now, failure_code=None)
            .returning(DocumentAssetModel)
        )
        model = (await self._session.execute(statement)).scalar_one_or_none()
        if model is not None:
            # Persist the claim before the network download/scan. Competing
            # requests can no longer acquire the same document.
            await self._session.commit()
        return _to_domain(model) if model is not None else None
