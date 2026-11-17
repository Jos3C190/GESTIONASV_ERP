"""Puerto de envío de correo (bloque V3c)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class EmailDeliveryError(Exception):
    """Fallo al enviar. ``transient`` dice si conviene reintentar."""

    def __init__(self, message: str, *, code: str, transient: bool) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.transient = transient


@dataclass(frozen=True, slots=True)
class EmailAttachment:
    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True, slots=True)
class OutgoingEmail:
    sender_name: str
    """Nombre visible del remitente; la dirección es la del servidor."""
    recipients: tuple[str, ...]
    subject: str
    text: str
    html: str
    reply_to: str | None = None
    attachments: tuple[EmailAttachment, ...] = field(default=())


class EmailSender(Protocol):
    async def send(self, email: OutgoingEmail) -> str:
        """Envía el correo y devuelve su ``Message-ID``."""
        ...
