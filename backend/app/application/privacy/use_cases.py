"""Casos de uso de protección de datos personales."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domain.entities.privacy import (
    OPEN_STATUSES,
    Channel,
    ConsentPurpose,
    IncidentNotifications,
    RequestAction,
    RequestStatus,
    apply_action,
    new_request_due,
    notice_template,
    require_erasure_request,
    require_incident_closable,
    require_notice_complete,
)
from app.domain.entities.privacy_records import (
    Consent,
    Incident,
    IncidentDraft,
    PrivacyNotice,
    RequestDraft,
    SubjectRequest,
    UserOption,
)
from app.domain.ports.privacy_repository import PrivacyRepository

EL_SALVADOR = ZoneInfo("America/El_Salvador")


def today_in_el_salvador() -> date:
    return datetime.now(EL_SALVADOR).date()


def _clean(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


class PrivacyUseCases:
    def __init__(self, repository: PrivacyRepository) -> None:
        self._repo = repository

    # --- notice ---
    async def current_notice(self, company_id: uuid.UUID) -> PrivacyNotice | None:
        return await self._repo.current_notice(company_id)

    async def list_notices(self, company_id: uuid.UUID) -> list[PrivacyNotice]:
        return await self._repo.list_notices(company_id)

    async def notice_template(self, company_id: uuid.UUID) -> str:
        contact = await self._repo.company_contact(company_id)
        if contact is None:
            raise NotFoundError("No se encontró la empresa.", code="privacy_company_not_found")
        return notice_template(
            company_name=contact.name,
            address=contact.address,
            email=contact.email,
            phone=contact.phone,
        )

    async def publish_notice(
        self,
        company_id: uuid.UUID,
        *,
        title: str,
        body: str,
        covered: list[str],
        actor_id: uuid.UUID,
    ) -> PrivacyNotice:
        elements = require_notice_complete(title, body, covered)
        return await self._repo.publish_notice(
            company_id, title=title, body=body, covered=elements, actor_id=actor_id
        )

    # --- customers ---
    async def _require_customer(self, company_id: uuid.UUID, customer_id: uuid.UUID) -> None:
        if not await self._repo.customer_exists(company_id, customer_id):
            raise NotFoundError("Cliente no encontrado.", code="sales_customer_not_found")

    async def export_customer(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> dict[str, Any]:
        await self._require_customer(company_id, customer_id)
        return await self._repo.export_customer(company_id, customer_id)

    async def anonymize_customer(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        request_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> SubjectRequest:
        await self._require_customer(company_id, customer_id)
        request = await self.get_request(company_id, request_id)
        if request.customer_id != customer_id:
            raise BusinessRuleError(
                "La solicitud no corresponde a ese cliente.",
                code="privacy_request_customer_mismatch",
            )
        require_erasure_request(request.right_type, request.status)
        if await self._repo.customer_is_anonymized(company_id, customer_id):
            raise ConflictError(
                "El cliente ya fue anonimizado.", code="privacy_customer_already_anonymized"
            )
        await self._repo.anonymize_customer(company_id, customer_id, actor_id, datetime.now(UTC))
        return request

    # --- consents ---
    async def list_consents(self, company_id: uuid.UUID, customer_id: uuid.UUID) -> list[Consent]:
        await self._require_customer(company_id, customer_id)
        return await self._repo.list_consents(company_id, customer_id)

    async def grant_consent(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        purpose: ConsentPurpose,
        channel: Channel,
        notes: str | None,
        actor_id: uuid.UUID,
    ) -> Consent:
        await self._require_customer(company_id, customer_id)
        if await self._repo.customer_is_anonymized(company_id, customer_id):
            raise BusinessRuleError(
                "El cliente fue anonimizado; no se registran consentimientos.",
                code="customer_anonymized_locked",
            )
        notice = await self._repo.current_notice(company_id)
        if notice is None:
            raise BusinessRuleError(
                "Publica el aviso de privacidad antes de registrar consentimientos: el titular "
                "debe conocerlo antes de aceptar.",
                code="privacy_notice_missing",
            )
        if await self._repo.active_consent(company_id, customer_id, purpose) is not None:
            raise ConflictError(
                "El cliente ya tiene ese consentimiento vigente.",
                code="privacy_consent_already_granted",
            )
        return await self._repo.grant_consent(
            company_id,
            customer_id,
            purpose=purpose,
            channel=channel,
            notice_id=notice.id,
            notes=_clean(notes),
            actor_id=actor_id,
        )

    async def revoke_consent(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        consent_id: uuid.UUID,
        *,
        channel: Channel,
        actor_id: uuid.UUID,
    ) -> tuple[Consent, Consent]:
        before = await self._repo.get_consent(company_id, customer_id, consent_id)
        if before is None:
            raise NotFoundError("Consentimiento no encontrado.", code="privacy_consent_not_found")
        if before.revoked_at is not None:
            raise ConflictError(
                "Ese consentimiento ya fue revocado.", code="privacy_consent_already_revoked"
            )
        await self._repo.revoke_consent(
            company_id, consent_id, channel=channel, actor_id=actor_id, now=datetime.now(UTC)
        )
        after = await self._repo.get_consent(company_id, customer_id, consent_id)
        assert after is not None
        return before, after

    # --- requests ---
    async def list_requests(self, company_id: uuid.UUID, scope: str) -> list[SubjectRequest]:
        if scope == "open":
            return await self._repo.list_requests(company_id, OPEN_STATUSES)
        if scope == "closed":
            closed = frozenset(set(RequestStatus) - set(OPEN_STATUSES))
            return await self._repo.list_requests(company_id, closed)
        return await self._repo.list_requests(company_id, None)

    async def get_request(self, company_id: uuid.UUID, request_id: uuid.UUID) -> SubjectRequest:
        request = await self._repo.get_request(company_id, request_id)
        if request is None:
            raise NotFoundError("Solicitud no encontrada.", code="privacy_request_not_found")
        return request

    async def _require_assignee(self, company_id: uuid.UUID, assignee_id: uuid.UUID | None) -> None:
        if assignee_id is None:
            return
        if assignee_id not in {u.id for u in await self._repo.user_options(company_id)}:
            raise NotFoundError(
                "Ese responsable no es un usuario activo de la empresa.",
                code="privacy_assignee_not_found",
            )

    async def create_request(
        self, company_id: uuid.UUID, draft: RequestDraft, actor_id: uuid.UUID
    ) -> SubjectRequest:
        if draft.customer_id is not None:
            await self._require_customer(company_id, draft.customer_id)
        await self._require_assignee(company_id, draft.assignee_id)
        if draft.received_on > today_in_el_salvador():
            raise BusinessRuleError(
                "La fecha de recepción no puede ser futura.", code="privacy_request_future_date"
            )
        draft = replace(
            draft,
            requester_name=draft.requester_name.strip(),
            requester_document=_clean(draft.requester_document),
            response_channel=draft.response_channel.strip(),
            description=draft.description.strip(),
        )
        return await self._repo.create_request(
            company_id, draft, new_request_due(draft.received_on), actor_id
        )

    async def act_on_request(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
        *,
        action: RequestAction,
        text: str | None,
        extension_reason: str | None,
        actor_id: uuid.UUID,
    ) -> SubjectRequest:
        request = await self.get_request(company_id, request_id)
        transition = apply_action(
            request.state,
            action,
            today=today_in_el_salvador(),
            text=text,
            extension_reason=extension_reason,
        )
        return await self._repo.apply_transition(
            company_id, request_id, transition, actor_id, datetime.now(UTC)
        )

    async def assign_request(
        self, company_id: uuid.UUID, request_id: uuid.UUID, assignee_id: uuid.UUID | None
    ) -> SubjectRequest:
        await self.get_request(company_id, request_id)
        await self._require_assignee(company_id, assignee_id)
        return await self._repo.set_assignee(company_id, request_id, assignee_id)

    async def user_options(self, company_id: uuid.UUID) -> list[UserOption]:
        return await self._repo.user_options(company_id)

    # --- incidents ---
    async def list_incidents(self, company_id: uuid.UUID) -> list[Incident]:
        return await self._repo.list_incidents(company_id)

    async def get_incident(self, company_id: uuid.UUID, incident_id: uuid.UUID) -> Incident:
        incident = await self._repo.get_incident(company_id, incident_id)
        if incident is None:
            raise NotFoundError("Vulneración no encontrada.", code="privacy_incident_not_found")
        return incident

    @staticmethod
    def _check_incident(draft: IncidentDraft) -> IncidentDraft:
        if len(draft.description.strip()) < 10:  # noqa: PLR2004
            raise BusinessRuleError(
                "Describe la vulneración (al menos 10 caracteres).",
                code="privacy_incident_description_required",
            )
        if not draft.data_categories.strip():
            raise BusinessRuleError(
                "Indica qué datos personales se vieron comprometidos.",
                code="privacy_incident_data_required",
            )
        if draft.occurred_at is not None and draft.occurred_at > draft.discovered_at:
            raise BusinessRuleError(
                "La vulneración no puede haber ocurrido después de conocerse.",
                code="privacy_incident_dates_invalid",
            )
        if draft.discovered_at > datetime.now(UTC):
            raise BusinessRuleError(
                "La fecha en que se conoció no puede ser futura.",
                code="privacy_incident_future_date",
            )
        return replace(
            draft,
            description=draft.description.strip(),
            data_categories=draft.data_categories.strip(),
            measures=_clean(draft.measures),
            ace_reference=_clean(draft.ace_reference),
            prosecutor_reference=_clean(draft.prosecutor_reference),
            subjects_reference=_clean(draft.subjects_reference),
            subjects_not_required_reason=_clean(draft.subjects_not_required_reason),
        )

    async def create_incident(
        self, company_id: uuid.UUID, draft: IncidentDraft, actor_id: uuid.UUID
    ) -> Incident:
        return await self._repo.create_incident(company_id, self._check_incident(draft), actor_id)

    async def update_incident(
        self, company_id: uuid.UUID, incident_id: uuid.UUID, draft: IncidentDraft
    ) -> Incident:
        current = await self.get_incident(company_id, incident_id)
        if current.status == "closed":
            raise BusinessRuleError(
                "La vulneración está cerrada; su registro ya no se modifica.",
                code="privacy_incident_closed",
            )
        return await self._repo.update_incident(
            company_id, incident_id, self._check_incident(draft)
        )

    async def close_incident(
        self, company_id: uuid.UUID, incident_id: uuid.UUID, actor_id: uuid.UUID
    ) -> Incident:
        current = await self.get_incident(company_id, incident_id)
        if current.status == "closed":
            raise ConflictError("La vulneración ya está cerrada.", code="privacy_incident_closed")
        require_incident_closable(
            IncidentNotifications(
                current.notified_ace_at,
                current.notified_prosecutor_at,
                current.notified_subjects_at,
                current.subjects_not_required_reason,
            )
        )
        return await self._repo.close_incident(company_id, incident_id, actor_id, datetime.now(UTC))
