"""Contingencia de facturación por establecimiento (bloque V4a).

El servicio DTE abre la ventana solo cuando Hacienda no responde; el operador la activa a mano ante
una falla que el servicio no ve (corte de energía o de internet en la tienda). Al cerrarla, el
servicio informa el Evento de Contingencia con el responsable registrado y transmite los
documentos. Antes de cada acción el ERP registra a la empresa en el servicio con su modo, sus
credenciales y su responsable, igual que al emitir.
"""

from __future__ import annotations

import uuid

from app.application.fiscal.hacienda_credentials import decrypt_credentials
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domain.entities.fiscal import dte_nit
from app.domain.entities.fiscal_contingency import (
    ContingencyOverview,
    ContingencyResponsible,
    ContingencyWindow,
    validate_activation,
    validate_responsible,
)
from app.domain.entities.sales_fiscal_document import (
    INVOICEABLE_DOCUMENTS,
    FiscalMode,
    fiscal_mode,
)
from app.domain.ports.contingency_repository import ContingencyResponsibleRepository
from app.domain.ports.dte_service import DteService, DteServiceError, IssuerCredentials
from app.domain.ports.fiscal_repository import FiscalRepository
from app.domain.ports.hacienda_credentials_repository import HaciendaCredentialsRepository

_SERVICE_MISSING = "La facturación electrónica no está configurada en este servidor."


def _translate(error: DteServiceError) -> Exception:
    """Errores del servicio en el idioma y los códigos del ERP."""

    if error.code == "CONTINGENCY_ALREADY_ACTIVE":
        return ConflictError(
            "Ese establecimiento ya está en contingencia.", code="sales_contingency_already_active"
        )
    if error.code == "CONTINGENCY_NOT_FOUND":
        return NotFoundError("Contingencia no encontrada.", code="sales_contingency_not_found")
    if error.code == "CONTINGENCY_STILL_ACTIVE":
        return BusinessRuleError(
            "La contingencia sigue activa: ciérrala primero.", code="sales_contingency_active"
        )
    if error.code == "CONTINGENCY_RESPONSIBLE_REQUIRED":
        return BusinessRuleError(
            "Registra al responsable de contingencias para informar el evento.",
            code="sales_contingency_responsible_required",
        )
    if error.transient:
        return BusinessRuleError(
            "El servicio de facturación no responde. Intenta de nuevo en unos minutos.",
            code="sales_invoice_service_unreachable",
        )
    return BusinessRuleError(error.message, code="sales_contingency_rejected")


class ContingencyUseCases:
    def __init__(
        self,
        fiscal: FiscalRepository,
        responsibles: ContingencyResponsibleRepository,
        credentials: HaciendaCredentialsRepository,
        dte: DteService | None,
    ) -> None:
        self._fiscal = fiscal
        self._responsibles = responsibles
        self._credentials = credentials
        self._dte = dte

    def _service(self) -> DteService:
        if self._dte is None:
            raise BusinessRuleError(_SERVICE_MISSING, code="sales_invoice_service_unavailable")
        return self._dte

    async def _nit(self, company_id: uuid.UUID) -> str:
        identity = await self._fiscal.company_identity(company_id)
        nit = dte_nit(identity.nit) if identity else None
        if nit is None:
            raise BusinessRuleError(
                "Completa el NIT de la empresa en su ficha.", code="sales_contingency_nit_missing"
            )
        return nit

    async def _register(self, company_id: uuid.UUID) -> str:
        """Registra a la empresa en el servicio con su modo, credenciales y responsable."""

        nit = await self._nit(company_id)
        identity = await self._fiscal.company_identity(company_id)
        profile = await self._fiscal.get_profile(company_id)
        mode = fiscal_mode(profile.operating_mode)
        credentials: IssuerCredentials | None = None
        if mode is not FiscalMode.SIMULATED:
            stored = await self._credentials.get(company_id)
            if stored is None:
                raise BusinessRuleError(
                    "La empresa no tiene credenciales de Hacienda. Cárgalas en Configuración "
                    "fiscal → Hacienda.",
                    code="hacienda_credentials_missing",
                )
            credentials = decrypt_credentials(stored)
        enabled = sorted(
            item.document_type
            for item in await self._fiscal.list_document_types(company_id)
            if item.is_enabled and item.document_type in INVOICEABLE_DOCUMENTS
        )
        try:
            await self._service().register_issuer(
                nit,
                name=identity.name if identity else nit,
                mode=mode.value,
                document_types=enabled,
                credentials=credentials,
                responsible=await self._responsibles.get(company_id),
            )
        except DteServiceError as error:
            raise _translate(error) from error
        return nit

    async def overview(self, company_id: uuid.UUID) -> ContingencyOverview:
        nit = await self._nit(company_id)
        try:
            return await self._service().contingencies(nit)
        except DteServiceError as error:
            raise _translate(error) from error

    async def establishment_codes(self, company_id: uuid.UUID) -> dict[str, str]:
        """Código del establecimiento → nombre de su sucursal, para mostrar las ventanas."""

        return {
            item.code: item.branch_name
            for item in await self._fiscal.list_establishments(company_id)
        }

    async def activate(
        self,
        company_id: uuid.UUID,
        *,
        establishment_id: uuid.UUID,
        contingency_type: int,
        reason: str | None,
    ) -> ContingencyWindow:
        text = validate_activation(contingency_type, reason)
        establishment = await self._fiscal.get_establishment(company_id, establishment_id)
        if establishment is None or not establishment.is_active:
            raise NotFoundError(
                "Establecimiento no encontrado.", code="sales_contingency_establishment_not_found"
            )
        nit = await self._register(company_id)
        try:
            return await self._service().activate_contingency(
                nit,
                establishment_code=establishment.code,
                contingency_type=contingency_type,
                reason=text,
            )
        except DteServiceError as error:
            raise _translate(error) from error

    async def close(self, company_id: uuid.UUID, window_id: int) -> ContingencyWindow:
        nit = await self._register(company_id)
        try:
            return await self._service().close_contingency(nit, window_id)
        except DteServiceError as error:
            raise _translate(error) from error

    async def send_event(self, company_id: uuid.UUID, window_id: int) -> ContingencyWindow:
        nit = await self._register(company_id)
        try:
            return await self._service().send_contingency_event(nit, window_id)
        except DteServiceError as error:
            raise _translate(error) from error

    async def responsible(self, company_id: uuid.UUID) -> ContingencyResponsible | None:
        return await self._responsibles.get(company_id)

    async def save_responsible(
        self,
        company_id: uuid.UUID,
        *,
        name: str,
        document_type: str,
        document_number: str,
        actor_id: uuid.UUID,
    ) -> tuple[ContingencyResponsible | None, ContingencyResponsible]:
        clean = validate_responsible(name, document_type, document_number)
        before = await self._responsibles.get(company_id)
        saved = await self._responsibles.save(company_id, clean, actor_id)
        return before, saved
