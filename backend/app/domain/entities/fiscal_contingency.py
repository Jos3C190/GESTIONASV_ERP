"""Contingencia de facturación por establecimiento (bloque V4a del área de Ventas).

La ventana de contingencia vive en el servicio DTE, una por empresa y establecimiento. El ERP la
muestra, deja activarla y cerrarla, y guarda al responsable que firma el Evento de Contingencia
(Manual Funcional VIII: nombre, tipo y número de documento). Fuente de los tipos: CAT-005 y CAT-022.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_fiscal_document import CONTINGENCY_TYPES

#: CAT-022, documento del responsable: NIT, DUI, otro, pasaporte y carné de residente.
RESPONSIBLE_DOCUMENT_TYPES = {
    "36": "NIT",
    "13": "DUI",
    "37": "Otro",
    "03": "Pasaporte",
    "02": "Carné de residente",
}
OTHER_CONTINGENCY = 5
MAX_REASON = 500
MIN_REASON = 5
MIN_NAME = 3
MAX_NAME = 100
MAX_DOCUMENT = 25


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


@dataclass(frozen=True, slots=True)
class ContingencyResponsible:
    name: str
    document_type: str
    document_number: str


def validate_responsible(
    name: str, document_type: str, document_number: str
) -> ContingencyResponsible:
    clean = ContingencyResponsible(name.strip(), document_type.strip(), document_number.strip())
    if not MIN_NAME <= len(clean.name) <= MAX_NAME:
        raise _rule(
            "Escribe el nombre del responsable (de 3 a 100 caracteres).",
            "sales_contingency_responsible_invalid",
        )
    if clean.document_type not in RESPONSIBLE_DOCUMENT_TYPES:
        raise _rule(
            "Elige el tipo de documento del responsable.", "sales_contingency_responsible_invalid"
        )
    if not 1 <= len(clean.document_number) <= MAX_DOCUMENT:
        raise _rule(
            "Escribe el número de documento del responsable (hasta 25 caracteres).",
            "sales_contingency_responsible_invalid",
        )
    return clean


def validate_activation(contingency_type: int, reason: str | None) -> str | None:
    """Tipo de CAT-005 y motivo; el tipo 5 (otro) exige describirlo."""

    if contingency_type not in CONTINGENCY_TYPES:
        raise _rule("Elige el tipo de contingencia.", "sales_contingency_type_invalid")
    text = (reason or "").strip() or None
    if contingency_type == OTHER_CONTINGENCY and (text is None or len(text) < MIN_REASON):
        raise _rule(
            "Describe el motivo de la contingencia (mínimo 5 caracteres).",
            "sales_contingency_reason_required",
        )
    if text is not None and len(text) > MAX_REASON:
        raise _rule(
            f"El motivo admite como máximo {MAX_REASON} caracteres.",
            "sales_contingency_reason_required",
        )
    return text


@dataclass(frozen=True, slots=True)
class ContingencyDocuments:
    total: int
    in_contingency: int
    pending_transmission: int
    transmitted: int
    rejected: int


@dataclass(frozen=True, slots=True)
class ContingencyWindow:
    """Ventana del servicio DTE, con los plazos de 24 h (evento) y 72 h (documentos)."""

    id: int
    establishment_code: str | None
    status: str
    """ACTIVA, CERRADA, REPORTADA o COMPLETADA."""
    contingency_type: int
    reason: str | None
    forced: bool
    started_at: datetime
    ended_at: datetime | None
    documents: ContingencyDocuments
    event_status: str | None
    event_seal: str | None
    event_sealed_at: datetime | None
    event_deadline: datetime | None
    event_overdue: bool
    transmission_deadline: datetime | None
    transmission_overdue: bool
    last_error: str | None


@dataclass(frozen=True, slots=True)
class ContingencyOverview:
    windows: tuple[ContingencyWindow, ...]
    responsible_registered: bool
    """Si el servicio tiene un responsable para informar el evento por su cuenta."""
