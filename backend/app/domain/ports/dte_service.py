"""Puerto del servicio DTE: registrar al emisor, emitir y bajar el JSON y el PDF."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


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
class IssueResult:
    status: str
    """Estado del servicio: SIMULADO, TRANSMITIDO, RECHAZADO, CONTINGENCIA, FIRMADO…"""
    generation_code: str | None
    control_number: str | None
    seal: str | None
    response: dict[str, Any] = field(default_factory=dict)


class DteService(Protocol):
    async def register_issuer(
        self, nit: str, *, name: str, mode: str, document_types: list[str]
    ) -> None: ...

    async def issue(
        self, document_type: str, *, nit: str, idempotency_key: str, body: dict[str, Any]
    ) -> IssueResult: ...

    async def document_json(self, nit: str, generation_code: str) -> dict[str, Any]: ...

    async def document_pdf(self, nit: str, generation_code: str) -> bytes: ...
