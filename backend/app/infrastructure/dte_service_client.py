"""Cliente HTTP del servicio DTE (``dte-service``), que vive en la red interna.

Cada solicitud declara la empresa en ``X-DTE-Issuer-NIT`` y viaja con la API key compartida.
La emisión lleva siempre la clave de idempotencia del documento fiscal: un reintento con la
misma clave devuelve el mismo DTE en lugar de crear otro.
"""

from __future__ import annotations

import base64
from datetime import date, datetime
from typing import Any

import httpx

from app.domain.entities.fiscal_contingency import (
    ContingencyDocuments,
    ContingencyOverview,
    ContingencyResponsible,
    ContingencyWindow,
)
from app.domain.ports.dte_service import (
    ConnectionCheck,
    DocumentState,
    DteServiceError,
    InvalidationRequest,
    InvalidationResult,
    InvalidationWindow,
    IssuerCredentials,
    IssueResult,
    ReturnEventResult,
)

_PATHS = {
    "01": "/api/dte/v2/factura",
    "03": "/api/dte/v2/ccf",
    "04": "/api/dte/v2/nota-remision",
    "05": "/api/dte/v2/nota-credito",
    "06": "/api/dte/v2/nota-debito",
}
#: Códigos del servicio que se resuelven solos al reintentar con la misma clave.
_TRANSIENT_CODES = frozenset({"IDEMPOTENCY_IN_PROGRESS", "ISSUER_MODE_UNAVAILABLE"})
#: Códigos 5xx que no se corrigen reintentando (configuración del firmador).
_PERMANENT_CODES = frozenset({"FIRMADOR_CONFIGURATION_ERROR"})
_SERVER_ERROR = 500
_NOT_FOUND = 404
_UNPROCESSABLE = 422


def _when(value: Any) -> datetime | None:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None


