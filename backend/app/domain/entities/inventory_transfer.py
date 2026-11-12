"""Pure transfer lifecycle rules shared by API and persistence adapters."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class TransferStatus(StrEnum):
    PREPARATION = "preparation"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    CLOSED_WITH_ADJUSTMENT = "closed_with_adjustment"
    INCIDENT = "incident"
    CANCELLED = "cancelled"


class TransferRoute(StrEnum):
    CENTRAL_DISTRIBUTION = "central_distribution"
    BRANCH_TO_BRANCH = "branch_to_branch"
    BRANCH_TO_CENTRAL = "branch_to_central"


#: A transfer that has not left its origin yet and can still be called off.
CANCELLABLE_STATUSES = (
    TransferStatus.PREPARATION,
    TransferStatus.PENDING_APPROVAL,
    TransferStatus.APPROVED,
)
MIN_REJECTION_REASON_LENGTH = 5
MAX_REJECTION_REASON_LENGTH = 1000


class TransferDomainError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class TransferPolicy:
    """A company's transfer rules. Without a saved row: central distribution only."""

    allow_branch_to_branch: bool = False
    allow_branch_to_central: bool = False
    require_approval: bool = True

    def route_enabled(self, route: TransferRoute | str) -> bool:
        if route == TransferRoute.BRANCH_TO_BRANCH:
            return self.allow_branch_to_branch
        if route == TransferRoute.BRANCH_TO_CENTRAL:
            return self.allow_branch_to_central
        return True


@dataclass(frozen=True, slots=True)
class WarehouseFacts:
    """What route classification needs to know about one warehouse and its branch."""

    id: uuid.UUID
    branch_id: uuid.UUID | None
    is_central: bool
    is_transit: bool
    is_active: bool
    operational_status: str
    storage_eligible: bool
    branch_active: bool
    branch_is_headquarters: bool

    @property
    def operable(self) -> bool:
        return self.is_active and self.operational_status == "active" and not self.is_transit


_ROUTE_DISABLED_MESSAGES = {
    TransferRoute.BRANCH_TO_BRANCH: (
        "Los traslados entre sucursales no están habilitados en esta empresa."
    ),
    TransferRoute.BRANCH_TO_CENTRAL: (
        "Los retornos a la bodega central no están habilitados en esta empresa."
    ),
}
_BRANCH_INVALID = "El origen o destino no está asociado a una sucursal activa."
_DESTINATION_NOT_STORABLE = "El destino debe ser una bodega activa y apta para almacenar."


def route_disabled_error(route: TransferRoute | str) -> TransferDomainError:
    return TransferDomainError(
        _ROUTE_DISABLED_MESSAGES[TransferRoute(route)],
        code="transfer_route_disabled",
        status_code=409,
    )


def _classify_central_origin(origin: WarehouseFacts, destination: WarehouseFacts) -> TransferRoute:
    if (
        not destination.is_active
        or destination.operational_status != "active"
        or destination.is_central
        or destination.is_transit
        or destination.branch_id is None
    ):
        raise TransferDomainError(
            "El destino debe ser una bodega activa de sucursal.",
            code="transfer_destination_invalid",
            status_code=422,
        )
    if not (origin.branch_active and origin.branch_is_headquarters and destination.branch_active):
        raise TransferDomainError(_BRANCH_INVALID, code="transfer_branch_invalid")
    if not origin.storage_eligible:
        raise TransferDomainError(
            "La bodega de origen no está habilitada para despachos.", code="transfer_origin_invalid"
        )
    if not destination.storage_eligible:
        raise TransferDomainError(
            _DESTINATION_NOT_STORABLE, code="transfer_destination_invalid", status_code=422
        )
    return TransferRoute.CENTRAL_DISTRIBUTION


def _classify_branch_origin(
    origin: WarehouseFacts, destination: WarehouseFacts, policy: TransferPolicy
) -> TransferRoute:
    if not (policy.allow_branch_to_branch or policy.allow_branch_to_central):
        # With both branch routes off the answer is the one given before they existed.
        raise TransferDomainError(
            "El traslado a sucursal debe salir de la bodega central.",
            code="transfer_origin_not_central",
            status_code=422,
        )
    if origin.branch_id is not None and origin.branch_id == destination.branch_id:
        raise TransferDomainError(
            "Ambas bodegas pertenecen a la misma sucursal; este flujo es para traslados entre sucursales.",
            code="transfer_same_branch",
            status_code=422,
        )
    if not destination.operable or destination.branch_id is None:
        raise TransferDomainError(
            _DESTINATION_NOT_STORABLE, code="transfer_destination_invalid", status_code=422
        )
    if not origin.storage_eligible:
        raise TransferDomainError(
            "La bodega de origen no está habilitada para despachos.", code="transfer_origin_invalid"
        )
    if not destination.storage_eligible:
        raise TransferDomainError(
            _DESTINATION_NOT_STORABLE, code="transfer_destination_invalid", status_code=422
        )
    if not (origin.branch_active and destination.branch_active):
        raise TransferDomainError(_BRANCH_INVALID, code="transfer_branch_invalid")
    if destination.is_central:
        if not destination.branch_is_headquarters:
            raise TransferDomainError(_BRANCH_INVALID, code="transfer_branch_invalid")
        return TransferRoute.BRANCH_TO_CENTRAL
    return TransferRoute.BRANCH_TO_BRANCH


