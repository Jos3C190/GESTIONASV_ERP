"""Protección de datos personales: plazos, solicitudes ARCO-POL, aviso y vulneraciones.

Ley para la Protección de Datos Personales (D.L. 144 de 2024, reformada por el D.L. 659 de
2026): arts. 18 a 22 (solicitudes), 24 (aviso), 25 (vulneraciones) y 30 (revocación). Los días
hábiles excluyen sábados, domingos y los asuetos nacionales del Código de Trabajo (art. 190).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from app.core.exceptions import BusinessRuleError

RESPONSE_DAYS = 20  # art. 20
EXTENSION_DAYS = 20  # art. 20
CORRECTION_DAYS = 10  # art. 18
RETURN_DAYS = 5  # art. 19
REVOCATION_DAYS = 5  # art. 30
INCIDENT_HOURS = 72  # art. 25
MIN_REASON = 10


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


# --- días hábiles ---


def easter_sunday(year: int) -> date:
    """Domingo de Pascua (algoritmo gregoriano anónimo)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def national_holidays(year: int) -> frozenset[date]:
    """Asuetos nacionales remunerados del Código de Trabajo, art. 190."""
    easter = easter_sunday(year)
    fixed = [(1, 1), (5, 1), (5, 10), (6, 17), (8, 6), (9, 15), (11, 2), (12, 25)]
    holy_week = [easter - timedelta(days=offset) for offset in (3, 2, 1)]
    return frozenset([date(year, month, day) for month, day in fixed] + holy_week)


def is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in national_holidays(day.year)  # noqa: PLR2004


def add_business_days(start: date, days: int) -> date:
    """Fecha en que vencen ``days`` días hábiles contados desde el día siguiente a ``start``."""
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if is_business_day(current):
            remaining -= 1
    return current


# --- solicitudes ARCO-POL ---


class RightType(StrEnum):
    ACCESS = "access"
    RECTIFICATION = "rectification"
    CANCELLATION = "cancellation"
    OPPOSITION = "opposition"
    PORTABILITY = "portability"
    ERASURE = "erasure"  # derecho al olvido
    RESTRICTION = "restriction"


class RequestStatus(StrEnum):
    RECEIVED = "received"
    IN_PROGRESS = "in_progress"
    AWAITING_CORRECTION = "awaiting_correction"
    EXTENDED = "extended"
    RESOLVED = "resolved"
    DENIED = "denied"
    RETURNED = "returned"
    ARCHIVED = "archived"


OPEN_STATUSES = frozenset(
    {
        RequestStatus.RECEIVED,
        RequestStatus.IN_PROGRESS,
        RequestStatus.AWAITING_CORRECTION,
        RequestStatus.EXTENDED,
    }
)
WORKING_STATUSES = frozenset(
    {RequestStatus.RECEIVED, RequestStatus.IN_PROGRESS, RequestStatus.EXTENDED}
)
ERASING_RIGHTS = frozenset({RightType.CANCELLATION, RightType.ERASURE})


class RequestAction(StrEnum):
    START = "start"
    REQUEST_CORRECTION = "request_correction"
    CORRECTION_RECEIVED = "correction_received"
    EXTEND = "extend"
    RESOLVE = "resolve"
    DENY = "deny"
    RETURN = "return"
    ARCHIVE = "archive"


_ALLOWED: dict[RequestAction, frozenset[RequestStatus]] = {
    RequestAction.START: frozenset({RequestStatus.RECEIVED}),
    RequestAction.REQUEST_CORRECTION: frozenset(
        {RequestStatus.RECEIVED, RequestStatus.IN_PROGRESS}
    ),
    RequestAction.CORRECTION_RECEIVED: frozenset({RequestStatus.AWAITING_CORRECTION}),
    RequestAction.EXTEND: frozenset({RequestStatus.RECEIVED, RequestStatus.IN_PROGRESS}),
    RequestAction.RESOLVE: WORKING_STATUSES,
    RequestAction.DENY: WORKING_STATUSES,
    RequestAction.RETURN: frozenset({RequestStatus.RECEIVED, RequestStatus.IN_PROGRESS}),
    RequestAction.ARCHIVE: frozenset({RequestStatus.AWAITING_CORRECTION}),
}
_TARGET: dict[RequestAction, RequestStatus] = {
    RequestAction.START: RequestStatus.IN_PROGRESS,
    RequestAction.REQUEST_CORRECTION: RequestStatus.AWAITING_CORRECTION,
    RequestAction.CORRECTION_RECEIVED: RequestStatus.IN_PROGRESS,
    RequestAction.EXTEND: RequestStatus.EXTENDED,
    RequestAction.RESOLVE: RequestStatus.RESOLVED,
    RequestAction.DENY: RequestStatus.DENIED,
    RequestAction.RETURN: RequestStatus.RETURNED,
    RequestAction.ARCHIVE: RequestStatus.ARCHIVED,
}
#: Acciones que cierran la solicitud y exigen una respuesta escrita.
CLOSING_ACTIONS = frozenset(
    {RequestAction.RESOLVE, RequestAction.DENY, RequestAction.RETURN, RequestAction.ARCHIVE}
)


