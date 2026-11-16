"""Puerto del repositorio de protección de datos. Toda operación recibe la empresa."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Protocol

from app.domain.entities.privacy import Channel, ConsentPurpose, RequestStatus, Transition
from app.domain.entities.privacy_records import (
    CompanyContact,
    Consent,
    Incident,
    IncidentDraft,
    PrivacyNotice,
    RequestDraft,
    SubjectRequest,
    UserOption,
)


class PrivacyRepository(Protocol):
    # --- notice ---
    async def company_contact(self, company_id: uuid.UUID) -> CompanyContact | None: ...

    async def current_notice(self, company_id: uuid.UUID) -> PrivacyNotice | None: ...

    async def list_notices(self, company_id: uuid.UUID) -> list[PrivacyNotice]: ...

    async def publish_notice(
        self,
        company_id: uuid.UUID,
        *,
        title: str,
        body: str,
        covered: tuple[str, ...],
        actor_id: uuid.UUID,
    ) -> PrivacyNotice: ...

    # --- customers ---
    async def customer_exists(self, company_id: uuid.UUID, customer_id: uuid.UUID) -> bool: ...

    async def customer_is_anonymized(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> bool: ...

    async def export_customer(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> dict[str, Any]: ...

    async def anonymize_customer(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, actor_id: uuid.UUID, now: datetime
    ) -> None: ...

    # --- consents ---
    async def list_consents(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> list[Consent]: ...

    async def active_consent(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, purpose: ConsentPurpose
    ) -> Consent | None: ...

    async def get_consent(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, consent_id: uuid.UUID
    ) -> Consent | None: ...

    async def grant_consent(
        self,
        company_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        purpose: ConsentPurpose,
        channel: Channel,
        notice_id: uuid.UUID,
        notes: str | None,
        actor_id: uuid.UUID,
    ) -> Consent: ...

    async def revoke_consent(
        self,
        company_id: uuid.UUID,
        consent_id: uuid.UUID,
        *,
        channel: Channel,
        actor_id: uuid.UUID,
        now: datetime,
    ) -> None: ...

    # --- requests ---
    async def list_requests(
        self, company_id: uuid.UUID, statuses: frozenset[RequestStatus] | None
    ) -> list[SubjectRequest]: ...

    async def get_request(
        self, company_id: uuid.UUID, request_id: uuid.UUID
    ) -> SubjectRequest | None: ...

    async def create_request(
        self, company_id: uuid.UUID, draft: RequestDraft, due_on: date, actor_id: uuid.UUID
    ) -> SubjectRequest: ...

    async def apply_transition(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
        transition: Transition,
        actor_id: uuid.UUID,
        now: datetime,
    ) -> SubjectRequest: ...

    async def set_assignee(
        self, company_id: uuid.UUID, request_id: uuid.UUID, assignee_id: uuid.UUID | None
    ) -> SubjectRequest: ...

    async def user_options(self, company_id: uuid.UUID) -> list[UserOption]: ...

    # --- incidents ---
    async def list_incidents(self, company_id: uuid.UUID) -> list[Incident]: ...

    async def get_incident(
        self, company_id: uuid.UUID, incident_id: uuid.UUID
    ) -> Incident | None: ...

    async def create_incident(
        self, company_id: uuid.UUID, draft: IncidentDraft, actor_id: uuid.UUID
    ) -> Incident: ...

    async def update_incident(
        self, company_id: uuid.UUID, incident_id: uuid.UUID, draft: IncidentDraft
    ) -> Incident: ...

    async def close_incident(
        self, company_id: uuid.UUID, incident_id: uuid.UUID, actor_id: uuid.UUID, now: datetime
    ) -> Incident: ...
