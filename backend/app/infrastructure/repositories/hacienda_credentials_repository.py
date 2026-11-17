"""Credenciales de Hacienda de la empresa en PostgreSQL (bloque V3d)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.hacienda_credentials import HaciendaCredentials
from app.domain.ports.hacienda_credentials_repository import (
    EncryptedHaciendaCredentials,
    StoredHaciendaCredentials,
)
from app.infrastructure.models.fiscal import CompanyHaciendaCredentialsModel

_MAX_ERROR = 1000


def _entity(model: CompanyHaciendaCredentialsModel) -> StoredHaciendaCredentials:
    return StoredHaciendaCredentials(
        credentials=HaciendaCredentials(
            certificate_nit=model.certificate_nit,
            certificate_sha256=model.certificate_sha256,
            last_test_at=model.last_test_at,
            last_test_ok=model.last_test_ok,
            last_test_error=model.last_test_error,
            updated_at=model.updated_at,
        ),
        api_password_encrypted=model.api_password_encrypted,
        private_key_password_encrypted=model.private_key_password_encrypted,
        certificate_encrypted=model.certificate_encrypted,
    )


class SqlAlchemyHaciendaCredentialsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, company_id: uuid.UUID) -> StoredHaciendaCredentials | None:
        model = await self._session.get(CompanyHaciendaCredentialsModel, company_id)
        return _entity(model) if model is not None else None

    async def save(
        self, company_id: uuid.UUID, values: EncryptedHaciendaCredentials, actor_id: uuid.UUID
    ) -> HaciendaCredentials:
        columns = {
            "api_password_encrypted": values.api_password,
            "private_key_password_encrypted": values.private_key_password,
            "certificate_encrypted": values.certificate,
            "certificate_sha256": values.certificate_sha256,
            "certificate_nit": values.certificate_nit,
            "updated_by": actor_id,
            "last_test_at": None,
            "last_test_ok": None,
            "last_test_error": None,
        }
        statement = insert(CompanyHaciendaCredentialsModel).values(company_id=company_id, **columns)
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=["company_id"], set_={**columns, "updated_at": func.now()}
            )
        )
        await self._session.flush()
        self._session.expire_all()
        stored = await self.get(company_id)
        assert stored is not None  # recién guardado
        return stored.credentials

    async def delete(self, company_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            delete(CompanyHaciendaCredentialsModel).where(
                CompanyHaciendaCredentialsModel.company_id == company_id
            )
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]

    async def record_test(self, company_id: uuid.UUID, ok: bool, error: str | None) -> None:
        model = await self._session.scalar(
            select(CompanyHaciendaCredentialsModel)
            .where(CompanyHaciendaCredentialsModel.company_id == company_id)
            .with_for_update()
        )
        if model is None:
            return
        model.last_test_at = datetime.now(UTC)
        model.last_test_ok = ok
        model.last_test_error = None if ok else (error or "Error desconocido")[:_MAX_ERROR]
        await self._session.flush()
