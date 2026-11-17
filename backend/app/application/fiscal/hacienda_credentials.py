"""Credenciales de Hacienda de la empresa: leer, guardar, quitar y probar (bloque V3d)."""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.secret_encryption import decrypt_secret, encrypt_secret
from app.domain.entities.fiscal import OperatingMode, dte_nit
from app.domain.entities.hacienda_credentials import (
    HaciendaCredentials,
    inspect_certificate,
    require_certificate_matches,
    require_passwords,
)
from app.domain.entities.sales_fiscal_document import INVOICEABLE_DOCUMENTS, FiscalMode
from app.domain.ports.dte_service import DteService, DteServiceError, IssuerCredentials
from app.domain.ports.fiscal_repository import FiscalRepository
from app.domain.ports.hacienda_credentials_repository import (
    EncryptedHaciendaCredentials,
    HaciendaCredentialsRepository,
    StoredHaciendaCredentials,
)


@dataclass(frozen=True, slots=True)
class ConnectionResult:
    ok: bool
    authentication_ok: bool
    authentication_message: str
    signature_ok: bool
    signature_message: str


def decrypt_credentials(stored: StoredHaciendaCredentials) -> IssuerCredentials:
    """Las credenciales en claro, solo en memoria para entregarlas al servicio DTE."""

    return IssuerCredentials(
        api_password=decrypt_secret(stored.api_password_encrypted),
        private_key_password=decrypt_secret(stored.private_key_password_encrypted),
        certificate=base64.b64decode(decrypt_secret(stored.certificate_encrypted)),
    )


class HaciendaCredentialsUseCases:
    def __init__(
        self,
        repo: HaciendaCredentialsRepository,
        fiscal: FiscalRepository,
        dte: DteService | None,
    ) -> None:
        self._repo = repo
        self._fiscal = fiscal
        self._dte = dte

    async def get(self, company_id: uuid.UUID) -> HaciendaCredentials | None:
        stored = await self._repo.get(company_id)
        return stored.credentials if stored else None

    async def _company_nit(self, company_id: uuid.UUID) -> str | None:
        identity = await self._fiscal.company_identity(company_id)
        return dte_nit(identity.nit) if identity else None

    async def save(
        self,
        company_id: uuid.UUID,
        *,
        api_password: str | None,
        private_key_password: str | None,
        certificate: bytes | None,
        actor_id: uuid.UUID,
    ) -> tuple[HaciendaCredentials | None, HaciendaCredentials]:
        """Lo que se deja en blanco se conserva; todo se valida junto antes de cifrarlo."""

        before = await self._repo.get(company_id)
        current = decrypt_credentials(before) if before else None
        api = api_password or (current.api_password if current else None)
        private = private_key_password or (current.private_key_password if current else None)
        cert = certificate or (current.certificate if current else None)
        require_passwords(api, private)
        assert api  # validado arriba
        assert private
        info = inspect_certificate(cert or b"")
        require_certificate_matches(info, await self._company_nit(company_id), private)
        saved = await self._repo.save(
            company_id,
            EncryptedHaciendaCredentials(
                api_password=encrypt_secret(api),
                private_key_password=encrypt_secret(private),
                certificate=encrypt_secret(base64.b64encode(cert or b"").decode("ascii")),
                certificate_sha256=info.sha256,
                certificate_nit=info.nit,
            ),
            actor_id,
        )
        return (before.credentials if before else None), saved

    async def remove(self, company_id: uuid.UUID) -> bool:
        profile = await self._fiscal.get_profile(company_id)
        if profile.operating_mode != OperatingMode.SIMULATED:
            raise BusinessRuleError(
                "La empresa emite ante Hacienda. Pásala a modo simulado antes de quitar sus "
                "credenciales.",
                code="hacienda_credentials_in_use",
            )
        return await self._repo.delete(company_id)

    async def test(self, company_id: uuid.UUID) -> ConnectionResult:
        """Registra a la empresa en el servicio con sus credenciales y prueba la conexión."""

        stored = await self._repo.get(company_id)
        if stored is None:
            raise NotFoundError(
                "La empresa no tiene credenciales de Hacienda.",
                code="hacienda_credentials_not_found",
            )
        if self._dte is None:
            raise BusinessRuleError(
                "La facturación electrónica no está configurada en este servidor.",
                code="sales_invoice_service_unavailable",
            )
        identity = await self._fiscal.company_identity(company_id)
        profile = await self._fiscal.get_profile(company_id)
        # Mientras la empresa sigue en simulado se prueba contra el ambiente de pruebas.
        mode = (
            FiscalMode.PRODUCTION
            if profile.operating_mode == OperatingMode.PRODUCTION
            else FiscalMode.TEST
        )
        enabled = sorted(
            item.document_type
            for item in await self._fiscal.list_document_types(company_id)
            if item.is_enabled and item.document_type in INVOICEABLE_DOCUMENTS
        )
        try:
            await self._dte.register_issuer(
                stored.credentials.certificate_nit,
                name=identity.name if identity else stored.credentials.certificate_nit,
                mode=mode.value,
                document_types=enabled,
                credentials=decrypt_credentials(stored),
            )
            check = await self._dte.test_issuer(stored.credentials.certificate_nit)
        except DteServiceError as error:
            await self._repo.record_test(company_id, False, error.message)
            return ConnectionResult(False, False, error.message, False, error.message)
        problems = [
            message
            for ok, message in (
                (check.authentication_ok, check.authentication_message),
                (check.signature_ok, check.signature_message),
            )
            if not ok
        ]
        await self._repo.record_test(company_id, check.ok, "; ".join(problems) or None)
        return ConnectionResult(
            ok=check.ok,
            authentication_ok=check.authentication_ok,
            authentication_message=check.authentication_message,
            signature_ok=check.signature_ok,
            signature_message=check.signature_message,
        )