def _window(data: dict[str, Any]) -> ContingencyWindow:
    """Ventana tal como la resume el servicio (``resumenVentana``)."""

    documents = data.get("documentos") or {}
    event = data.get("evento") or {}
    deadlines = data.get("plazos") or {}
    started = _when(data.get("inicio"))
    assert started is not None
    return ContingencyWindow(
        id=int(data["id"]),
        establishment_code=data.get("establecimiento") or None,
        status=str(data.get("estado") or ""),
        contingency_type=int(data.get("tipoContingencia") or 0),
        reason=data.get("motivo") or None,
        forced=bool(data.get("forzada")),
        started_at=started,
        ended_at=_when(data.get("fin")),
        documents=ContingencyDocuments(
            total=int(documents.get("total") or 0),
            in_contingency=int(documents.get("enContingencia") or 0),
            pending_transmission=int(documents.get("pendientesDeTransmitir") or 0),
            transmitted=int(documents.get("transmitidos") or 0),
            rejected=int(documents.get("rechazados") or 0),
        ),
        event_status=event.get("estado") or None,
        event_seal=event.get("selloRecepcion") or None,
        event_sealed_at=_when(event.get("selloEn")),
        event_deadline=_when(deadlines.get("eventoLimite")),
        event_overdue=bool(deadlines.get("eventoVencido")),
        transmission_deadline=_when(deadlines.get("transmisionLimite")),
        transmission_overdue=bool(deadlines.get("transmisionVencida")),
        last_error=data.get("ultimoError") or None,
    )


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
        self,
        nit: str,
        *,
        name: str,
        mode: str,
        document_types: list[str],
        credentials: IssuerCredentials | None = None,
        responsible: ContingencyResponsible | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "nombre": name,
            "modo": mode,
            "tiposHabilitados": document_types,
            "activo": True,
        }
        if credentials is not None:
            body["credenciales"] = {
                "passwordApi": credentials.api_password,
                "passwordPri": credentials.private_key_password,
                "certificado": base64.b64encode(credentials.certificate).decode("ascii"),
            }
        if responsible is not None:
            # Sin el campo el servicio conserva el que tenga (V4a).
            body["responsable"] = {
                "nombre": responsible.name,
                "tipoDocumento": responsible.document_type,
                "numeroDocumento": responsible.document_number,
            }
        response = await self._send(None, "PUT", f"/api/emisores/{nit}", json=body)
        if response.is_error:
            raise self._error(response)

    async def test_issuer(self, nit: str) -> ConnectionCheck:
        response = await self._send(None, "POST", f"/api/emisores/{nit}/probar")
        if response.is_error:
            raise self._error(response)
        data = response.json()
        auth = data.get("autenticacion") or {}
        firma = data.get("firma") or {}
        return ConnectionCheck(
            ok=bool(data.get("ok")),
            authentication_ok=bool(auth.get("ok")),
            authentication_message=str(auth.get("mensaje") or ""),
            signature_ok=bool(firma.get("ok")),
            signature_message=str(firma.get("mensaje") or ""),
        )

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

    async def document_state(self, nit: str, generation_code: str) -> DocumentState:
        response = await self._send(nit, "GET", f"/api/dte/{generation_code}")
        if response.is_error:
            raise self._error(response)
        data = response.json()
        return DocumentState(
            status=str(data.get("estado") or ""), seal=data.get("sello_recepcion") or None
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

    # --- invalidación (V4b) ---

    async def invalidation_window(self, nit: str, generation_code: str) -> InvalidationWindow:
        response = await self._send(nit, "GET", f"/api/dte/{generation_code}/invalidacion")
        if response.is_error:
            raise self._error(response)
        deadline = response.json().get("plazo") or {}
        return InvalidationWindow(
            deadline=date.fromisoformat(str(deadline["limite"])),
            expired=bool(deadline.get("vencido")),
            estimated=bool(deadline.get("estimado")),
        )

    async def invalidate(
        self,
        nit: str,
        generation_code: str,
        *,
        idempotency_key: str,
        request: InvalidationRequest,
    ) -> InvalidationResult:
        def person(value: ContingencyResponsible) -> dict[str, str]:
            return {
                "nombre": value.name,
                "tipoDocumento": value.document_type,
                "numeroDocumento": value.document_number,
            }

        body: dict[str, Any] = {
            "motivo": {
                "tipoAnulacion": request.kind,
                "motivoAnulacion": request.reason,
                "responsable": person(request.responsible),
                "solicitante": person(request.requester),
            },
            "codigoGeneracionReemplazo": request.replacement_generation_code,
        }
        response = await self._send(
            nit,
            "POST",
            f"/api/dte/{generation_code}/anular",
            json=body,
            headers={"Idempotency-Key": idempotency_key},
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if (
            response.status_code == _UNPROCESSABLE
            and payload.get("code") == "INVALIDATION_REJECTED"
        ):
            hacienda = payload.get("respuestaHacienda") or payload.get("simulacion") or {}
            observations = hacienda.get("observaciones") or []
            message = " | ".join(
                str(item) for item in [hacienda.get("descripcionMsg"), *observations] if item
            )
            return InvalidationResult(
                accepted=False,
                event_generation_code=payload.get("codigoGeneracionEvento"),
                seal=None,
                message=message or str(payload.get("error") or "Hacienda rechazó la invalidación."),
                response=payload,
            )
        if response.is_error:
            raise self._error(response)
        if payload.get("estado") not in ("INVALIDADO", "SIMULADO_INVALIDADO"):
            raise DteServiceError(
                "El servicio no confirmó la invalidación todavía.",
                code="dte_invalidation_unconfirmed",
                transient=True,
            )
        return InvalidationResult(
            accepted=True,
            event_generation_code=payload.get("codigoGeneracionEvento"),
            seal=payload.get("selloRecepcionEvento") or payload.get("simulationMarkerEvento"),
            message=None,
            response=payload,
        )

    # --- evento de retorno (V4d2) ---

    def _return_result(
        self, response: httpx.Response, *, accepted_state: str, rejected_code: str
    ) -> ReturnEventResult:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.status_code == _UNPROCESSABLE and payload.get("code") == rejected_code:
            hacienda = payload.get("respuestaHacienda") or payload.get("simulacion") or {}
            if isinstance(hacienda, dict) and "respuesta" in hacienda:
                hacienda = hacienda.get("respuesta") or hacienda
            observations = hacienda.get("observaciones") or [] if isinstance(hacienda, dict) else []
            message = " | ".join(
                str(item)
                for item in [
                    hacienda.get("descripcionMsg") if isinstance(hacienda, dict) else None,
                    *observations,
                ]
                if item
            )
            return ReturnEventResult(
                accepted=False,
                generation_code=payload.get("codigoGeneracionEvento"),
                seal=None,
                simulated=payload.get("issuanceMode") == "SIMULATED",
                message=message or str(payload.get("error") or "Hacienda rechazó el evento."),
                response=payload,
            )
        if response.is_error:
            raise self._error(response)
        if payload.get("estado") not in (accepted_state, "SIMULADO"):
            raise DteServiceError(
                "El servicio no confirmó el evento todavía.",
                code="dte_return_unconfirmed",
                transient=True,
            )
        return ReturnEventResult(
            accepted=True,
            generation_code=payload.get("codigoGeneracionEvento"),
            seal=payload.get("selloRecepcionEvento") or payload.get("simulationMarkerEvento"),
            simulated=payload.get("issuanceMode") == "SIMULATED",
            message=None,
            response=payload,
        )

    async def issue_return(
        self, nit: str, invoice_generation_code: str, *, idempotency_key: str, body: dict[str, Any]
    ) -> ReturnEventResult:
        response = await self._send(
            nit,
            "POST",
            f"/api/dte/{invoice_generation_code}/retorno",
            json=body,
            headers={"Idempotency-Key": idempotency_key},
        )
        return self._return_result(
            response, accepted_state="ACEPTADO", rejected_code="RETURN_REJECTED"
        )

    async def annul_return(
        self,
        nit: str,
        return_generation_code: str,
        *,
        idempotency_key: str,
        request: InvalidationRequest,
    ) -> ReturnEventResult:
        def person(value: ContingencyResponsible) -> dict[str, str]:
            return {
                "nombre": value.name,
                "tipoDocumento": value.document_type,
                "numeroDocumento": value.document_number,
            }

        body = {
            "motivo": {
                "tipoAnulacion": 2,
                "motivoAnulacion": request.reason,
                "responsable": person(request.responsible),
                "solicitante": person(request.requester),
            }
        }
        response = await self._send(
            nit,
            "POST",
            f"/api/dte/eventos/{return_generation_code}/anular",
            json=body,
            headers={"Idempotency-Key": idempotency_key},
        )
        return self._return_result(
            response,
            accepted_state="RETORNO_INVALIDADO",
            rejected_code="RETURN_INVALIDATION_REJECTED",
        )

    async def event_json(self, nit: str, event_generation_code: str) -> dict[str, Any]:
        response = await self._send(nit, "GET", f"/api/dte/eventos/{event_generation_code}/json")
        if response.is_error:
            raise self._error(response)
        data: dict[str, Any] = response.json()
        return data

    async def invalidation_pdf(self, nit: str, event_generation_code: str) -> bytes:
        response = await self._send(
            nit, "POST", f"/api/dte/eventos/{event_generation_code}/pdf/render", json={}
        )
        if response.is_error:
            raise self._error(response)
        return response.content

    # --- contingencia por establecimiento (V4a) ---

    async def contingencies(self, nit: str) -> ContingencyOverview:
        response = await self._send(None, "GET", f"/api/emisores/{nit}/contingencias")
        if response.status_code == _NOT_FOUND:
            # Aún no registrada: no tiene ventanas.
            return ContingencyOverview(windows=(), responsible_registered=False)
        if response.is_error:
            raise self._error(response)
        data = response.json()
        return ContingencyOverview(
            windows=tuple(_window(item) for item in data.get("ventanas") or []),
            responsible_registered=bool(data.get("responsableConfigurado")),
        )

    async def activate_contingency(
        self, nit: str, *, establishment_code: str, contingency_type: int, reason: str | None
    ) -> ContingencyWindow:
        response = await self._send(
            None,
            "POST",
            f"/api/emisores/{nit}/contingencias",
            json={
                "establecimiento": establishment_code,
                "tipoContingencia": contingency_type,
                "motivoContingencia": reason,
            },
        )
        if response.is_error:
            raise self._error(response)
        return _window(response.json())

    async def close_contingency(self, nit: str, window_id: int) -> ContingencyWindow:
        response = await self._send(
            None, "POST", f"/api/emisores/{nit}/contingencias/{window_id}/cerrar", json={}
        )
        if response.is_error:
            raise self._error(response)
        return _window(response.json())

    async def send_contingency_event(self, nit: str, window_id: int) -> ContingencyWindow:
        response = await self._send(
            None, "POST", f"/api/emisores/{nit}/contingencias/{window_id}/evento", json={}
        )
        if response.is_error:
            raise self._error(response)
        return _window(response.json())
