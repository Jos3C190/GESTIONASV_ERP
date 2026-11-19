"""Puerto de persistencia del documento fiscal del pedido (bloque V3b)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from app.domain.entities.sales_fiscal_document import FiscalDocumentStatus


@dataclass(slots=True)
class FiscalDocument:
    id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID
    sale_id: uuid.UUID
    establishment_id: uuid.UUID
    point_of_sale_id: uuid.UUID
    document_type: str
    mode: str
    status: FiscalDocumentStatus
    idempotency_key: str
    total: Decimal
    issuer_snapshot: dict[str, Any]
    request_payload: dict[str, Any]
    created_by_id: uuid.UUID
    attempts: int = 0
    generation_code: uuid.UUID | None = None
    control_number: str | None = None
    dte_json: dict[str, Any] | None = None
    seal: str | None = None
    service_response: dict[str, Any] | None = None
    json_object_key: str | None = None
    pdf_object_key: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    issued_at: datetime | None = None
    contingency_type: int | None = None
    contingency_reason: str | None = None
    contingency_at: datetime | None = None
    replaces_document_id: uuid.UUID | None = None
    superseded_by_id: uuid.UUID | None = None
    renta_operation_type: int | None = None
    """Clasificación de renta del documento para los anexos del F-07 (V4b2)."""
    renta_income_type: int | None = None
    related_document_id: uuid.UUID | None = None
    """En una nota (05 o 06), el crédito fiscal que ajusta (V4c)."""
    note_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    sale_code: str | None = None
    customer_name: str | None = None
    point_of_sale_code: str | None = None
    establishment_code: str | None = None
    customer_email: str | None = None


@dataclass(frozen=True, slots=True)
class FiscalNoteLine:
    """Lo que ajusta una línea de una nota de crédito o de débito (V4c)."""

    line_number: int
    ccf_line_number: int | None
    kind: str
    nature: str
    description: str
    quantity: Decimal | None
    amount: Decimal


@dataclass(frozen=True, slots=True)
class FiscalDocumentFilters:
    branch_ids: tuple[uuid.UUID, ...] | None
    """``None``: todas las sucursales; tupla vacía: ninguna."""
    branch_id: uuid.UUID | None = None
    sale_id: uuid.UUID | None = None
    status: str | None = None
    document_type: str | None = None
    search: str | None = None


class SalesFiscalRepository(Protocol):
    async def create(self, document: FiscalDocument) -> FiscalDocument: ...

    async def get(
        self, company_id: uuid.UUID, document_id: uuid.UUID, *, lock: bool = False
    ) -> FiscalDocument | None: ...

    async def active_for_order(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> FiscalDocument | None: ...

    async def latest_for_order(
        self, company_id: uuid.UUID, order_id: uuid.UUID
    ) -> FiscalDocument | None: ...

    async def list_documents(
        self, company_id: uuid.UUID, filters: FiscalDocumentFilters, *, page: int, size: int
    ) -> tuple[list[FiscalDocument], int]: ...

    async def save(self, document: FiscalDocument) -> FiscalDocument: ...

    async def create_note(
        self, document: FiscalDocument, lines: Sequence[FiscalNoteLine]
    ) -> FiscalDocument: ...

    async def notes_for(self, company_id: uuid.UUID, ccf_id: uuid.UUID) -> list[FiscalDocument]:
        """Las notas de un crédito fiscal, de la más reciente a la más antigua."""
        ...

    async def note_lines(
        self, company_id: uuid.UUID, note_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[FiscalNoteLine]]: ...

    async def lock_contingency(self, document_id: uuid.UUID) -> FiscalDocument | None:
        """Toma un documento en contingencia para seguirlo (``SKIP LOCKED``)."""
        ...

    async def claim(self, document_id: uuid.UUID, max_attempts: int) -> FiscalDocument | None:
        """Toma un documento pendiente para emitirlo (``SKIP LOCKED``) y cuenta el intento."""
        ...

    async def pending_ids(self, updated_before: datetime, limit: int) -> list[uuid.UUID]: ...

    async def unit_codes(self, company_id: uuid.UUID, unit_ids: set[int]) -> dict[int, str]:
        """CAT-014 de cada unidad en la empresa (solo las que lo tienen)."""
        ...

    async def catalog_version(self, catalog_code: str) -> str | None: ...


@dataclass(slots=True)
class FiscalDocumentEmail:
    """Un envío por correo del documento fiscal (bloque V3c)."""

    id: uuid.UUID
    company_id: uuid.UUID
    document_id: uuid.UUID
    recipients: tuple[str, ...]
    origin: str
    status: str
    attempts: int = 0
    error_code: str | None = None
    error_message: str | None = None
    message_id: str | None = None
    requested_by_id: uuid.UUID | None = None
    requested_by_name: str | None = None
    invalidation_id: uuid.UUID | None = None
    """Aviso de una invalidación aceptada (V4b), en lugar del documento."""
    sent_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SalesFiscalEmailRepository(Protocol):
    async def create(self, email: FiscalDocumentEmail) -> FiscalDocumentEmail: ...

    async def auto_exists(self, company_id: uuid.UUID, document_id: uuid.UUID) -> bool: ...

    async def list_for_document(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[FiscalDocumentEmail]: ...

    async def claim(self, email_id: uuid.UUID) -> FiscalDocumentEmail | None:
        """Toma un envío pendiente (``SKIP LOCKED``) y cuenta el intento."""
        ...

    async def save(self, email: FiscalDocumentEmail) -> FiscalDocumentEmail: ...

    async def pending_ids(self, updated_before: datetime, limit: int) -> list[uuid.UUID]: ...
