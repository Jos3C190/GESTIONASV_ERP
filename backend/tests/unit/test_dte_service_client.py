"""Cliente del servicio DTE: encabezados, rutas y clasificación de errores."""

from __future__ import annotations

import json

import httpx
import pytest
from app.domain.ports.dte_service import DteServiceError
from app.infrastructure.dte_service_client import HttpDteServiceClient

NIT = "06142803901121"


def _client(handler) -> HttpDteServiceClient:  # type: ignore[no-untyped-def]
    return HttpDteServiceClient(
        "http://dte-service:3000/", "llave", transport=httpx.MockTransport(handler)
    )


async def test_issue_sends_issuer_key_and_idempotency() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            201,
            json={
                "codigoGeneracion": "A1B2",
                "numeroControl": "DTE-01-M001P001-000000000000001",
                "estado": "SIMULADO",
            },
        )

    result = await _client(handler).issue(
        "01", nit=NIT, idempotency_key="erp-clave-1", body={"items": []}
    )
    assert result.status == "SIMULADO"
    assert result.generation_code == "A1B2"
    request = seen[0]
    assert request.url.path == "/api/dte/v2/factura"
    assert request.headers["Authorization"] == "Bearer llave"
    assert request.headers["X-DTE-Issuer-NIT"] == NIT
    assert request.headers["Idempotency-Key"] == "erp-clave-1"
    assert json.loads(request.content) == {"items": []}


async def test_register_issuer_uses_put_without_issuer_header() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"nit": NIT})

    await _client(handler).register_issuer(
        NIT, name="Lorena", mode="simulated", document_types=["01", "03"]
    )
    assert seen[0].method == "PUT"
    assert seen[0].url.path == f"/api/emisores/{NIT}"
    assert "X-DTE-Issuer-NIT" not in seen[0].headers
    assert json.loads(seen[0].content)["tiposHabilitados"] == ["01", "03"]


@pytest.mark.parametrize(
    ("status", "body", "code", "transient"),
    [
        (400, {"error": "Mal", "code": "INVALID_DTE_REQUEST"}, "INVALID_DTE_REQUEST", False),
        (
            409,
            {"error": "En curso", "code": "IDEMPOTENCY_IN_PROGRESS"},
            "IDEMPOTENCY_IN_PROGRESS",
            True,
        ),
        (503, {"error": "Caído"}, "dte_service_http_503", True),
        (
            502,
            {"error": "Firma", "code": "FIRMADOR_CONFIGURATION_ERROR", "codigoGeneracion": "X"},
            "FIRMADOR_CONFIGURATION_ERROR",
            False,
        ),
        (
            422,
            {"error": "Schema", "code": "DTE_SCHEMA_INVALID", "detalles": ["x"]},
            "DTE_SCHEMA_INVALID",
            False,
        ),
    ],
)
async def test_errors_are_classified(
    status: int, body: dict[str, object], code: str, transient: bool
) -> None:
    client = _client(lambda _request: httpx.Response(status, json=body))
    with pytest.raises(DteServiceError) as raised:
        await client.issue("03", nit=NIT, idempotency_key="erp-clave-2", body={})
    assert raised.value.code == code
    assert raised.value.transient is transient
    assert raised.value.status == status


async def test_network_failure_is_transient_and_unknown_document_is_not() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red", request=request)

    with pytest.raises(DteServiceError) as raised:
        await _client(handler).document_pdf(NIT, "A1B2")
    assert raised.value.transient is True
    assert raised.value.code == "dte_service_unreachable"
    with pytest.raises(DteServiceError) as unsupported:
        await _client(handler).issue("11", nit=NIT, idempotency_key="erp-clave-3", body={})
    assert unsupported.value.transient is False


async def test_downloads_json_and_pdf() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/json"):
            return httpx.Response(200, json={"identificacion": {"codigoGeneracion": "A1B2"}})
        return httpx.Response(200, content=b"%PDF-1.7", headers={"Content-Type": "application/pdf"})

    client = _client(handler)
    assert (await client.document_json(NIT, "A1B2"))["identificacion"]["codigoGeneracion"] == "A1B2"
    assert await client.document_pdf(NIT, "A1B2") == b"%PDF-1.7"
