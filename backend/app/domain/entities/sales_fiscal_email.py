"""Correo del documento fiscal al cliente (bloque V3c).

El correo lleva el PDF y el JSON del DTE, los datos para identificarlo (número de control, código
de generación, fecha y total) y el aviso de privacidad vigente de la empresa (Ley de Protección
de Datos Personales, art. 24). Un documento simulado se marca en el asunto y en el cuerpo.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from zoneinfo import ZoneInfo

from app.core.exceptions import BusinessRuleError

MAX_RECIPIENTS = 5
SIMULATED_MARK = "SIMULADO — sin validez fiscal"
DOCUMENT_NAMES = {"01": "Factura", "03": "Comprobante de crédito fiscal"}
_ZONE = ZoneInfo("America/El_Salvador")
_EMAIL = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
_MAX_EMAIL = 254


class EmailOrigin(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


class EmailStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


def normalize_recipients(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Destinatarios limpios, sin repetir y en minúsculas; de 1 a 5."""

    seen: list[str] = []
    for raw in values:
        address = raw.strip().lower()
        if not address:
            continue
        if len(address) > _MAX_EMAIL or not _EMAIL.match(address):
            raise _rule(f"«{raw.strip()}» no es un correo válido.", "sales_invoice_email_invalid")
        if address not in seen:
            seen.append(address)
    if not seen:
        raise _rule("Indica al menos un correo.", "sales_invoice_email_required")
    if len(seen) > MAX_RECIPIENTS:
        raise _rule(
            f"Se envía a {MAX_RECIPIENTS} correos como máximo.", "sales_invoice_email_too_many"
        )
    return tuple(seen)


def customer_recipients(email: str | None) -> tuple[str, ...]:
    """El correo de la ficha del cliente para el envío automático; vacío si no sirve."""

    try:
        return normalize_recipients([email or ""])
    except BusinessRuleError:
        return ()


@dataclass(frozen=True, slots=True)
class PrivacyNoticeText:
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class FiscalEmailContent:
    company_name: str
    document_type: str
    control_number: str
    generation_code: str
    issued_at: datetime
    total: Decimal
    customer_name: str
    simulated: bool
    reply_to: str | None = None
    contingency: bool = False
    """Generado en contingencia: se avisa que se transmitirá a Hacienda después (V4a)."""
    privacy_notice: PrivacyNoticeText | None = None


@dataclass(frozen=True, slots=True)
class ComposedEmail:
    subject: str
    text: str
    html: str
    pdf_filename: str
    json_filename: str


def _money(value: Decimal) -> str:
    return f"${value:,.2f}"


CONTINGENCY_NOTE = (
    "Este documento se generó en contingencia, sin comunicación con Hacienda; se le "
    "transmitirá al restablecerse el servicio."
)


def _day(value: datetime) -> str:
    return value.astimezone(_ZONE).strftime("%d/%m/%Y")


def compose(content: FiscalEmailContent) -> ComposedEmail:
    name = DOCUMENT_NAMES.get(content.document_type, "Documento tributario electrónico")
    subject = f"{name} {content.control_number} — {content.company_name}"
    if content.simulated:
        subject = f"[{SIMULATED_MARK}] {subject}"
    facts = [
        ("Documento", name),
        ("Número de control", content.control_number),
        ("Código de generación", content.generation_code.upper()),
        ("Fecha de emisión", _day(content.issued_at)),
        ("Total", _money(content.total)),
    ]
    reply = (
        f"Si tiene dudas sobre este documento, responda a este correo ({content.reply_to})."
        if content.reply_to
        else "Si tiene dudas sobre este documento, comuníquese con nosotros."
    )
    lines = [f"Estimado/a {content.customer_name}:", ""]
    if content.simulated:
        lines += [f"*** {SIMULATED_MARK}: documento de prueba, no fue enviado a Hacienda. ***", ""]
    lines += [
        f"{content.company_name} le envía su {name.lower()} electrónica. Adjuntamos el PDF y el "
        "archivo JSON del documento tributario electrónico.",
        "",
        *([CONTINGENCY_NOTE, ""] if content.contingency else []),
        *(f"{label}: {value}" for label, value in facts),
        "",
        reply,
    ]
    if content.privacy_notice:
        lines += [
            "",
            "—",
            content.privacy_notice.title,
            content.privacy_notice.body,
        ]
    text = "\n".join(lines) + "\n"

    e = html.escape
    rows = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#555'>{e(label)}</td>"
        f"<td style='padding:4px 0'><strong>{e(value)}</strong></td></tr>"
        for label, value in facts
    )
    banner = (
        f"<p style='padding:8px 12px;background:#fff4e5;border:1px solid #f0b46c;"
        f"color:#8a4b00'><strong>{e(SIMULATED_MARK)}</strong>: documento de prueba, no fue "
        "enviado a Hacienda.</p>"
        if content.simulated
        else ""
    )
    notice = (
        f"<hr><p style='font-size:12px;color:#666'><strong>{e(content.privacy_notice.title)}"
        f"</strong></p><p style='font-size:12px;color:#666;white-space:pre-wrap'>"
        f"{e(content.privacy_notice.body)}</p>"
        if content.privacy_notice
        else ""
    )
    contingency = f"<p><em>{e(CONTINGENCY_NOTE)}</em></p>" if content.contingency else ""
    body_html = (
        "<div style='font-family:Arial,sans-serif;font-size:14px;color:#222'>"
        f"<p>Estimado/a {e(content.customer_name)}:</p>{banner}"
        f"<p>{e(content.company_name)} le envía su {e(name.lower())} electrónica. Adjuntamos el "
        "PDF y el archivo JSON del documento tributario electrónico.</p>"
        f"{contingency}<table>{rows}</table><p>{e(reply)}</p>{notice}</div>"
    )
    return ComposedEmail(
        subject=subject,
        text=text,
        html=body_html,
        pdf_filename=f"{content.control_number}.pdf",
        json_filename=f"{content.control_number}.json",
    )


