"""Correo saliente propio de la empresa (bloque V3c).

La empresa envía los documentos a sus clientes desde su servidor SMTP y su dominio. El dominio y
su DNS (SPF, DKIM y DMARC) son responsabilidad de la empresa; el ERP valida los datos de conexión,
guarda la contraseña cifrada y deja probar el envío.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from app.core.exceptions import BusinessRuleError

SECURITY_MODES = ("none", "starttls", "ssl")
_EMAIL = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
_HOST = re.compile(r"^[A-Za-z0-9.-]+$")
_MAX_HOST = 255
_MAX_NAME = 150
_MAX_EMAIL = 254


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


@dataclass(frozen=True, slots=True)
class EmailSettingsInput:
    host: str
    port: int
    security: str
    username: str | None
    password: str | None
    """Vacío al editar: se conserva la contraseña guardada."""
    from_address: str
    from_name: str | None
    is_enabled: bool


@dataclass(frozen=True, slots=True)
class EmailSettings:
    host: str
    port: int
    security: str
    username: str | None
    has_password: bool
    from_address: str
    from_name: str | None
    is_enabled: bool
    last_test_at: datetime | None = None
    last_test_ok: bool | None = None
    last_test_error: str | None = None
    updated_at: datetime | None = None


def validate_email_address(value: str, *, code: str) -> str:
    address = value.strip().lower()
    if len(address) > _MAX_EMAIL or not _EMAIL.match(address):
        raise _rule(f"«{value.strip()}» no es un correo válido.", code)
    return address


def validate_settings(
    values: EmailSettingsInput, *, has_stored_password: bool
) -> EmailSettingsInput:
    """Normaliza la configuración y explica en español qué está mal."""

    host = values.host.strip().lower()
    if not host or len(host) > _MAX_HOST or not _HOST.match(host):
        raise _rule(
            "Escribe el servidor SMTP, por ejemplo smtp.gmail.com.", "email_settings_host_invalid"
        )
    if not 1 <= values.port <= 65535:  # noqa: PLR2004 - rango de puertos TCP
        raise _rule("El puerto va de 1 a 65535.", "email_settings_port_invalid")
    if values.security not in SECURITY_MODES:
        raise _rule(
            "La seguridad debe ser ninguna, STARTTLS o SSL.", "email_settings_security_invalid"
        )
    username = (values.username or "").strip() or None
    password = values.password or None
    if password and not username:
        raise _rule(
            "Escribe el usuario junto con la contraseña.", "email_settings_username_required"
        )
    if username and not password and not has_stored_password:
        raise _rule("Escribe la contraseña del usuario SMTP.", "email_settings_password_required")
    from_name = " ".join((values.from_name or "").split()) or None
    if from_name and len(from_name) > _MAX_NAME:
        raise _rule(
            "El nombre del remitente tiene 150 caracteres como máximo.",
            "email_settings_from_name_too_long",
        )
    return EmailSettingsInput(
        host=host,
        port=values.port,
        security=values.security,
        username=username,
        password=password,
        from_address=validate_email_address(
            values.from_address, code="email_settings_from_invalid"
        ),
        from_name=from_name,
        is_enabled=values.is_enabled,
    )