@dataclass(frozen=True, slots=True)
class RequestState:
    status: RequestStatus
    received_on: date
    due_on: date
    correction_due_on: date | None
    extended_due_on: date | None

    @property
    def effective_due_on(self) -> date:
        return self.extended_due_on or self.due_on

    def overdue(self, today: date) -> bool:
        return self.status in OPEN_STATUSES and today > self.effective_due_on


@dataclass(frozen=True, slots=True)
class Transition:
    status: RequestStatus
    correction_due_on: date | None
    extended_due_on: date | None
    extension_reason: str | None
    resolution: str | None
    closes: bool


def apply_action(
    state: RequestState,
    action: RequestAction,
    *,
    today: date,
    text: str | None,
    extension_reason: str | None,
) -> Transition:
    """Valida y calcula el cambio de estado de una solicitud."""
    if state.status not in _ALLOWED[action]:
        raise _rule(
            "Esa acción no aplica al estado actual de la solicitud.",
            "privacy_request_action_invalid",
        )
    note = (text or "").strip() or None
    reason = (extension_reason or "").strip() or None
    correction_due = state.correction_due_on
    extended_due = state.extended_due_on
    if action == RequestAction.EXTEND:
        if reason is None or len(reason) < MIN_REASON:
            raise _rule(
                "La prórroga requiere una causa justificada (al menos 10 caracteres).",
                "privacy_request_extension_reason_required",
            )
        extended_due = add_business_days(state.due_on, EXTENSION_DAYS)
    if action == RequestAction.REQUEST_CORRECTION:
        if note is None:
            raise _rule(
                "Indica qué debe corregir o completar el titular.",
                "privacy_request_correction_note_required",
            )
        correction_due = add_business_days(today, CORRECTION_DAYS)
    if action == RequestAction.CORRECTION_RECEIVED:
        correction_due = None
    if action == RequestAction.ARCHIVE and correction_due and today <= correction_due:
        raise _rule(
            "Solo se archiva cuando venció el plazo de 10 días hábiles para corregir.",
            "privacy_request_archive_too_early",
        )
    if action in CLOSING_ACTIONS and (note is None or len(note) < MIN_REASON):
        raise _rule(
            "Escribe la respuesta o el motivo que se comunicará al titular "
            "(al menos 10 caracteres).",
            "privacy_request_resolution_required",
        )
    return Transition(
        status=_TARGET[action],
        correction_due_on=correction_due,
        extended_due_on=extended_due,
        extension_reason=reason if action == RequestAction.EXTEND else None,
        resolution=note if action in CLOSING_ACTIONS else None,
        closes=action in CLOSING_ACTIONS,
    )


def new_request_due(received_on: date) -> date:
    return add_business_days(received_on, RESPONSE_DAYS)


def return_due(received_on: date) -> date:
    return add_business_days(received_on, RETURN_DAYS)


def require_erasure_request(right: RightType, status: RequestStatus) -> None:
    if right not in ERASING_RIGHTS or status not in WORKING_STATUSES:
        raise _rule(
            "Para anonimizar al cliente debe haber una solicitud de cancelación u olvido "
            "en trámite.",
            "privacy_erasure_request_required",
        )


# --- aviso de privacidad (art. 24) ---

#: Elementos mínimos del aviso, en el orden del art. 24.
NOTICE_ELEMENTS: dict[str, str] = {
    "controller_address": "Domicilio del responsable.",
    "data_processed": "Datos personales que se tratan, identificando los sensibles.",
    "legal_basis": "Fundamento legal del tratamiento.",
    "purposes": "Finalidades, distinguiendo las que requieren consentimiento.",
    "rights_and_revocation": "Cómo ejercer los derechos ARCO-POL y revocar el consentimiento.",
    "request_channels": "Medios para presentar las solicitudes de derechos ARCO-POL.",
    "notice_changes": "Cómo se comunicarán los cambios al aviso.",
    "processor": "Encargado del tratamiento, si lo hay.",
    "cookies": "Uso de cookies.",
}


