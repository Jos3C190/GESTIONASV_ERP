"""Envío de correo por SMTP con la biblioteca estándar (bloque V3c).

``smtplib`` es síncrono: cada envío corre en un hilo para no bloquear el bucle de eventos. El
remitente es la dirección del servidor (``SMTP_FROM_ADDRESS``) con el nombre de la empresa, y
``Reply-To`` lleva el correo DTE de la empresa, así el cliente responde a quien le facturó.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.domain.ports.email_sender import EmailDeliveryError, OutgoingEmail

SECURITY_MODES = ("none", "starttls", "ssl")
#: Respuestas SMTP 4xx: el servidor pide reintentar más tarde.
_TEMPORARY_REPLY = range(400, 500)


class SmtpEmailSender:
    def __init__(
        self,
        host: str,
        port: int,
        from_address: str,
        *,
        username: str | None = None,
        password: str | None = None,
        security: str = "starttls",
        timeout_seconds: float = 20,
    ) -> None:
        if security not in SECURITY_MODES:
            raise ValueError(f"SMTP_SECURITY debe ser uno de {', '.join(SECURITY_MODES)}")
        self._host = host
        self._port = port
        self._from = from_address
        self._username = username
        self._password = password
        self._security = security
        self._timeout = timeout_seconds

    def message(self, email: OutgoingEmail) -> EmailMessage:
        message = EmailMessage()
        message["From"] = formataddr((email.sender_name, self._from))
        message["To"] = ", ".join(email.recipients)
        if email.reply_to:
            message["Reply-To"] = email.reply_to
        message["Subject"] = email.subject
        message["Message-ID"] = make_msgid(domain=self._from.rsplit("@", 1)[-1])
        message.set_content(email.text)
        message.add_alternative(email.html, subtype="html")
        for attachment in email.attachments:
            maintype, _, subtype = attachment.content_type.partition("/")
            message.add_attachment(
                attachment.data,
                maintype=maintype,
                subtype=subtype or "octet-stream",
                filename=attachment.filename,
            )
        return message

    def _deliver(self, message: EmailMessage) -> None:
        context = ssl.create_default_context()
        client: smtplib.SMTP
        if self._security == "ssl":
            client = smtplib.SMTP_SSL(
                self._host, self._port, timeout=self._timeout, context=context
            )
        else:
            client = smtplib.SMTP(self._host, self._port, timeout=self._timeout)
        with client:
            if self._security == "starttls":
                client.starttls(context=context)
            if self._username:
                client.login(self._username, self._password or "")
            client.send_message(message)

    async def send(self, email: OutgoingEmail) -> str:
        if not email.recipients:
            raise EmailDeliveryError(
                "El correo no tiene destinatarios.", code="email_no_recipients", transient=False
            )
        message = self.message(email)
        try:
            await asyncio.to_thread(self._deliver, message)
        except smtplib.SMTPAuthenticationError as exc:
            raise EmailDeliveryError(
                "El servidor de correo rechazó las credenciales.",
                code="email_auth_failed",
                transient=False,
            ) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            raise EmailDeliveryError(
                "El servidor de correo rechazó los destinatarios.",
                code="email_recipients_refused",
                transient=False,
            ) from exc
        except smtplib.SMTPResponseException as exc:
            raise EmailDeliveryError(
                f"El servidor de correo respondió {exc.smtp_code}.",
                code="email_smtp_error",
                transient=exc.smtp_code in _TEMPORARY_REPLY,
            ) from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailDeliveryError(
                "No se pudo conectar con el servidor de correo.",
                code="email_unreachable",
                transient=True,
            ) from exc
        return str(message["Message-ID"])
