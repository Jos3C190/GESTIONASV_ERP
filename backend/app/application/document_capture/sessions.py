"""The lifecycle every guided capture shares, whatever the document or its owner.

Photos stay assets without a document record until a capture is confirmed, so
nothing that reads documents can see them. What a capture checks and what confirming
it does belong to each document's own service.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.audit.audit_service import AuditService
from app.application.documents.service import DocumentService, InitiateDocumentInput, UploadTicket
from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.entities.document import DocumentAsset
from app.infrastructure.models.document_capture import OPEN_CAPTURE_STATUSES, DocumentCaptureModel

CAPTURE_MAX_BYTES = 15 * 1024 * 1024
_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


@dataclass(frozen=True, slots=True)
class CaptureConfig:
    kind: str
    owner_type: str
    #: Fixed on purpose: the original name would reach the audit log and may hold data.
    file_prefix: str
    code_prefix: str
    cancel_action: str
    resource_type: str


class CaptureSessions:
    def __init__(
        self,
        session: AsyncSession,
        documents: DocumentService,
        audit: AuditService,
        config: CaptureConfig,
    ) -> None:
        self._session = session
        self._documents = documents
        self._audit = audit
        self._config = config

    async def open(
        self, company_id: uuid.UUID, owner_id: uuid.UUID, actor_id: uuid.UUID
    ) -> DocumentCaptureModel:
        """Resume the owner's open capture, or start one."""
        existing = await self._session.scalar(
            select(DocumentCaptureModel).where(
                DocumentCaptureModel.company_id == company_id,
                DocumentCaptureModel.kind == self._config.kind,
                DocumentCaptureModel.owner_type == self._config.owner_type,
                DocumentCaptureModel.owner_id == owner_id,
                DocumentCaptureModel.status.in_(OPEN_CAPTURE_STATUSES),
            )
        )
        if existing is not None:
            return existing
        capture = DocumentCaptureModel(
            company_id=company_id,
            kind=self._config.kind,
            owner_type=self._config.owner_type,
            owner_id=owner_id,
            status="draft",
            expires_at=datetime.now(UTC)
            + timedelta(hours=settings.LICENSE_CAPTURE_RETENTION_HOURS),
            created_by=actor_id,
        )
        self._session.add(capture)
        await self._session.flush()
        return capture

    async def get(
        self,
        company_id: uuid.UUID,
        owner_id: uuid.UUID,
        capture_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> DocumentCaptureModel:
        statement = select(DocumentCaptureModel).where(
            DocumentCaptureModel.id == capture_id,
            DocumentCaptureModel.company_id == company_id,
            DocumentCaptureModel.kind == self._config.kind,
            DocumentCaptureModel.owner_type == self._config.owner_type,
            DocumentCaptureModel.owner_id == owner_id,
        )
        if lock:
            statement = statement.with_for_update()
        capture = await self._session.scalar(statement)
        if capture is None:
            raise NotFoundError(
                "Captura no encontrada.", code=f"{self._config.code_prefix}_not_found"
            )
        return capture

    def require_open(self, capture: DocumentCaptureModel) -> None:
        if capture.status not in OPEN_CAPTURE_STATUSES:
            raise ConflictError(
                "Esta captura ya terminó.", code=f"{self._config.code_prefix}_closed"
            )

    @staticmethod
    def side_id(capture: DocumentCaptureModel, side: str) -> uuid.UUID | None:
        return capture.front_document_id if side == "front" else capture.back_document_id

    async def initiate_side(
        self,
        capture: DocumentCaptureModel,
        side: str,
        *,
        content_type: str,
        size_bytes: int,
        checksum_sha256: str,
        actor_id: uuid.UUID,
    ) -> UploadTicket:
        self.require_open(capture)
        if size_bytes > CAPTURE_MAX_BYTES:
            raise ValidationError(
                "La foto supera el tamaño permitido.",
                code=f"{self._config.code_prefix}_too_large",
            )
        ticket = await self._documents.initiate(
            InitiateDocumentInput(
                company_id=capture.company_id,
                actor_id=actor_id,
                filename=f"{self._config.file_prefix}-{side}.{_EXTENSIONS[content_type]}",
                content_type=content_type,
                size_bytes=size_bytes,
                checksum_sha256=checksum_sha256,
            )
        )
        previous = self.side_id(capture, side)
        if side == "front":
            capture.front_document_id = ticket.document.id
        else:
            capture.back_document_id = ticket.document.id
        if capture.extracted and side in capture.extracted:
            capture.extracted = {k: v for k, v in capture.extracted.items() if k != side}
        await self._session.flush()
        if previous is not None:
            await self._documents.discard(capture.company_id, previous)
        return ticket

    async def complete_side(
        self, capture: DocumentCaptureModel, side: str, actor_id: uuid.UUID
    ) -> bool:
        """Scan the uploaded photo. Returns whether the capture now awaits extraction."""
        self.require_open(capture)
        document_id = self.side_id(capture, side)
        if document_id is None:
            raise ConflictError(
                "Primero carga la foto.", code=f"{self._config.code_prefix}_side_missing"
            )
        await self._documents.complete(capture.company_id, document_id, actor_id)
        if not settings.VLM_ENABLED:
            return False
        capture.status = "pending"
        capture.attempts = 0
        capture.failure_code = None
        capture.started_at = None
        await self._session.flush()
        return True

    async def asset(self, capture: DocumentCaptureModel, side: str) -> DocumentAsset | None:
        document_id = self.side_id(capture, side)
        if document_id is None:
            return None
        return await self._documents.get(capture.company_id, document_id)

    async def cancel(self, capture: DocumentCaptureModel, actor_id: uuid.UUID) -> None:
        self.require_open(capture)
        for document_id in (capture.front_document_id, capture.back_document_id):
            if document_id is not None:
                await self._documents.discard(capture.company_id, document_id)
        capture.status = "cancelled"
        capture.extracted = None
        capture.front_document_id = None
        capture.back_document_id = None
        await self._session.flush()
        await self._audit.record(
            action=self._config.cancel_action,
            user_id=actor_id,
            company_id=capture.company_id,
            resource_type=self._config.resource_type,
            resource_id=str(capture.owner_id),
            after_state={"capture_id": str(capture.id)},
            required=True,
        )
