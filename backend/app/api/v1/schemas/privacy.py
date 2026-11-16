"""DTOs de protección de datos personales."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities.privacy import (
    Channel,
    ConsentPurpose,
    RequestAction,
    RequestStatus,
    RightType,
)

_IN = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NoticeElementOut(BaseModel):
    key: str
    description: str


class NoticeOut(BaseModel):
    id: uuid.UUID
    version: int
    title: str
    body: str
    covered_elements: list[str]
    published_at: datetime
    published_by_name: str | None


class NoticeTemplateOut(BaseModel):
    title: str
    body: str
    elements: list[NoticeElementOut]


class NoticeIn(BaseModel):
    model_config = _IN

    title: str = Field(min_length=5, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    covered_elements: list[str] = Field(default_factory=list, max_length=20)


class ConsentOut(BaseModel):
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


class ConsentIn(BaseModel):
    model_config = _IN

    purpose: ConsentPurpose
    channel: Channel
    notes: str | None = Field(default=None, max_length=1000)


class ConsentRevokeIn(BaseModel):
    model_config = _IN

    channel: Channel


class RequestOut(BaseModel):
    id: uuid.UUID
    code: str
    customer_id: uuid.UUID | None
    customer_name: str | None
    requester_name: str
    requester_document: str | None
    response_channel: str
    right_type: RightType
    description: str
    status: RequestStatus
    received_on: date
    due_on: date
    effective_due_on: date
    correction_due_on: date | None
    extended_due_on: date | None
    extension_reason: str | None
    overdue: bool
    assignee_id: uuid.UUID | None
    assignee_name: str | None
    resolution: str | None
    closed_at: datetime | None
    created_at: datetime


class RequestIn(BaseModel):
    model_config = _IN

    customer_id: uuid.UUID | None = None
    requester_name: str = Field(min_length=3, max_length=200)
    requester_document: str | None = Field(default=None, max_length=30)
    response_channel: str = Field(min_length=3, max_length=200)
    right_type: RightType
    description: str = Field(min_length=5, max_length=5000)
    received_on: date
    assignee_id: uuid.UUID | None = None


class RequestActionIn(BaseModel):
    model_config = _IN

    action: RequestAction
    text: str | None = Field(default=None, max_length=5000)
    extension_reason: str | None = Field(default=None, max_length=2000)


class RequestAssigneeIn(BaseModel):
    model_config = _IN

    assignee_id: uuid.UUID | None


class UserOptionOut(BaseModel):
    id: uuid.UUID
    name: str


class AnonymizeIn(BaseModel):
    model_config = _IN

    request_id: uuid.UUID


class IncidentOut(BaseModel):
    id: uuid.UUID
    code: str
    discovered_at: datetime
    occurred_at: datetime | None
    notification_deadline: datetime
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


class IncidentIn(BaseModel):
    model_config = _IN

    discovered_at: datetime
    occurred_at: datetime | None = None
    description: str = Field(min_length=1, max_length=5000)
    data_categories: str = Field(min_length=1, max_length=2000)
    affected_count: int | None = Field(default=None, ge=0)
    measures: str | None = Field(default=None, max_length=5000)
    notified_ace_at: datetime | None = None
    ace_reference: str | None = Field(default=None, max_length=200)
    notified_prosecutor_at: datetime | None = None
    prosecutor_reference: str | None = Field(default=None, max_length=200)
    notified_subjects_at: datetime | None = None
    subjects_reference: str | None = Field(default=None, max_length=200)
    subjects_not_required_reason: str | None = Field(default=None, max_length=2000)
