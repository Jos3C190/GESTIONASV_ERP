from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.document_derivative import DocumentDerivative
from app.infrastructure.models.document_derivative import DocumentDerivativeModel


def _to_domain(model: DocumentDerivativeModel) -> DocumentDerivative:
    return DocumentDerivative(
        id=model.id,
        company_id=model.company_id,
        document_id=model.document_id,
        kind=model.kind,
        status=model.status,
        bucket=model.bucket,
        object_key=model.object_key,
        content_type=model.content_type,
        size_bytes=model.size_bytes,
        checksum_sha256=model.checksum_sha256,
        etag=model.etag,
        attempts=model.attempts,
        failure_code=model.failure_code,
        started_at=model.started_at,
        completed_at=model.completed_at,
        object_deleted_at=model.object_deleted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _copy_to_model(derivative: DocumentDerivative, model: DocumentDerivativeModel) -> None:
    for name in (
        "status",
        "content_type",
        "size_bytes",
        "checksum_sha256",
        "etag",
        "attempts",
        "failure_code",
        "started_at",
        "completed_at",
        "object_deleted_at",
    ):
        setattr(model, name, getattr(derivative, name))


class SqlAlchemyDocumentDerivativeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_ocr(
        self,
        *,
        derivative_id: uuid.UUID,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        bucket: str,
        object_key: str,
    ) -> DocumentDerivative:
        statement = (
            insert(DocumentDerivativeModel)
            .values(
                id=derivative_id,
                company_id=company_id,
                document_id=document_id,
                kind="ocr_pdf",
                status="pending",
                bucket=bucket,
                object_key=object_key,
                content_type="application/pdf",
            )
            .on_conflict_do_nothing(index_elements=["document_id", "kind"])
            .returning(DocumentDerivativeModel)
        )
        model = (await self._session.execute(statement)).scalar_one_or_none()
        if model is None:
            existing = await self.get_ocr(document_id)
            if existing is None:
                raise LookupError("OCR derivative was not created")
            return existing
        return _to_domain(model)

    async def get(self, derivative_id: uuid.UUID) -> DocumentDerivative | None:
        model = await self._session.get(DocumentDerivativeModel, derivative_id)
        return _to_domain(model) if model is not None else None

    async def get_ocr(self, document_id: uuid.UUID) -> DocumentDerivative | None:
        model = (
            await self._session.execute(
                select(DocumentDerivativeModel).where(
                    DocumentDerivativeModel.document_id == document_id,
                    DocumentDerivativeModel.kind == "ocr_pdf",
                )
            )
        ).scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    async def list_ocr(self, document_ids: Sequence[uuid.UUID]) -> Sequence[DocumentDerivative]:
        if not document_ids:
            return []
        models = (
            (
                await self._session.execute(
                    select(DocumentDerivativeModel).where(
                        DocumentDerivativeModel.document_id.in_(document_ids),
                        DocumentDerivativeModel.kind == "ocr_pdf",
                    )
                )
            )
            .scalars()
            .all()
        )
        return [_to_domain(model) for model in models]

    async def list_pending_ids(self, limit: int) -> Sequence[uuid.UUID]:
        return list(
            (
                await self._session.scalars(
                    select(DocumentDerivativeModel.id)
                    .where(DocumentDerivativeModel.status == "pending")
                    .order_by(DocumentDerivativeModel.created_at, DocumentDerivativeModel.id)
                    .limit(limit)
                )
            ).all()
        )

    async def pending_summary(self) -> tuple[int, datetime | None]:
        count, oldest = (
            await self._session.execute(
                select(
                    func.count(DocumentDerivativeModel.id),
                    func.min(DocumentDerivativeModel.created_at),
                ).where(DocumentDerivativeModel.status == "pending")
            )
        ).one()
        return int(count), oldest

    async def claim(self, derivative_id: uuid.UUID, now: datetime) -> DocumentDerivative | None:
        model = (
            await self._session.execute(
                update(DocumentDerivativeModel)
                .where(
                    DocumentDerivativeModel.id == derivative_id,
                    DocumentDerivativeModel.status == "pending",
                )
                .values(
                    status="processing",
                    started_at=now,
                    failure_code=None,
                    attempts=DocumentDerivativeModel.attempts + 1,
                )
                .returning(DocumentDerivativeModel)
            )
        ).scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    async def save(self, derivative: DocumentDerivative) -> DocumentDerivative:
        model = await self._session.get(DocumentDerivativeModel, derivative.id)
        if model is None:
            raise LookupError("Document derivative not found")
        _copy_to_model(derivative, model)
        await self._session.flush()
        return _to_domain(model)

    async def reset_for_retry(self, derivative_id: uuid.UUID) -> DocumentDerivative | None:
        model = (
            await self._session.execute(
                update(DocumentDerivativeModel)
                .where(
                    DocumentDerivativeModel.id == derivative_id,
                    DocumentDerivativeModel.status == "failed",
                )
                .values(
                    status="pending",
                    failure_code=None,
                    attempts=0,
                    started_at=None,
                    completed_at=None,
                )
                .returning(DocumentDerivativeModel)
            )
        ).scalar_one_or_none()
        return _to_domain(model) if model is not None else None

    async def reset_stale(self, before: datetime) -> int:
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(DocumentDerivativeModel)
                .where(
                    DocumentDerivativeModel.status == "processing",
                    DocumentDerivativeModel.started_at < before,
                )
                .values(
                    status="pending", failure_code="ocr_processing_interrupted", started_at=None
                )
            ),
        )
        return int(result.rowcount or 0)
