"""V3c: correo del documento fiscal (destinatarios, asunto, cuerpo y marca de simulado)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_fiscal_email import (
    CONTINGENCY_NOTE,
    SIMULATED_MARK,
    FiscalEmailContent,
    InvalidationEmailContent,
    PrivacyNoticeText,
    compose,
    compose_invalidation,
    customer_recipients,
    normalize_recipients,
    require_sendable,
)

CONTENT = FiscalEmailContent(
    company_name="Panadería Lorena",
    document_type="01",
    control_number="DTE-01-M001P001-000000000000001",
    generation_code="a1b2c3d4-0000-4000-8000-000000000001",
    # 02:30 UTC del 18 es el 17 en El Salvador.
    issued_at=datetime(2026, 11, 18, 2, 30, tzinfo=UTC),
    total=Decimal("1250.00"),
    customer_name="María <Rivas> & Cía.",
    simulated=False,
    reply_to="dte@example.com",
    privacy_notice=PrivacyNoticeText("Aviso de privacidad", "Tratamos sus datos para facturar."),
)


def test_recipients_are_cleaned_deduplicated_and_limited() -> None:
    assert normalize_recipients([" Cliente@Example.com ", "cliente@example.com", "", "b@x.sv"]) == (
        "cliente@example.com",
        "b@x.sv",
    )
    cases = [
        ([], "sales_invoice_email_required"),
        (["  "], "sales_invoice_email_required"),
        (["sin-arroba"], "sales_invoice_email_invalid"),
        (["a@b"], "sales_invoice_email_invalid"),
        (["uno@x.sv, dos@x.sv"], "sales_invoice_email_invalid"),
        ([f"c{i}@x.sv" for i in range(6)], "sales_invoice_email_too_many"),
    ]
    for values, code in cases:
        with pytest.raises(BusinessRuleError) as raised:
            normalize_recipients(values)
        assert raised.value.code == code
    assert customer_recipients("Compras@Cliente.com") == ("compras@cliente.com",)
    assert customer_recipients(None) == ()
    assert customer_recipients("no es correo") == ()


def test_compose_with_facts_privacy_notice_and_escaped_html() -> None:
    email = compose(CONTENT)
    assert email.subject == "Factura DTE-01-M001P001-000000000000001 — Panadería Lorena"
    assert email.pdf_filename == "DTE-01-M001P001-000000000000001.pdf"
    assert email.json_filename == "DTE-01-M001P001-000000000000001.json"
    assert "Fecha de emisión: 17/11/2026" in email.text
    assert "Total: $1,250.00" in email.text
    assert "A1B2C3D4-0000-4000-8000-000000000001" in email.text
    assert "responda a este correo (dte@example.com)" in email.text
    assert "Aviso de privacidad" in email.text
    assert SIMULATED_MARK not in email.text
    assert "María &lt;Rivas&gt; &amp; Cía." in email.html
    assert "<Rivas>" not in email.html
    assert "Tratamos sus datos para facturar." in email.html


def test_simulated_documents_are_marked_and_ccf_is_named() -> None:
    email = compose(replace(CONTENT, simulated=True, document_type="03", privacy_notice=None))
    assert email.subject.startswith(f"[{SIMULATED_MARK}] Comprobante de crédito fiscal")
    assert SIMULATED_MARK in email.text
    assert SIMULATED_MARK in email.html
    assert "Aviso de privacidad" not in email.text
    no_reply = compose(replace(CONTENT, reply_to=None))
    assert "comuníquese con nosotros" in no_reply.text


def test_contingency_documents_say_they_will_be_transmitted_later() -> None:
    email = compose(replace(CONTENT, contingency=True))
    assert CONTINGENCY_NOTE in email.text
    assert "se generó en contingencia" in email.html
    assert CONTINGENCY_NOTE not in compose(CONTENT).text


def test_only_issued_documents_are_sent() -> None:
    require_sendable("issued")
    require_sendable("simulated")
    require_sendable("contingency")
    for status in ("pending", "rejected", "failed"):
        with pytest.raises(BusinessRuleError) as raised:
            require_sendable(status)
        assert raised.value.code == "sales_invoice_email_not_issued"


def test_invalidation_notice_names_the_document_and_its_replacement() -> None:
    content = InvalidationEmailContent(
        company_name="Panadería Lorena",
        document_type="03",
        control_number="DTE-03-M001P001-000000000000007",
        generation_code="a1b2c3d4-0000-4000-8000-000000000007",
        invalidated_at=datetime(2026, 11, 18, 2, 30, tzinfo=UTC),
        customer_name="Clínica San Rafael",
        simulated=False,
        reason="Rescindir la operación",
    )
    email = compose_invalidation(content)
    assert email.subject == (
        "Anulación de comprobante de crédito fiscal DTE-03-M001P001-000000000000007 — "
        "Panadería Lorena"
    )
    assert "17/11/2026" in email.text
    assert "Motivo: Rescindir la operación" in email.text
    replaced = compose_invalidation(
        replace(content, replacement_control_number="DTE-03-M001P001-000000000000008")
    )
    assert "La sustituye el documento DTE-03-M001P001-000000000000008" in replaced.text
    assert "Motivo:" not in replaced.text
    assert compose_invalidation(replace(content, simulated=True)).subject.startswith("[SIMULADO")
