"""Application service for the record lifecycle contract."""

from __future__ import annotations

import uuid

from app.core.exceptions import ValidationError
from app.domain.ports.lifecycle_repository import DeletedRecord, LifecycleRepository

MIN_DELETION_REASON_LENGTH = 3


class LifecycleService:
    def __init__(self, repository: LifecycleRepository) -> None:
        self._repository = repository

    async def list_deleted(
        self,
        company_id: uuid.UUID,
        *,
        page: int,
        size: int,
        resource: str | None = None,
        search: str | None = None,
        include_global: bool = False,
        include_all_companies: bool = False,
    ) -> tuple[list[DeletedRecord], int]:
        return await self._repository.list_deleted(
            company_id,
            page=page,
            size=size,
            resource=resource,
            search=search,
            include_global=include_global,
            include_all_companies=include_all_companies,
        )

    async def delete(
        self,
        resource: str,
        record_id: str,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str,
        allow_global: bool = False,
    ) -> DeletedRecord:
        normalized_reason = reason.strip()
        if len(normalized_reason) < MIN_DELETION_REASON_LENGTH:
            raise ValidationError(
                "Indique un motivo de eliminación de al menos 3 caracteres.",
                code="deletion_reason_required",
            )
        return await self._repository.soft_delete(
            resource,
            record_id,
            company_id=company_id,
            actor_id=actor_id,
            reason=normalized_reason,
            allow_global=allow_global,
        )

    async def restore(
        self,
        resource: str,
        record_id: str,
        *,
        company_id: uuid.UUID,
        actor_id: uuid.UUID,
        allow_global: bool = False,
    ) -> DeletedRecord:
        return await self._repository.restore(
            resource,
            record_id,
            company_id=company_id,
            actor_id=actor_id,
            allow_global=allow_global,
        )
