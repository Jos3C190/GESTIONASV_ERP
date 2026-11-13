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
    PARTIALLY_RECEIVED = "partially_received"
    DISCREPANCY = "discrepancy"
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
#: The vehicle and the driver are busy and the GPS is watched while a transfer is here.
ON_ROAD_STATUSES = (
    TransferStatus.IN_TRANSIT,
    TransferStatus.PARTIALLY_RECEIVED,
    TransferStatus.INCIDENT,
)
#: The trip is over (even if differences are still open): its trail is archived.
TRIP_FINISHED_STATUSES = (
    TransferStatus.DISCREPANCY,
    TransferStatus.RECEIVED,
    TransferStatus.CLOSED_WITH_ADJUSTMENT,
)
#: Nothing changes the status of a transfer in one of these.
FINAL_STATUSES = (
    TransferStatus.RECEIVED,
    TransferStatus.CLOSED_WITH_ADJUSTMENT,
    TransferStatus.CANCELLED,
)
MIN_REJECTION_REASON_LENGTH = 5
MAX_REJECTION_REASON_LENGTH = 1000
MIN_DISCREPANCY_NOTES_LENGTH = 5
MIN_SUBSTITUTION_REASON_LENGTH = 10


class DiscrepancyKind(StrEnum):
    SHORTAGE = "shortage"
    SURPLUS = "surplus"
    DAMAGE = "damage"


class DiscrepancyStatus(StrEnum):
    OPEN = "open"
    IN_CLAIM = "in_claim"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class DiscrepancySource(StrEnum):
    RECEIPT = "receipt"
    RECEPTION_CLOSE = "reception_close"
    INCIDENT = "incident"


class DamageType(StrEnum):
    BROKEN = "broken"
    CRUSHED = "crushed"
    WET = "wet"
    CONTAMINATED = "contaminated"
    PACKAGING = "packaging"
    TAMPERED = "tampered"
    TEMPERATURE = "temperature"
    OTHER = "other"


class DiscrepancyResolution(StrEnum):
    WRITTEN_OFF = "written_off"
    FOUND = "found"
    RELEASED = "released"
    REGULARIZED = "regularized"
    DISMISSED = "dismissed"


class SubstitutionCode(StrEnum):
    VEHICLE_UNFIT = "vehicle_unfit"
    VEHICLE_UNAVAILABLE = "vehicle_unavailable"
    DRIVER_UNFIT = "driver_unfit"
    DRIVER_UNAVAILABLE = "driver_unavailable"
    LOAD_CHANGE = "load_change"
    OTHER = "other"


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
    if status not in (TransferStatus.IN_TRANSIT, TransferStatus.PARTIALLY_RECEIVED):
        raise TransferDomainError(
            "Solo se reciben traslados en tránsito o con recepción parcial.",
            code="transfer_not_receivable",
        )


def require_incident_openable(status: str) -> None:
    if status not in (TransferStatus.IN_TRANSIT, TransferStatus.PARTIALLY_RECEIVED):
        raise TransferDomainError(
            "Solo puede abrir una incidencia de un traslado en tránsito.",
            code="transfer_incident_not_allowed",
        )


def require_reception_closable(status: str, *, received_any: bool) -> None:
    """Closing a reception only makes sense once part of the load has arrived."""
    if status not in (TransferStatus.IN_TRANSIT, TransferStatus.PARTIALLY_RECEIVED):
        raise TransferDomainError(
            "Solo se cierra la recepción de un traslado en recepción parcial.",
            code="transfer_reception_close_not_allowed",
        )
    if not received_any:
        raise TransferDomainError(
            "Si no llegó nada, reporta una incidencia del traslado.",
            code="transfer_reception_close_requires_receipt",
        )


def require_assignment_for_submission(
    vehicle_id: uuid.UUID | None, driver_id: uuid.UUID | None
) -> None:
    if vehicle_id is None or driver_id is None:
        raise TransferDomainError(
            "Elige vehículo y conductor antes de enviar el traslado a aprobación.",
            code="transfer_assignment_required",
            status_code=422,
        )


