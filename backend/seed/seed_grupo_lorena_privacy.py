"""Aviso de privacidad inicial de Grupo Lorena.

Publica la versión 1 con la plantilla de la Ley para la Protección de Datos Personales y los
datos de contacto de la empresa, para que la demostración pueda registrar consentimientos.
No se vuelve a publicar si la empresa ya tiene un aviso.
"""

from __future__ import annotations

from app.application.privacy import PrivacyUseCases
from app.domain.entities.privacy import NOTICE_ELEMENTS
from app.infrastructure.db.session import session_scope
from app.infrastructure.models.user import User
from app.infrastructure.repositories.privacy_repository import SqlAlchemyPrivacyRepository
from sqlalchemy import select

from seed.seed_grupo_lorena import COMPANY_ID, SUPER_ADMIN_USERNAME

NOTICE_TITLE = "Aviso de privacidad"


async def seed() -> bool:
    async with session_scope() as session:
        actor = await session.scalar(select(User.id).where(User.username == SUPER_ADMIN_USERNAME))
        if actor is None:
            print("[seed] Aviso de privacidad: falta el superadministrador; se reintenta después.")
            return False
        privacy = PrivacyUseCases(SqlAlchemyPrivacyRepository(session))
        if await privacy.current_notice(COMPANY_ID) is not None:
            return True
        body = await privacy.notice_template(COMPANY_ID)
        await privacy.publish_notice(
            COMPANY_ID,
            title=NOTICE_TITLE,
            body=body,
            covered=list(NOTICE_ELEMENTS),
            actor_id=actor,
        )
    return True