def require_notice_complete(title: str, body: str, covered: list[str]) -> tuple[str, ...]:
    if len(title.strip()) < 5:  # noqa: PLR2004
        raise _rule("Escribe el título del aviso.", "privacy_notice_title_required")
    if len(body.strip()) < 200:  # noqa: PLR2004
        raise _rule(
            "El aviso es demasiado corto para cubrir lo que exige la ley.",
            "privacy_notice_body_too_short",
        )
    unknown = [item for item in covered if item not in NOTICE_ELEMENTS]
    if unknown:
        raise _rule("Hay elementos del aviso que no existen.", "privacy_notice_element_unknown")
    missing = [text for key, text in NOTICE_ELEMENTS.items() if key not in covered]
    if missing:
        raise _rule(
            "Antes de publicar, confirma que el aviso incluye: " + " ".join(missing),
            "privacy_notice_incomplete",
        )
    return tuple(key for key in NOTICE_ELEMENTS if key in covered)


def notice_template(
    *, company_name: str, address: str, email: str | None, phone: str | None
) -> str:
    contact = " o ".join(part for part in (email, phone) if part) or "nuestras sucursales"
    return (
        f"{company_name}, con domicilio en {address}, es responsable del tratamiento de los "
        "datos personales de sus clientes.\n\n"
        "Datos que tratamos: nombre, documento de identidad, NIT y NRC, dirección, teléfono "
        "y correo electrónico. No tratamos datos sensibles.\n\n"
        "Fundamento legal: la relación comercial con el cliente y las obligaciones tributarias "
        "de emitir y conservar documentos fiscales (Código Tributario, arts. 114 y 147). Los "
        "datos para facturar no requieren consentimiento (Ley para la Protección de Datos "
        "Personales, art. 28).\n\n"
        "Finalidades: facturar, entregar y cobrar las compras. Solo con tu consentimiento: "
        "enviarte promociones y novedades.\n\n"
        "Tus derechos: puedes pedir acceso, rectificación, cancelación, oposición, "
        "portabilidad, olvido o limitación del tratamiento de tus datos, y revocar tu "
        f"consentimiento, escribiendo a {contact} o en cualquiera de nuestras sucursales. "
        "Respondemos en un máximo de veinte días hábiles.\n\n"
        "Cambios a este aviso: los publicaremos en nuestras sucursales y en los documentos que "
        "te enviemos.\n\n"
        "Encargado del tratamiento: el proveedor del sistema de gestión, que trata los datos "
        "solo por cuenta nuestra.\n\n"
        "Cookies: el sistema usa solo las cookies necesarias para la sesión."
    )


# --- consentimientos ---


class ConsentPurpose(StrEnum):
    MARKETING = "marketing"
    PROFILING = "profiling"
    THIRD_PARTY_SHARING = "third_party_sharing"


class Channel(StrEnum):
    IN_PERSON = "in_person"
    PHONE = "phone"
    EMAIL = "email"
    WEB = "web"
    WRITTEN = "written"


# --- vulneraciones (art. 25) ---


@dataclass(frozen=True, slots=True)
class IncidentNotifications:
    ace_at: datetime | None
    prosecutor_at: datetime | None
    subjects_at: datetime | None
    subjects_not_required_reason: str | None


def notification_deadline(discovered_at: datetime) -> datetime:
    return discovered_at + timedelta(hours=INCIDENT_HOURS)


def require_incident_closable(notes: IncidentNotifications) -> None:
    missing: list[str] = []
    if notes.ace_at is None:
        missing.append("a la Agencia de Ciberseguridad del Estado")
    if notes.prosecutor_at is None:
        missing.append("a la Fiscalía General de la República")
    if notes.subjects_at is None and not (notes.subjects_not_required_reason or "").strip():
        missing.append("a los titulares afectados (o el motivo por el que no aplica)")
    if missing:
        raise _rule(
            "Para cerrar la vulneración registra la notificación " + ", ".join(missing) + ".",
            "privacy_incident_notifications_missing",
        )


@dataclass(frozen=True, slots=True)
class AnonymizationTarget:
    customer_id: uuid.UUID
    request_id: uuid.UUID
