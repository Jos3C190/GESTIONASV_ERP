"""Pure transfer lifecycle rules shared by API and persistence adapters."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum


class TransferStatus(StrEnum):
    PREPARATION = "preparation"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    INCIDENT = "incident"
    CANCELLED = "cancelled"


class TransferDomainError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def require_preparation(status: str) -> None:
    if status != TransferStatus.PREPARATION:
        raise TransferDomainError(
            "Solo se puede editar o cancelar un traslado en preparación.",
            code="transfer_not_in_preparation",
        )


def require_dispatchable(status: str, line_count: int) -> None:
    if status != TransferStatus.PREPARATION:
        raise TransferDomainError(
            "El traslado ya no está en preparación.", code="transfer_not_dispatchable"
        )
    if line_count < 1:
        raise TransferDomainError(
            "Agregue al menos una unidad logística al traslado.",
            code="transfer_lines_required",
            status_code=422,
        )


def require_receivable(status: str) -> None:
    if status != TransferStatus.IN_TRANSIT:
        raise TransferDomainError(
            "Solo se reciben traslados que están en tránsito.", code="transfer_not_receivable"
        )


def validate_positive_quantity(quantity: Decimal) -> None:
    if not quantity.is_finite() or quantity <= 0:
        raise TransferDomainError(
            "La cantidad debe ser un decimal positivo.",
            code="transfer_quantity_invalid",
            status_code=422,
        )


def validate_receipt_quantity(*, requested: Decimal, remaining: Decimal) -> None:
    validate_positive_quantity(requested)
    if requested > remaining:
        raise TransferDomainError(
            "La recepción supera la cantidad todavía en tránsito.",
            code="transfer_over_receipt",
        )


def validate_dispatch_quantity(*, requested: Decimal, available: Decimal) -> None:
    validate_positive_quantity(requested)
    if requested > available:
        raise TransferDomainError(
            "La cantidad solicitada supera la unidad logística disponible.",
            code="transfer_over_dispatch",
        )

