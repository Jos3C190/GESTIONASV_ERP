"""SMTP propio de la empresa en PostgreSQL (bloque V3c)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.company_email import EmailSettings, EmailSettingsInput
from app.domain.ports.company_email_repository import StoredEmailSettings
from app.infrastructure.models.fiscal import CompanyEmailSettingsModel

_MAX_ERROR = 1000


def _entity(model: CompanyEmailSettingsModel) -> StoredEmailSettings:
    return StoredEmailSettings(
        settings=EmailSettings(
            host=model.host,
            port=model.port,
            security=model.security,
            username=model.username,
            has_password=model.password_encrypted is not None,
            from_address=model.from_address,
            from_name=model.from_name,
            is_enabled=model.is_enabled,
            last_test_at=model.last_test_at,
            last_test_ok=model.last_test_ok,
            last_test_error=model.last_test_error,
            updated_at=model.updated_at,
        ),
        password_encrypted=model.password_encrypted,
    )


class SqlAlchemyCompanyEmailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, company_id: uuid.UUID) -> StoredEmailSettings | None:
        model = await self._session.get(CompanyEmailSettingsModel, company_id)
        return _entity(model) if model is not None else None

    async def save(
        self,
        company_id: uuid.UUID,
        values: EmailSettingsInput,
        password_encrypted: bytes | None,
        *,
        keep_password: bool,
        actor_id: uuid.UUID,
    ) -> EmailSettings:
        columns = {
            "host": values.host,
            "port": values.port,
            "security": values.security,
            "username": values.username,
            "from_address": values.from_address,
            "from_name": values.from_name,
            "is_enabled": values.is_enabled,
            "updated_by": actor_id,
            "updated_at": func.now(),
            # Cambiar la conexión invalida la prueba anterior.
            "last_test_at": None,
            "last_test_ok": None,
            "last_test_error": None,
        }
        if not keep_password:
            columns["password_encrypted"] = password_encrypted
        statement = insert(CompanyEmailSettingsModel).values(
            company_id=company_id,
            password_encrypted=password_encrypted,
            **{key: value for key, value in columns.items() if key != "password_encrypted"},
        )
        await self._session.execute(
            statement.on_conflict_do_update(index_elements=["company_id"], set_=columns)
        )
        await self._session.flush()
        self._session.expire_all()
        stored = await self.get(company_id)
        assert stored is not None  # recién guardado
        return stored.settings

    async def delete(self, company_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            delete(CompanyEmailSettingsModel).where(
                CompanyEmailSettingsModel.company_id == company_id
            )
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]

    async def record_test(self, company_id: uuid.UUID, ok: bool, error: str | None) -> None:
        model = await self._session.scalar(
            select(CompanyEmailSettingsModel)
            .where(CompanyEmailSettingsModel.company_id == company_id)
            .with_for_update()
        )
        if model is None:
            return
        model.last_test_at = datetime.now(UTC)
        model.last_test_ok = ok
        model.last_test_error = None if ok else (error or "Error desconocido")[:_MAX_ERROR]
        await self._session.flush()
