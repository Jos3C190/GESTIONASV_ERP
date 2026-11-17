"""Puerto del SMTP propio de la empresa (bloque V3c)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.domain.entities.company_email import EmailSettings, EmailSettingsInput


@dataclass(frozen=True, slots=True)
class StoredEmailSettings:
    settings: EmailSettings
    password_encrypted: bytes | None


class CompanyEmailRepository(Protocol):
    async def get(self, company_id: uuid.UUID) -> StoredEmailSettings | None: ...

    async def save(
        self,
        company_id: uuid.UUID,
        values: EmailSettingsInput,
        password_encrypted: bytes | None,
        *,
        keep_password: bool,
        actor_id: uuid.UUID,
    ) -> EmailSettings:
        """Guarda la configuración. Con ``keep_password`` conserva la contraseña guardada."""
        ...

    async def delete(self, company_id: uuid.UUID) -> bool: ...

    async def record_test(self, company_id: uuid.UUID, ok: bool, error: str | None) -> None: ...
