"""Invalidación y reemplazo de un documento fiscal (bloque V4b del área de Ventas).

Un DTE sellado no se borra: se invalida con un evento firmado. El ERP ofrece dos caminos:

- **Rescindir la operación** (tipo 2 de CAT-024): la venta no se hizo. Se invalida sin reemplazo y,
  si se pide desde el pedido, el pedido se cancela al aceptarse.
- **Corregir los datos** (tipo 1): primero se emite el documento correcto con los datos actuales
  del cliente y del pedido; cuando queda sellado, se invalida el original vinculándolo.

Fuente: Manual Funcional v2 (invalidación) y el constructor del evento del servicio DTE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum, StrEnum
from uuid import UUID

from app.core.exceptions import BusinessRuleError
from app.domain.entities.fiscal_contingency import ContingencyResponsible, validate_responsible
from app.domain.entities.sales_fiscal_document import INVOICEABLE_DOCUMENTS, FiscalDocumentStatus

MIN_REASON = 5
MAX_REASON = 200

#: Lo que se puede invalidar o corregir: tiene sello (o es simulado).
SEALED_STATUSES = (FiscalDocumentStatus.ISSUED, FiscalDocumentStatus.SIMULATED)


class InvalidationKind(IntEnum):
    CORRECTION = 1
    """Error en la información: con documento de reemplazo."""
    RESCISSION = 2
    """Rescindir la operación: sin reemplazo."""


class InvalidationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(slots=True)
class FiscalInvalidation:
    id: UUID
    company_id: UUID
    document_id: UUID
    kind: InvalidationKind
    reason: str | None
    requester: ContingencyResponsible
    requested_by_id: UUID
    idempotency_key: str
    status: InvalidationStatus = InvalidationStatus.PENDING
    responsible: ContingencyResponsible | None = None
    replacement_document_id: UUID | None = None
    cancel_order: bool = False
    attempts: int = 0
    event_generation_code: UUID | None = None
    event_seal: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    resolved_at: datetime | None = None


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


def require_invalidatable(
    status: FiscalDocumentStatus, *, superseded: bool, pending_invalidation: bool
) -> None:
    if status not in SEALED_STATUSES:
        raise _rule(
            "Solo se invalida un documento emitido o simulado.",
            "sales_invoice_not_invalidatable",
        )
    if pending_invalidation:
        raise _rule(
            "Este documento ya tiene una invalidación en curso.",
            "sales_invoice_invalidation_in_progress",
        )
    if superseded:
        raise _rule(
            "Este documento se está corrigiendo con un reemplazo; se invalidará solo.",
            "sales_invoice_replacement_in_progress",
        )


def require_correctable(
    status: FiscalDocumentStatus,
    document_type: str,
    *,
    superseded: bool,
    pending_invalidation: bool,
) -> None:
    require_invalidatable(status, superseded=superseded, pending_invalidation=pending_invalidation)
    if document_type not in INVOICEABLE_DOCUMENTS:
        raise _rule(
            "Solo se corrige una factura o un comprobante de crédito fiscal.",
            "sales_invoice_not_correctable",
        )


def validate_reason(reason: str | None) -> str:
    text = (reason or "").strip()
    if not MIN_REASON <= len(text) <= MAX_REASON:
        raise _rule(
            f"Escribe el motivo (de {MIN_REASON} a {MAX_REASON} caracteres).",
            "sales_invoice_invalidation_reason_required",
        )
    return text


def validate_requester(
    name: str, document_type: str, document_number: str
) -> ContingencyResponsible:
    """Quien solicita la invalidación (el cliente o alguien de la empresa), con su documento."""

    return validate_responsible(
        name, document_type, document_number, code="sales_invoice_requester_invalid"
    )
