"""Puerto del servicio DTE: registrar al emisor, emitir y bajar el JSON y el PDF."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from app.domain.entities.fiscal_contingency import (
    ContingencyOverview,
    ContingencyResponsible,
    ContingencyWindow,
)


class DteServiceError(Exception):
    """Fallo del servicio. ``transient`` dice si conviene reintentar con la misma clave."""

    def __init__(
        self, message: str, *, code: str, transient: bool, status: int | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.transient = transient
        self.status = status


@dataclass(frozen=True, slots=True)
class IssuerCredentials:
    """Credenciales de Hacienda en claro, solo en memoria para entregarlas al servicio."""

    api_password: str
    private_key_password: str
    certificate: bytes


@dataclass(frozen=True, slots=True)
class ConnectionCheck:
    ok: bool
    authentication_ok: bool
    authentication_message: str
    signature_ok: bool
    signature_message: str


@dataclass(frozen=True, slots=True)
class IssueResult:
    status: str
    """Estado del servicio: SIMULADO, TRANSMITIDO, RECHAZADO, CONTINGENCIA, FIRMADO…"""
    generation_code: str | None
    control_number: str | None
    seal: str | None
    response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DocumentState:
    """Estado de un documento en el servicio (seguimiento de la contingencia, V4a)."""

    status: str
    seal: str | None


@dataclass(frozen=True, slots=True)
class InvalidationWindow:
    """Plazo para invalidar un documento según el servicio (V4b)."""

    deadline: date
    expired: bool
    estimated: bool
    """El décimo día hábil depende de los feriados: el servicio lo estima."""


@dataclass(frozen=True, slots=True)
class InvalidationRequest:
    kind: int
    reason: str | None
    responsible: ContingencyResponsible
    requester: ContingencyResponsible
    replacement_generation_code: str | None = None


@dataclass(frozen=True, slots=True)
class InvalidationResult:
    accepted: bool
    event_generation_code: str | None
    seal: str | None
    message: str | None
    response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReturnEventResult:
    """Respuesta del servicio a un evento de retorno o a su anulación (V4d2)."""

    accepted: bool
    generation_code: str | None
    seal: str | None
    """Sello de Hacienda o, en simulado, el marcador del evento."""
    simulated: bool
    message: str | None
    response: dict[str, Any] = field(default_factory=dict)


class DteService(Protocol):
    async def register_issuer(
        self,
        nit: str,
        *,
        name: str,
        mode: str,
        document_types: list[str],
        credentials: IssuerCredentials | None = None,
        responsible: ContingencyResponsible | None = None,
    ) -> None: ...

    async def test_issuer(self, nit: str) -> ConnectionCheck: ...

    async def issue(
        self, document_type: str, *, nit: str, idempotency_key: str, body: dict[str, Any]
    ) -> IssueResult: ...

    async def document_state(self, nit: str, generation_code: str) -> DocumentState: ...

    async def document_json(self, nit: str, generation_code: str) -> dict[str, Any]: ...

    async def document_pdf(self, nit: str, generation_code: str) -> bytes: ...

    # --- invalidación (V4b) ---

    async def invalidation_window(self, nit: str, generation_code: str) -> InvalidationWindow: ...

    async def invalidate(
        self,
        nit: str,
        generation_code: str,
        *,
        idempotency_key: str,
        request: InvalidationRequest,
    ) -> InvalidationResult:
        """Aceptada o rechazada por Hacienda; lanza ``DteServiceError`` si no hubo respuesta."""
        ...

    async def invalidation_pdf(self, nit: str, event_generation_code: str) -> bytes: ...

    # --- evento de retorno (V4d2) ---

    async def issue_return(
        self, nit: str, invoice_generation_code: str, *, idempotency_key: str, body: dict[str, Any]
    ) -> ReturnEventResult:
        """Aceptado o rechazado; lanza ``DteServiceError`` si no hubo respuesta."""
        ...

    async def annul_return(
        self,
        nit: str,
        return_generation_code: str,
        *,
        idempotency_key: str,
        request: InvalidationRequest,
    ) -> ReturnEventResult: ...

    async def event_json(self, nit: str, event_generation_code: str) -> dict[str, Any]: ...

    # --- contingencia por establecimiento (V4a) ---

    async def contingencies(self, nit: str) -> ContingencyOverview: ...

    async def activate_contingency(
        self, nit: str, *, establishment_code: str, contingency_type: int, reason: str | None
    ) -> ContingencyWindow: ...

    async def close_contingency(self, nit: str, window_id: int) -> ContingencyWindow: ...

    async def send_contingency_event(self, nit: str, window_id: int) -> ContingencyWindow: ...