@dataclass(frozen=True, slots=True)
class InvalidationEmailContent:
    """Aviso al cliente de una invalidación aceptada (bloque V4b)."""

    company_name: str
    document_type: str
    control_number: str
    generation_code: str
    invalidated_at: datetime
    customer_name: str
    simulated: bool
    reason: str | None
    replacement_control_number: str | None = None
    reply_to: str | None = None
    privacy_notice: PrivacyNoticeText | None = None


def compose_invalidation(content: InvalidationEmailContent) -> ComposedEmail:
    name = DOCUMENT_NAMES.get(content.document_type, "Documento tributario electrónico")
    subject = f"Anulación de {name.lower()} {content.control_number} — {content.company_name}"
    if content.simulated:
        subject = f"[{SIMULATED_MARK}] {subject}"
    summary = (
        f"{content.company_name} le informa que anuló su {name.lower()} electrónica número de "
        f"control {content.control_number} ante el Ministerio de Hacienda el "
        f"{_day(content.invalidated_at)}. Ese documento ya no tiene validez."
    )
    replacement = (
        f"La sustituye el documento {content.replacement_control_number}, que recibirá por "
        "separado."
        if content.replacement_control_number
        else None
    )
    facts = [
        ("Documento anulado", content.control_number),
        ("Código de generación", content.generation_code.upper()),
        ("Fecha de anulación", _day(content.invalidated_at)),
        *([("Motivo", content.reason)] if content.reason and not replacement else []),
    ]
    reply = (
        f"Si tiene dudas, responda a este correo ({content.reply_to})."
        if content.reply_to
        else "Si tiene dudas, comuníquese con nosotros."
    )
    lines = [f"Estimado/a {content.customer_name}:", ""]
    if content.simulated:
        lines += [f"*** {SIMULATED_MARK}: aviso de prueba, no se envió a Hacienda. ***", ""]
    lines += [summary, ""]
    if replacement:
        lines += [replacement, ""]
    lines += [
        *(f"{label}: {value}" for label, value in facts),
        "",
        "Adjuntamos el comprobante del evento de invalidación.",
        "",
        reply,
    ]
    if content.privacy_notice:
        lines += ["", "—", content.privacy_notice.title, content.privacy_notice.body]
    e = html.escape
    rows = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#555'>{e(label)}</td>"
        f"<td style='padding:4px 0'><strong>{e(value)}</strong></td></tr>"
        for label, value in facts
    )
    banner = (
        f"<p style='padding:8px 12px;background:#fff4e5;border:1px solid #f0b46c;"
        f"color:#8a4b00'><strong>{e(SIMULATED_MARK)}</strong>: aviso de prueba, no se envió a "
        "Hacienda.</p>"
        if content.simulated
        else ""
    )
    notice = (
        f"<hr><p style='font-size:12px;color:#666'><strong>{e(content.privacy_notice.title)}"
        f"</strong></p><p style='font-size:12px;color:#666;white-space:pre-wrap'>"
        f"{e(content.privacy_notice.body)}</p>"
        if content.privacy_notice
        else ""
    )
    body_html = (
        "<div style='font-family:Arial,sans-serif;font-size:14px;color:#222'>"
        f"<p>Estimado/a {e(content.customer_name)}:</p>{banner}<p>{e(summary)}</p>"
        f"{f'<p>{e(replacement)}</p>' if replacement else ''}<table>{rows}</table>"
        "<p>Adjuntamos el comprobante del evento de invalidación.</p>"
        f"<p>{e(reply)}</p>{notice}</div>"
    )
    return ComposedEmail(
        subject=subject,
        text="\n".join(lines) + "\n",
        html=body_html,
        pdf_filename=f"anulacion-{content.control_number}.pdf",
        json_filename=f"anulacion-{content.control_number}.json",
    )


def require_sendable(status: str) -> None:
    """Se envía un documento emitido, simulado o generado en contingencia (V4a)."""

    if status not in ("issued", "simulated", "contingency"):
        raise _rule(
            "Solo se envía por correo un documento emitido.", "sales_invoice_email_not_issued"
        )
