"""Puerto de persistencia de los eventos de retorno (revisión 0138, bloque V4d2)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from app.domain.entities.fiscal_contingency import ContingencyResponsible
from app.domain.entities.sales_fiscal_notes import Nature
from app.domain.entities.sales_fiscal_returns import AnnulStatus, PriorReturnLine, ReturnStatus


@dataclass(frozen=True, slots=True)
class ReturnLineRecord:
    line_number: int
    invoice_line_number: int
    nature: Nature
    description: str
    quantity: Decimal
    amount: Decimal
    vat: Decimal


@dataclass(slots=True)
class FiscalReturn:
    id: uuid.UUID
    company_id: uuid.UUID
    document_id: uuid.UUID
    """La factura a la que se aplica."""
    reason: str
    status: ReturnStatus
    idempotency_key: str
    request_payload: dict[str, Any]
    total: Decimal
    created_by_id: uuid.UUID
    lines: tuple[ReturnLineRecord, ...] = ()
    attempts: int = 0
    generation_code: uuid.UUID | None = None
    seal: str | None = None
    """Sello de Hacienda o, en simulado, el marcador del evento."""
    dte_json: dict[str, Any] | None = None
    json_object_key: str | None = None
    pdf_object_key: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    issued_at: datetime | None = None
    annul_status: AnnulStatus | None = None
    annul_idempotency_key: str | None = None
    annul_attempts: int = 0
    annul_requester: ContingencyResponsible | None = None
    annul_responsible: ContingencyResponsible | None = None
    annul_generation_code: uuid.UUID | None = None
    annul_seal: str | None = None
    annul_error_code: str | None = None
    annul_error_message: str | None = None
    annul_requested_by_id: uuid.UUID | None = None
    annul_requested_at: datetime | None = None
    annulled_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SalesFiscalReturnRepository(Protocol):
    async def create(self, item: FiscalReturn) -> FiscalReturn: ...

    async def get(
        self, company_id: uuid.UUID, return_id: uuid.UUID, *, lock: bool = False
    ) -> FiscalReturn | None: ...

    async def for_document(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[FiscalReturn]: ...

    async def prior_lines(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[PriorReturnLine]:
        """Líneas de los retornos vigentes de la factura (para su saldo)."""
        ...

    async def vigent_count(self, company_id: uuid.UUID, document_id: uuid.UUID) -> int: ...

    async def save(self, item: FiscalReturn) -> FiscalReturn: ...
