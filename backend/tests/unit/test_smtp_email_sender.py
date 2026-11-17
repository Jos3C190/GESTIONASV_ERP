"""Envío SMTP: armado del mensaje, conexión según la seguridad y clasificación de errores."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any

import pytest
from app.domain.ports.email_sender import EmailAttachment, EmailDeliveryError, OutgoingEmail
from app.infrastructure import smtp_email_sender
from app.infrastructure.smtp_email_sender import SmtpEmailSender

EMAIL = OutgoingEmail(
    sender_name="Panadería Lorena",
    recipients=("cliente@example.com",),
    subject="Factura DTE-01-M001P001-000000000000001",
    text="Adjuntamos su factura.",
    html="<p>Adjuntamos su factura.</p>",
    reply_to="dte@example.com",
    attachments=(
        EmailAttachment("DTE-01.pdf", "application/pdf", b"%PDF-1.7"),
        EmailAttachment("DTE-01.json", "application/json", b"{}"),
    ),
)


class FakeSmtp:
    """Registra lo que el adaptador le pide al servidor."""

    instances: list[FakeSmtp] = []
    fail: Exception | None = None

    def __init__(self, host: str, port: int, **kwargs: Any) -> None:
        self.host = host
        self.port = port
        self.kwargs = kwargs
        self.calls: list[str] = []
        self.sent: list[EmailMessage] = []
        FakeSmtp.instances.append(self)

    def __enter__(self) -> FakeSmtp:
        return self

    def __exit__(self, *_: object) -> None:
        self.calls.append("quit")

    def starttls(self, **_: object) -> None:
        self.calls.append("starttls")

    def login(self, user: str, password: str) -> None:
        self.calls.append(f"login:{user}")

    def send_message(self, message: EmailMessage) -> None:
        if FakeSmtp.fail is not None:
            raise FakeSmtp.fail
        self.sent.append(message)


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSmtp.instances = []
    FakeSmtp.fail = None
    monkeypatch.setattr(smtp_email_sender.smtplib, "SMTP", FakeSmtp)
    monkeypatch.setattr(smtp_email_sender.smtplib, "SMTP_SSL", FakeSmtp)


async def test_sends_with_company_name_reply_to_and_attachments() -> None:
    sender = SmtpEmailSender(
        "mail.example.com", 587, "no-reply@example.com", username="erp", password="secreto"
    )
    message_id = await sender.send(EMAIL)
    server = FakeSmtp.instances[0]
    assert server.calls == ["starttls", "login:erp", "quit"]
    message = server.sent[0]
    sender_address = message["From"].addresses[0]
    assert sender_address.display_name == "Panadería Lorena"
    assert sender_address.addr_spec == "no-reply@example.com"
    assert message["Reply-To"] == "dte@example.com"
    assert message["Message-ID"] == message_id
    assert message_id.endswith("@example.com>")
    names = [part.get_filename() for part in message.iter_attachments()]
    assert names == ["DTE-01.pdf", "DTE-01.json"]
    body = message.get_body(("plain",))
    assert body is not None
    assert "Adjuntamos" in body.get_content()


async def test_plain_connection_without_login_for_the_local_mailbox() -> None:
    sender = SmtpEmailSender("mailpit", 1025, "no-reply@erp.local", security="none")
    await sender.send(EMAIL)
    assert FakeSmtp.instances[0].calls == ["quit"]
    with pytest.raises(ValueError, match="SMTP_SECURITY"):
        SmtpEmailSender("mailpit", 1025, "x@erp.local", security="tls")


@pytest.mark.parametrize(
    ("error", "code", "transient"),
    [
        (smtplib.SMTPAuthenticationError(535, b"no"), "email_auth_failed", False),
        (smtplib.SMTPRecipientsRefused({"x@y": (550, b"no")}), "email_recipients_refused", False),
        (smtplib.SMTPDataError(451, b"later"), "email_smtp_error", True),
        (smtplib.SMTPDataError(552, b"too big"), "email_smtp_error", False),
        (ConnectionRefusedError(), "email_unreachable", True),
    ],
)
async def test_errors_are_classified(error: Exception, code: str, transient: bool) -> None:
    FakeSmtp.fail = error
    with pytest.raises(EmailDeliveryError) as raised:
        await SmtpEmailSender("mailpit", 1025, "x@erp.local", security="none").send(EMAIL)
    assert raised.value.code == code
    assert raised.value.transient is transient


async def test_refuses_an_email_without_recipients() -> None:
    sender = SmtpEmailSender("mailpit", 1025, "x@erp.local", security="none")
    with pytest.raises(EmailDeliveryError) as raised:
        await sender.send(OutgoingEmail("Lorena", (), "Asunto", "texto", "<p>html</p>"))
    assert raised.value.code == "email_no_recipients"
    assert FakeSmtp.instances == []
