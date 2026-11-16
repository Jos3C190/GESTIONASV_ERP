"""Modelos de lectura de protección de datos que comparten puerto, casos de uso y API."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from app.domain.entities.privacy import (
    Channel,
    ConsentPurpose,
    RequestState,
    RequestStatus,
    RightType,
    notification_deadline,
)


@dataclass(frozen=True, slots=True)
class CompanyContact:
    name: str
    address: str
    email: str | None
    phone: str | None


@dataclass(frozen=True, slots=True)
class PrivacyNotice:
    id: uuid.UUID
    version: int
    title: str
    body: str
    covered_elements: tuple[str, ...]
    published_at: datetime
    published_by_name: str | None


@dataclass(frozen=True, slots=True)
class Consent:
    id: uuid.UUID
    customer_id: uuid.UUID
    purpose: ConsentPurpose
    channel: Channel
    notice_version: int
    granted_at: datetime
    granted_by_name: str | None
    revoked_at: datetime | None
    revocation_channel: Channel | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class SubjectRequest:
    id: uuid.UUID
    code: str
    customer_id: uuid.UUID | None
    customer_name: str | None
    requester_name: str
    requester_document: str | None
    response_channel: str
    right_type: RightType
    description: str
    state: RequestState
    extension_reason: str | None
    assignee_id: uuid.UUID | None
    assignee_name: str | None
    resolution: str | None
    closed_at: datetime | None
    created_at: datetime

    @property
    def status(self) -> RequestStatus:
        return self.state.status

    def overdue(self, today: date) -> bool:
        return self.state.overdue(today)


@dataclass(frozen=True, slots=True)
class RequestDraft:
    customer_id: uuid.UUID | None
    requester_name: str
    requester_document: str | None
    response_channel: str
    right_type: RightType
    description: str
    received_on: date
    assignee_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class Incident:
    id: uuid.UUID
    code: str
    discovered_at: datetime
    occurred_at: datetime | None
    description: str
    data_categories: str
    affected_count: int | None
    measures: str | None
    notified_ace_at: datetime | None
    ace_reference: str | None
    notified_prosecutor_at: datetime | None
    prosecutor_reference: str | None
    notified_subjects_at: datetime | None
    subjects_reference: str | None
    subjects_not_required_reason: str | None
    status: str
    closed_at: datetime | None

    @property
    def notification_deadline(self) -> datetime:
        return notification_deadline(self.discovered_at)


@dataclass(frozen=True, slots=True)
class IncidentDraft:
    discovered_at: datetime
    occurred_at: datetime | None
    description: str
    data_categories: str
    affected_count: int | None
    measures: str | None
    notified_ace_at: datetime | None = None
    ace_reference: str | None = None
    notified_prosecutor_at: datetime | None = None
    prosecutor_reference: str | None = None
    notified_subjects_at: datetime | None = None
    subjects_reference: str | None = None
    subjects_not_required_reason: str | None = None


@dataclass(frozen=True, slots=True)
class UserOption:
    id: uuid.UUID
    name: str
