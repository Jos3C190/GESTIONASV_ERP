"""SMTP propio de la empresa: leer, guardar, quitar y probar (bloque V3c)."""

from __future__ import annotations

import html
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from app.core.exceptions import NotFoundError
from app.core.secret_encryption import encrypt_secret
from app.domain.entities.company_email import (
    EmailSettings,
    EmailSettingsInput,
    validate_email_address,
    validate_settings,
)
from app.domain.ports.company_email_repository import CompanyEmailRepository, StoredEmailSettings
from app.domain.ports.email_sender import EmailDeliveryError, EmailSender, OutgoingEmail

#: Arma el remitente SMTP a partir de la configuración guardada (descifra la contraseña).
SenderFactory = Callable[[StoredEmailSettings], EmailSender]


@dataclass(frozen=True, slots=True)
class TestResult:
    ok: bool
    message: str


class CompanyEmailSettingsUseCases:
    def __init__(self, repo: CompanyEmailRepository, sender_factory: SenderFactory) -> None:
        self._repo = repo
        self._sender_factory = sender_factory

    async def get(self, company_id: uuid.UUID) -> EmailSettings | None:
        stored = await self._repo.get(company_id)
        return stored.settings if stored else None

    async def save(
        self, company_id: uuid.UUID, values: EmailSettingsInput, actor_id: uuid.UUID
    ) -> tuple[EmailSettings | None, EmailSettings]:
        before = await self._repo.get(company_id)
        clean = validate_settings(
            values,
            has_stored_password=bool(before and before.password_encrypted),
        )
        # Sin usuario no hay contraseña; con usuario y sin contraseña nueva se conserva.
        keep = bool(clean.username and not clean.password)
        encrypted = encrypt_secret(clean.password) if clean.password else None
        saved = await self._repo.save(
            company_id, clean, encrypted, keep_password=keep, actor_id=actor_id
        )
        return (before.settings if before else None), saved

    async def remove(self, company_id: uuid.UUID) -> bool:
        return await self._repo.delete(company_id)

    async def test(self, company_id: uuid.UUID, recipient: str, company_name: str) -> TestResult:
        stored = await self._repo.get(company_id)
        if stored is None:
            raise NotFoundError(
                "La empresa no tiene configurado su correo saliente.",
                code="email_settings_not_found",
            )
        address = validate_email_address(recipient, code="email_settings_test_recipient_invalid")
        settings = stored.settings
        sender_name = settings.from_name or company_name
        try:
            await self._sender_factory(stored).send(
                OutgoingEmail(
                    sender_name=sender_name,
                    recipients=(address,),
                    subject=f"Prueba de correo — {sender_name}",
                    text=(
                        "Este es un correo de prueba enviado desde el ERP con la configuración "
                        f"SMTP de {sender_name}.\n\nSi lo recibió, los documentos tributarios "
                        "electrónicos se enviarán a sus clientes desde "
                        f"{settings.from_address}.\n"
                    ),
                    html=(
                        "<p>Este es un correo de prueba enviado desde el ERP con la configuración "
                        f"SMTP de {html.escape(sender_name)}.</p><p>Si lo recibió, los documentos "
                        "tributarios electrónicos se enviarán a sus clientes desde "
                        f"{html.escape(settings.from_address)}.</p>"
                    ),
                )
            )
        except EmailDeliveryError as error:
            await self._repo.record_test(company_id, False, error.message)
            return TestResult(ok=False, message=error.message)
        await self._repo.record_test(company_id, True, None)
        return TestResult(ok=True, message=f"Se envió un correo de prueba a {address}.")