def classify_route(
    origin: WarehouseFacts, destination: WarehouseFacts, policy: TransferPolicy
) -> TransferRoute:
    """Name the route between two warehouses, or say why they cannot be linked.

    Distribution from the central warehouse keeps its original checks and is
    always available. A route that starts at a branch warehouse also needs the
    company to have turned that route on.
    """
    if origin.id == destination.id:
        raise TransferDomainError(
            "El origen y el destino deben ser distintos.",
            code="transfer_same_warehouse",
            status_code=422,
        )
    if not origin.operable:
        raise TransferDomainError(
            "La bodega de origen no está habilitada para despachos.", code="transfer_origin_invalid"
        )
    route = (
        _classify_central_origin(origin, destination)
        if origin.is_central
        else _classify_branch_origin(origin, destination, policy)
    )
    if not policy.route_enabled(route):
        raise route_disabled_error(route)
    return route


def approval_required(route: TransferRoute | str, policy: TransferPolicy) -> bool:
    """Distribution from the central warehouse never waits for approval."""
    return route != TransferRoute.CENTRAL_DISTRIBUTION and policy.require_approval


def require_preparation(status: str) -> None:
    if status != TransferStatus.PREPARATION:
        raise TransferDomainError(
            "Solo se puede editar un traslado en preparación.",
            code="transfer_not_in_preparation",
        )


def require_cancellable(status: str, route: TransferRoute | str) -> None:
    if status in CANCELLABLE_STATUSES:
        return
    if route == TransferRoute.CENTRAL_DISTRIBUTION:
        # The central route keeps the error contract it has always had.
        raise TransferDomainError(
            "Solo se puede editar o cancelar un traslado en preparación.",
            code="transfer_not_in_preparation",
        )
    raise TransferDomainError(
        "Solo se cancelan traslados que aún no se despachan.", code="transfer_not_cancellable"
    )


def require_submittable(status: str, route: TransferRoute | str, approval_needed: bool) -> None:
    if status != TransferStatus.PREPARATION:
        raise TransferDomainError(
            "Solo se envía a aprobación un traslado en preparación.",
            code="transfer_not_in_preparation",
        )
    if route == TransferRoute.CENTRAL_DISTRIBUTION:
        raise TransferDomainError(
            "Los traslados desde la bodega central no requieren aprobación.",
            code="transfer_approval_not_applicable",
            status_code=422,
        )
    if not approval_needed:
        raise TransferDomainError(
            "Esta empresa no exige aprobación para esta ruta; puedes despachar directamente.",
            code="transfer_approval_not_applicable",
            status_code=422,
        )


def require_pending_approval(status: str) -> None:
    if status != TransferStatus.PENDING_APPROVAL:
        raise TransferDomainError(
            "El traslado ya no está esperando aprobación.", code="transfer_not_pending_approval"
        )


def require_current_round(expected_round: int, current_round: int) -> None:
    if expected_round != current_round:
        raise TransferDomainError(
            "La solicitud cambió desde que la abriste; actualiza el documento antes de decidir.",
            code="transfer_approval_stale",
        )


def require_independent_approver(
    *,
    actor_id: uuid.UUID,
    created_by_id: uuid.UUID,
    submitted_by_id: uuid.UUID | None,
    last_edited_by_id: uuid.UUID | None = None,
    allow_self_approval: bool,
) -> None:
    if allow_self_approval:
        return
    if actor_id in (created_by_id, submitted_by_id, last_edited_by_id):
        raise TransferDomainError(
            "No puedes aprobar un traslado que tú preparaste, editaste o enviaste.",
            code="transfer_approval_self_forbidden",
            status_code=403,
        )


def validate_rejection_reason(reason: str) -> str:
    normalized = reason.strip()
    if not (MIN_REJECTION_REASON_LENGTH <= len(normalized) <= MAX_REJECTION_REASON_LENGTH):
        raise TransferDomainError(
            "Indica el motivo del rechazo (mínimo 5 caracteres).",
            code="transfer_rejection_reason_required",
            status_code=422,
        )
    return normalized


def require_dispatchable(
    status: str,
    line_count: int,
    route: TransferRoute | str = TransferRoute.CENTRAL_DISTRIBUTION,
    approval_needed: bool = False,
) -> None:
    if route == TransferRoute.CENTRAL_DISTRIBUTION:
        if status != TransferStatus.PREPARATION:
            raise TransferDomainError(
                "El traslado ya no está en preparación.", code="transfer_not_dispatchable"
            )
    elif status == TransferStatus.APPROVED or (
        status == TransferStatus.PREPARATION and not approval_needed
    ):
        pass
    elif status in (TransferStatus.PREPARATION, TransferStatus.PENDING_APPROVAL):
        raise TransferDomainError(
            "Este traslado necesita aprobación antes de despacharse.",
            code="transfer_approval_required",
        )
    else:
        raise TransferDomainError(
            "El traslado ya no está pendiente de despacho.", code="transfer_not_dispatchable"
        )
    if line_count < 1:
        raise TransferDomainError(
            "Agrega al menos una unidad logística al traslado.",
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
