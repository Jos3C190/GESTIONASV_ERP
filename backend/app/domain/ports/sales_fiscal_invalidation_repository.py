"""Puerto de las invalidaciones de documentos fiscales (bloque V4b)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from app.domain.entities.sales_fiscal_invalidation import FiscalInvalidation


class SalesFiscalInvalidationRepository(Protocol):
    async def create(self, invalidation: FiscalInvalidation) -> FiscalInvalidation: ...

    async def get(
        self, company_id: uuid.UUID, invalidation_id: uuid.UUID
    ) -> FiscalInvalidation | None: ...

    async def by_key(
        self, company_id: uuid.UUID, idempotency_key: str
    ) -> FiscalInvalidation | None: ...

    async def pending_for_document(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> FiscalInvalidation | None: ...

    async def for_document(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[FiscalInvalidation]:
        """Todas las solicitudes del documento, de la más reciente a la más antigua."""
        ...

    async def save(self, invalidation: FiscalInvalidation) -> FiscalInvalidation: ...

    async def claim(self, invalidation_id: uuid.UUID) -> FiscalInvalidation | None:
        """Toma una invalidación pendiente (``SKIP LOCKED``) y cuenta el intento."""
        ...

    async def pending_ids(self, updated_before: datetime, limit: int) -> list[uuid.UUID]: ...
