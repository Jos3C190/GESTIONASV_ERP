from __future__ import annotations

import pytest
from app.core.config import Settings
from app.infrastructure import observability
from app.infrastructure.observability import (
    initialize_observability,
    inject_trace_context,
    redact_value,
    sanitize_metric_attributes,
)
from opentelemetry import baggage, context


def test_disabled_observability_is_a_noop() -> None:
    config = Settings(_env_file=None, OBSERVABILITY_ENABLED=False)
    assert initialize_observability("test-service", config=config) is False


def test_redaction_masks_nested_secrets_document_paths_and_presigned_signatures() -> None:
    event = {
        "password": "sentinel-password",
        "nested": {"authorization": "Bearer sentinel-token"},
        "message": (
            "url=https://storage/file?X-Amz-Signature=sentinel-signature "
            "postgresql://erp:sentinel-database-password@db/erp "
            "companies/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/documents/"
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/private.pdf"
        ),
    }
    redacted = redact_value(event)
    assert redacted["password"] == "[REDACTED]"
    assert redacted["nested"]["authorization"] == "[REDACTED]"
    assert "sentinel" not in redacted["message"]
    assert "private.pdf" not in redacted["message"]
    assert "sentinel-database-password" not in redacted["message"]


def test_metric_attributes_drop_high_cardinality_and_sensitive_fields() -> None:
    cleaned = sanitize_metric_attributes(
        {
            "service": "rustfs",
            "operation": "head",
            "result": "ok",
            "company_id": "secret-company",
            "document_id": "secret-document",
            "trace_id": "secret-trace",
            "object_key": "private/path",
            "ip": "127.0.0.1",
            "component": "database",
        }
    )
    assert cleaned == {
        "service": "rustfs",
        "operation": "head",
        "result": "ok",
        "component": "database",
    }


def test_arq_trace_carrier_never_propagates_baggage() -> None:
    token = context.attach(baggage.set_baggage("company_id", "must-not-leave-process"))
    try:
        carrier = inject_trace_context()
    finally:
        context.detach(token)
    assert "baggage" not in carrier


def test_initialization_failure_is_non_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    def _failure(*_args: object, **_kwargs: object) -> bool:
        raise RuntimeError("exporter setup failed")

    monkeypatch.setattr(observability, "_initialize_observability_impl", _failure)
    assert observability.initialize_observability("test-service") is False
