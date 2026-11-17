"""Cliente HTTP del servicio DTE (``dte-service``), que vive en la red interna.

Cada solicitud declara la empresa en ``X-DTE-Issuer-NIT`` y viaja con la API key compartida.
La emisión lleva siempre la clave de idempotencia del documento fiscal: un reintento con la
misma clave devuelve el mismo DTE en lugar de crear otro.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.domain.ports.dte_service import DteServiceError, IssueResult

_PATHS = {"01": "/api/dte/v2/factura", "03": "/api/dte/v2/ccf"}
#: Códigos del servicio que se resuelven solos al reintentar con la misma clave.
_TRANSIENT_CODES = frozenset({"IDEMPOTENCY_IN_PROGRESS", "ISSUER_MODE_UNAVAILABLE"})
#: Códigos 5xx que no se corrigen reintentando (configuración del firmador).
_PERMANENT_CODES = frozenset({"FIRMADOR_CONFIGURATION_ERROR"})
_SERVER_ERROR = 500


class HttpDteServiceClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_seconds: float = 30,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._transport = transport

    def _client(self, nit: str | None = None) -> httpx.AsyncClient:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if nit:
            headers["X-DTE-Issuer-NIT"] = nit
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
            transport=self._transport,
        )

    async def _send(self, nit: str | None, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            async with self._client(nit) as client:
                return await client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise DteServiceError(
                "No se pudo conectar con el servicio DTE.",
                code="dte_service_unreachable",
                transient=True,
            ) from exc

    @staticmethod
    def _error(response: httpx.Response) -> DteServiceError:
        try:
            body = response.json()
        except ValueError:
            body = {}
        code = str(body.get("code") or f"dte_service_http_{response.status_code}")
        message = str(body.get("error") or "El servicio DTE rechazó la solicitud.")
        detail = body.get("detalles") or body.get("detalle")
        if detail:
            message = f"{message}: {str(detail)[:500]}"
        transient = code not in _PERMANENT_CODES and (
            response.status_code >= _SERVER_ERROR or code in _TRANSIENT_CODES
        )
        return DteServiceError(message, code=code, transient=transient, status=response.status_code)

    async def register_issuer(
        self, nit: str, *, name: str, mode: str, document_types: list[str]
    ) -> None:
        response = await self._send(
            None,
            "PUT",
            f"/api/emisores/{nit}",
            json={
                "nombre": name,
                "modo": mode,
                "tiposHabilitados": document_types,
                "activo": True,
            },
        )
        if response.is_error:
            raise self._error(response)

    async def issue(
        self, document_type: str, *, nit: str, idempotency_key: str, body: dict[str, Any]
    ) -> IssueResult:
        path = _PATHS.get(document_type)
        if path is None:
            raise DteServiceError(
                "Tipo de documento sin ruta de emisión.",
                code="dte_document_unsupported",
                transient=False,
            )
        response = await self._send(
            nit, "POST", path, json=body, headers={"Idempotency-Key": idempotency_key}
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.is_error:
            # Si el servicio ya reservó la identidad (por ejemplo, falló la firma), reintentar
            # con la misma clave retoma ese mismo DTE.
            raise self._error(response)
        return IssueResult(
            status=str(payload.get("estado") or ""),
            generation_code=payload.get("codigoGeneracion"),
            control_number=payload.get("numeroControl"),
            seal=payload.get("selloRecepcion"),
            response=payload,
        )

    async def document_json(self, nit: str, generation_code: str) -> dict[str, Any]:
        response = await self._send(nit, "GET", f"/api/dte/{generation_code}/json")
        if response.is_error:
            raise self._error(response)
        data: dict[str, Any] = response.json()
        return data

    async def document_pdf(self, nit: str, generation_code: str) -> bytes:
        response = await self._send(nit, "GET", f"/api/dte/{generation_code}/pdf")
        if response.is_error:
            raise self._error(response)
        return response.content