def require_substitution(*, code: str | None, reason: str | None) -> tuple[str, str]:
    """A different vehicle or driver than the approved ones needs a code and a reason."""
    normalized = (reason or "").strip()
    if len(normalized) < MIN_SUBSTITUTION_REASON_LENGTH:
        raise TransferDomainError(
            "Indica por qué cambias el vehículo o el conductor aprobado (mínimo 10 caracteres).",
            code="transfer_substitution_reason_required",
            status_code=422,
        )
    if code not in {item.value for item in SubstitutionCode}:
        raise TransferDomainError(
            "Elige el motivo del cambio de vehículo o conductor.",
            code="transfer_substitution_code_invalid",
            status_code=422,
        )
    return str(code), normalized


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


def _non_negative(value: Decimal) -> bool:
    return value.is_finite() and value >= 0


def validate_receipt_line(
    *,
    good: Decimal,
    damaged: Decimal = Decimal("0"),
    surplus: Decimal = Decimal("0"),
    pending: Decimal,
    damage_type: str | None = None,
    damage_notes: str | None = None,
    surplus_notes: str | None = None,
) -> None:
    """One receipt line: what arrived well, what arrived damaged and what is extra."""
    if not (_non_negative(good) and _non_negative(damaged) and _non_negative(surplus)):
        raise TransferDomainError(
            "Las cantidades deben ser decimales positivos o cero.",
            code="transfer_quantity_invalid",
            status_code=422,
        )
    received = good + damaged
    if received <= 0:
        raise TransferDomainError(
            "Indica cuánto recibiste de esta línea.",
            code="transfer_receipt_empty",
            status_code=422,
        )
    if received > pending:
        raise TransferDomainError(
            "La recepción supera la cantidad todavía en tránsito.",
            code="transfer_over_receipt",
        )
    if surplus > 0 and received != pending:
        raise TransferDomainError(
            "Declara sobrante solo cuando registras todo lo pendiente de la línea.",
            code="transfer_surplus_requires_full_receipt",
            status_code=422,
        )
    if damaged > 0 and (
        damage_type not in {item.value for item in DamageType}
        or len((damage_notes or "").strip()) < MIN_DISCREPANCY_NOTES_LENGTH
    ):
        raise TransferDomainError(
            "Indica el tipo de avería y descríbela (mínimo 5 caracteres).",
            code="transfer_damage_details_required",
            status_code=422,
        )
    if surplus > 0 and len((surplus_notes or "").strip()) < MIN_DISCREPANCY_NOTES_LENGTH:
        raise TransferDomainError(
            "Describe el sobrante (mínimo 5 caracteres).",
            code="transfer_surplus_notes_required",
            status_code=422,
        )


def settle_transfer_status(
    *,
    current_status: str,
    uncovered_pending: Decimal,
    has_open_discrepancies: bool,
    had_discrepancy: bool,
    had_loss: bool,
    received_any: bool,
    incident_open: bool,
) -> TransferStatus:
    """The status a dispatched transfer takes once its quantities and differences are known.

    ``uncovered_pending`` is what was dispatched minus what was received, returned,
    adjusted out or already declared missing. A final state is never reopened.
    """
    if current_status in FINAL_STATUSES:
        return TransferStatus(current_status)
    if incident_open:
        return TransferStatus.INCIDENT
    if uncovered_pending > 0:
        return TransferStatus.PARTIALLY_RECEIVED if received_any else TransferStatus.IN_TRANSIT
    if has_open_discrepancies:
        return TransferStatus.DISCREPANCY
    if had_discrepancy or had_loss:
        return TransferStatus.CLOSED_WITH_ADJUSTMENT
    return TransferStatus.RECEIVED


def require_discrepancy_open(status: str, *, allow_claim: bool = False) -> None:
    allowed = (
        (DiscrepancyStatus.OPEN, DiscrepancyStatus.IN_CLAIM)
        if allow_claim
        else (DiscrepancyStatus.OPEN,)
    )
    if status not in allowed:
        raise TransferDomainError(
            "Esta diferencia ya no está abierta.", code="transfer_discrepancy_not_open"
        )


def require_discrepancy_kind(kind: str, *allowed: DiscrepancyKind) -> None:
    if kind not in allowed:
        raise TransferDomainError(
            "Esta acción no corresponde al tipo de diferencia.",
            code="transfer_discrepancy_action_invalid",
        )


def validate_dispatch_quantity(*, requested: Decimal, available: Decimal) -> None:
    validate_positive_quantity(requested)
    if requested > available:
        raise TransferDomainError(
            "La cantidad solicitada supera la unidad logística disponible.",
            code="transfer_over_dispatch",
        )
