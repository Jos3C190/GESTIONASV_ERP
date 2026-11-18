"""Puerto del servicio DTE: registrar al emisor, emitir y bajar el JSON y el PDF."""

from __future__ import annotations

from dataclasses import dataclass, field
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

    # --- contingencia por establecimiento (V4a) ---

    async def contingencies(self, nit: str) -> ContingencyOverview: ...

    async def activate_contingency(
        self, nit: str, *, establishment_code: str, contingency_type: int, reason: str | None
    ) -> ContingencyWindow: ...

    async def close_contingency(self, nit: str, window_id: int) -> ContingencyWindow: ...

    async def send_contingency_event(self, nit: str, window_id: int) -> ContingencyWindow: ...
