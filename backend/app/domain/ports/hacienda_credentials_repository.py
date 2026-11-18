"""Puerto de las credenciales de Hacienda de la empresa (bloque V3d)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.domain.entities.hacienda_credentials import HaciendaCredentials


@dataclass(frozen=True, slots=True)
class StoredHaciendaCredentials:
    credentials: HaciendaCredentials
    api_password_encrypted: bytes
    private_key_password_encrypted: bytes
    certificate_encrypted: bytes


@dataclass(frozen=True, slots=True)
class EncryptedHaciendaCredentials:
    api_password: bytes
    private_key_password: bytes
    certificate: bytes
    certificate_sha256: str
    certificate_nit: str


class HaciendaCredentialsRepository(Protocol):
    async def get(self, company_id: uuid.UUID) -> StoredHaciendaCredentials | None: ...

    async def save(
        self, company_id: uuid.UUID, values: EncryptedHaciendaCredentials, actor_id: uuid.UUID
    ) -> HaciendaCredentials:
        """Guarda y borra la última prueba: las credenciales nuevas no están probadas."""
        ...

    async def delete(self, company_id: uuid.UUID) -> bool: ...

    async def record_test(self, company_id: uuid.UUID, ok: bool, error: str | None) -> None: ...
