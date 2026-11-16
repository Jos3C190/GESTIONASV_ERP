"""SQLAlchemy implementation of the personal data protection repository."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.privacy import (
    Channel,
    ConsentPurpose,
    RequestState,
    RequestStatus,
    RightType,
    Transition,
)
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
from app.infrastructure.models.employee import Employee
from app.infrastructure.models.organization import Company, UserCompany
from app.infrastructure.models.privacy import (
    CustomerConsentModel,
    DataSubjectRequestModel,
    PersonalDataIncidentModel,
    PrivacyNoticeModel,
)
from app.infrastructure.models.sales import (
    SaleModel,
    SalesCustomerDeliveryAddressModel,
    SalesCustomerModel,
    SalesQuotationModel,
)
from app.infrastructure.models.user import User

ANONYMIZED_NAME = "Titular anonimizado"


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: object) -> object:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


class SqlAlchemyPrivacyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _names(self, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        ids = {i for i in user_ids if i is not None}
        if not ids:
            return {}
        rows = await self._session.execute(
            select(User.id, User.username, Employee.first_name, Employee.last_name)
            .outerjoin(Employee, (Employee.user_id == User.id) & Employee.deleted_at.is_(None))
            .where(User.id.in_(ids))
        )
        names: dict[uuid.UUID, str] = {}
        for user_id, username, first, last in rows.tuples().all():
            full = f"{first or ''} {last or ''}".strip()
            names.setdefault(user_id, full or username)
        return names

    async def _next_code(self, model: Any, company_id: uuid.UUID, prefix: str) -> str:
        codes = (
            await self._session.execute(select(model.code).where(model.company_id == company_id))
        ).scalars()
        pattern = re.compile(rf"^{prefix}-(\d+)$")
        numbers = [int(m.group(1)) for code in codes if (m := pattern.match(code))]
        return f"{prefix}-{max(numbers, default=0) + 1:05d}"

    # --- notice ---
    async def company_contact(self, company_id: uuid.UUID) -> CompanyContact | None:
        company = await self._session.get(Company, company_id)
        if company is None:
            return None
        return CompanyContact(company.name, company.address, company.email, company.phone)

    async def _notices(self, company_id: uuid.UUID, limit: int | None) -> list[PrivacyNotice]:
        stmt = (
            select(PrivacyNoticeModel)
            .where(PrivacyNoticeModel.company_id == company_id)
            .order_by(PrivacyNoticeModel.version.desc())
        )
        if limit:
            stmt = stmt.limit(limit)
        rows = list((await self._session.execute(stmt)).scalars().all())
        names = await self._names({r.published_by for r in rows if r.published_by})
        return [
            PrivacyNotice(
                id=r.id,
                version=r.version,
                title=r.title,
                body=r.body,
                covered_elements=tuple(r.covered_elements),
                published_at=r.published_at,
                published_by_name=names.get(r.published_by) if r.published_by else None,
            )
            for r in rows
        ]

    async def current_notice(self, company_id: uuid.UUID) -> PrivacyNotice | None:
        found = await self._notices(company_id, 1)
        return found[0] if found else None

    async def list_notices(self, company_id: uuid.UUID) -> list[PrivacyNotice]:
        return await self._notices(company_id, None)

    async def publish_notice(
        self,
        company_id: uuid.UUID,
        *,
        title: str,
        body: str,
        covered: tuple[str, ...],
        actor_id: uuid.UUID,
    ) -> PrivacyNotice:
        latest = await self._session.scalar(
            select(func.max(PrivacyNoticeModel.version)).where(
                PrivacyNoticeModel.company_id == company_id
            )
        )
        self._session.add(
            PrivacyNoticeModel(
                company_id=company_id,
                version=int(latest or 0) + 1,
                title=title.strip(),
                body=body.strip(),
                covered_elements=list(covered),
                published_by=actor_id,
            )
        )
        await self._session.flush()
        notice = await self.current_notice(company_id)
        assert notice is not None
        return notice

    # --- customers ---
    async def _customer(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> SalesCustomerModel | None:
        row: SalesCustomerModel | None = await self._session.scalar(
            select(SalesCustomerModel).where(
                SalesCustomerModel.company_id == company_id, SalesCustomerModel.id == customer_id
            )
        )
        return row

    async def customer_exists(self, company_id: uuid.UUID, customer_id: uuid.UUID) -> bool:
        return await self._customer(company_id, customer_id) is not None

    async def customer_is_anonymized(self, company_id: uuid.UUID, customer_id: uuid.UUID) -> bool:
        row = await self._customer(company_id, customer_id)
        return bool(row and row.anonymized_at)

    async def export_customer(
        self, company_id: uuid.UUID, customer_id: uuid.UUID
    ) -> dict[str, Any]:
        row = await self._customer(company_id, customer_id)
        assert row is not None
        fields = (
            "code", "customer_type", "name", "commercial_name", "person_type", "document_type",
            "document_number", "nrc", "activity_code", "address_line", "country_code", "phone",
            "email", "credit_days", "credit_limit", "is_active", "created_at", "updated_at",
            "anonymized_at",
        )  # fmt: skip
        addresses = (
            await self._session.execute(
                select(SalesCustomerDeliveryAddressModel).where(
                    SalesCustomerDeliveryAddressModel.company_id == company_id,
                    SalesCustomerDeliveryAddressModel.customer_id == customer_id,
                )
            )
        ).scalars()
        quotations = await self._session.execute(
            select(SalesQuotationModel.code, SalesQuotationModel.quotation_date).where(
                SalesQuotationModel.company_id == company_id,
                SalesQuotationModel.customer_id == customer_id,
            )
        )
        sales = await self._session.execute(
            select(SaleModel.code, SaleModel.created_at).where(
                SaleModel.company_id == company_id, SaleModel.customer_id == customer_id
            )
        )
        return {
            "customer": {name: _iso(getattr(row, name)) for name in fields},
            "delivery_addresses": [
                {
                    "label": a.label,
                    "address_line": a.address_line,
                    "contact_name": a.contact_name,
                    "phone": a.phone,
                    "latitude": _iso(a.latitude),
                    "longitude": _iso(a.longitude),
                }
                for a in addresses
            ],
            "consents": [
                {
                    "purpose": c.purpose.value,
                    "channel": c.channel.value,
                    "notice_version": c.notice_version,
                    "granted_at": _iso(c.granted_at),
                    "revoked_at": _iso(c.revoked_at),
                }
                for c in await self.list_consents(company_id, customer_id)
            ],
            "quotations": [
                {"code": code, "date": _iso(day)} for code, day in quotations.tuples().all()
            ],
            "sales": [{"code": code, "date": _iso(day)} for code, day in sales.tuples().all()],
        }

    async def anonymize_customer(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, actor_id: uuid.UUID, now: datetime
    ) -> None:
        row = await self._customer(company_id, customer_id)
        assert row is not None
        row.name = f"{ANONYMIZED_NAME} {row.code}"
        for column in (
            "commercial_name", "document_type", "document_number", "nrc", "activity_code",
            "department_id", "municipality_id", "district_id", "address_line", "phone", "email",
            "seller_employee_id",
        ):  # fmt: skip
            setattr(row, column, None)
        row.is_active = False
        row.anonymized_at = now
        row.updated_by_id = actor_id
        row.updated_at = now
        await self._session.execute(
            delete(SalesCustomerDeliveryAddressModel).where(
                SalesCustomerDeliveryAddressModel.company_id == company_id,
                SalesCustomerDeliveryAddressModel.customer_id == customer_id,
            )
        )
        await self._session.execute(
            update(CustomerConsentModel)
            .where(
                CustomerConsentModel.company_id == company_id,
                CustomerConsentModel.customer_id == customer_id,
                CustomerConsentModel.revoked_at.is_(None),
            )
            .values(revoked_at=now, revoked_by=actor_id, revocation_channel=Channel.WRITTEN.value)
        )
        await self._session.flush()

    # --- consents ---
    async def _consents(self, company_id: uuid.UUID, *conditions: Any) -> list[Consent]:
        rows = (
            await self._session.execute(
                select(CustomerConsentModel, PrivacyNoticeModel.version)
                .join(
                    PrivacyNoticeModel,
                    (PrivacyNoticeModel.company_id == CustomerConsentModel.company_id)
                    & (PrivacyNoticeModel.id == CustomerConsentModel.notice_id),
                )
                .where(CustomerConsentModel.company_id == company_id, *conditions)
                .order_by(CustomerConsentModel.granted_at.desc())
            )
        ).all()
        names = await self._names({c.granted_by for c, _ in rows if c.granted_by})
        return [
            Consent(
                id=c.id,
                customer_id=c.customer_id,
                purpose=ConsentPurpose(c.purpose),
                channel=Channel(c.channel),
                notice_version=version,
                granted_at=c.granted_at,
                granted_by_name=names.get(c.granted_by) if c.granted_by else None,
                revoked_at=c.revoked_at,
                revocation_channel=Channel(c.revocation_channel) if c.revocation_channel else None,
                notes=c.notes,
            )
            for c, version in rows
        ]

    async def list_consents(self, company_id: uuid.UUID, customer_id: uuid.UUID) -> list[Consent]:
        return await self._consents(company_id, CustomerConsentModel.customer_id == customer_id)

    async def active_consent(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, purpose: ConsentPurpose
    ) -> Consent | None:
        found = await self._consents(
            company_id,
            CustomerConsentModel.customer_id == customer_id,
            CustomerConsentModel.purpose == purpose.value,
            CustomerConsentModel.revoked_at.is_(None),
        )
        return found[0] if found else None

    async def get_consent(
        self, company_id: uuid.UUID, customer_id: uuid.UUID, consent_id: uuid.UUID
    ) -> Consent | None:
        found = await self._consents(
            company_id,
            CustomerConsentModel.customer_id == customer_id,
            CustomerConsentModel.id == consent_id,
        )
        return found[0] if found else None

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
    ) -> Consent:
        row = CustomerConsentModel(
            company_id=company_id,
            customer_id=customer_id,
            purpose=purpose.value,
            channel=channel.value,
            notice_id=notice_id,
            notes=notes,
            granted_by=actor_id,
        )
        self._session.add(row)
        await self._session.flush()
        consent = await self.get_consent(company_id, customer_id, row.id)
        assert consent is not None
        return consent

    async def revoke_consent(
        self,
        company_id: uuid.UUID,
        consent_id: uuid.UUID,
        *,
        channel: Channel,
        actor_id: uuid.UUID,
        now: datetime,
    ) -> None:
        await self._session.execute(
            update(CustomerConsentModel)
            .where(
                CustomerConsentModel.company_id == company_id, CustomerConsentModel.id == consent_id
            )
            .values(revoked_at=now, revoked_by=actor_id, revocation_channel=channel.value)
        )
        await self._session.flush()

    # --- requests ---
    async def _requests(self, company_id: uuid.UUID, *conditions: Any) -> list[SubjectRequest]:
        rows = (
            await self._session.execute(
                select(DataSubjectRequestModel, SalesCustomerModel.name)
                .outerjoin(
                    SalesCustomerModel,
                    (SalesCustomerModel.company_id == DataSubjectRequestModel.company_id)
                    & (SalesCustomerModel.id == DataSubjectRequestModel.customer_id),
                )
                .where(DataSubjectRequestModel.company_id == company_id, *conditions)
                .order_by(
                    DataSubjectRequestModel.received_on.desc(), DataSubjectRequestModel.code.desc()
                )
            )
        ).all()
        names = await self._names({r.assignee_id for r, _ in rows if r.assignee_id})
        return [
            SubjectRequest(
                id=r.id,
                code=r.code,
                customer_id=r.customer_id,
                customer_name=customer_name,
                requester_name=r.requester_name,
                requester_document=r.requester_document,
                response_channel=r.response_channel,
                right_type=RightType(r.right_type),
                description=r.description,
                state=RequestState(
                    status=RequestStatus(r.status),
                    received_on=r.received_on,
                    due_on=r.due_on,
                    correction_due_on=r.correction_due_on,
                    extended_due_on=r.extended_due_on,
                ),
                extension_reason=r.extension_reason,
                assignee_id=r.assignee_id,
                assignee_name=names.get(r.assignee_id) if r.assignee_id else None,
                resolution=r.resolution,
                closed_at=r.closed_at,
                created_at=r.created_at,
            )
            for r, customer_name in rows
        ]

    async def list_requests(
        self, company_id: uuid.UUID, statuses: frozenset[RequestStatus] | None
    ) -> list[SubjectRequest]:
        if statuses is None:
            return await self._requests(company_id)
        return await self._requests(
            company_id, DataSubjectRequestModel.status.in_([s.value for s in statuses])
        )

    async def get_request(
        self, company_id: uuid.UUID, request_id: uuid.UUID
    ) -> SubjectRequest | None:
        found = await self._requests(company_id, DataSubjectRequestModel.id == request_id)
        return found[0] if found else None

    async def create_request(
        self, company_id: uuid.UUID, draft: RequestDraft, due_on: date, actor_id: uuid.UUID
    ) -> SubjectRequest:
        row = DataSubjectRequestModel(
            company_id=company_id,
            code=await self._next_code(DataSubjectRequestModel, company_id, "SOL"),
            customer_id=draft.customer_id,
            requester_name=draft.requester_name,
            requester_document=draft.requester_document,
            response_channel=draft.response_channel,
            right_type=draft.right_type.value,
            description=draft.description,
            received_on=draft.received_on,
            due_on=due_on,
            assignee_id=draft.assignee_id,
            created_by=actor_id,
        )
        self._session.add(row)
        await self._session.flush()
        created = await self.get_request(company_id, row.id)
        assert created is not None
        return created

    async def apply_transition(
        self,
        company_id: uuid.UUID,
        request_id: uuid.UUID,
        transition: Transition,
        actor_id: uuid.UUID,
        now: datetime,
    ) -> SubjectRequest:
        values: dict[str, Any] = {
            "status": transition.status.value,
            "correction_due_on": transition.correction_due_on,
            "extended_due_on": transition.extended_due_on,
            "updated_at": now,
        }
        if transition.extension_reason is not None:
            values["extension_reason"] = transition.extension_reason
        if transition.closes:
            values.update(resolution=transition.resolution, closed_at=now, closed_by=actor_id)
        await self._session.execute(
            update(DataSubjectRequestModel)
            .where(
                DataSubjectRequestModel.company_id == company_id,
                DataSubjectRequestModel.id == request_id,
            )
            .values(**values)
        )
        await self._session.flush()
        updated = await self.get_request(company_id, request_id)
        assert updated is not None
        return updated

    async def set_assignee(
        self, company_id: uuid.UUID, request_id: uuid.UUID, assignee_id: uuid.UUID | None
    ) -> SubjectRequest:
        await self._session.execute(
            update(DataSubjectRequestModel)
            .where(
                DataSubjectRequestModel.company_id == company_id,
                DataSubjectRequestModel.id == request_id,
            )
            .values(assignee_id=assignee_id, updated_at=_now())
        )
        await self._session.flush()
        updated = await self.get_request(company_id, request_id)
        assert updated is not None
        return updated

    async def user_options(self, company_id: uuid.UUID) -> list[UserOption]:
        ids = (
            (
                await self._session.execute(
                    select(UserCompany.user_id)
                    .join(User, User.id == UserCompany.user_id)
                    .where(UserCompany.company_id == company_id, User.is_active.is_(True))
                )
            )
            .scalars()
            .all()
        )
        names = await self._names(set(ids))
        return sorted((UserOption(i, names.get(i, "")) for i in ids), key=lambda u: u.name)

    # --- incidents ---
    @staticmethod
    def _incident(row: PersonalDataIncidentModel) -> Incident:
        return Incident(
            id=row.id,
            code=row.code,
            discovered_at=row.discovered_at,
            occurred_at=row.occurred_at,
            description=row.description,
            data_categories=row.data_categories,
            affected_count=row.affected_count,
            measures=row.measures,
            notified_ace_at=row.notified_ace_at,
            ace_reference=row.ace_reference,
            notified_prosecutor_at=row.notified_prosecutor_at,
            prosecutor_reference=row.prosecutor_reference,
            notified_subjects_at=row.notified_subjects_at,
            subjects_reference=row.subjects_reference,
            subjects_not_required_reason=row.subjects_not_required_reason,
            status=row.status,
            closed_at=row.closed_at,
        )

    async def _incident_row(
        self, company_id: uuid.UUID, incident_id: uuid.UUID
    ) -> PersonalDataIncidentModel | None:
        row: PersonalDataIncidentModel | None = await self._session.scalar(
            select(PersonalDataIncidentModel).where(
                PersonalDataIncidentModel.company_id == company_id,
                PersonalDataIncidentModel.id == incident_id,
            )
        )
        return row

    async def list_incidents(self, company_id: uuid.UUID) -> list[Incident]:
        rows = (
            await self._session.execute(
                select(PersonalDataIncidentModel)
                .where(PersonalDataIncidentModel.company_id == company_id)
                .order_by(PersonalDataIncidentModel.discovered_at.desc())
            )
        ).scalars()
        return [self._incident(r) for r in rows]

    async def get_incident(self, company_id: uuid.UUID, incident_id: uuid.UUID) -> Incident | None:
        row = await self._incident_row(company_id, incident_id)
        return self._incident(row) if row is not None else None

    @staticmethod
    def _assign_incident(row: PersonalDataIncidentModel, draft: IncidentDraft) -> None:
        for name in (
            "discovered_at", "occurred_at", "description", "data_categories", "affected_count",
            "measures", "notified_ace_at", "ace_reference", "notified_prosecutor_at",
            "prosecutor_reference", "notified_subjects_at", "subjects_reference",
            "subjects_not_required_reason",
        ):  # fmt: skip
            setattr(row, name, getattr(draft, name))

    async def create_incident(
        self, company_id: uuid.UUID, draft: IncidentDraft, actor_id: uuid.UUID
    ) -> Incident:
        row = PersonalDataIncidentModel(
            company_id=company_id,
            code=await self._next_code(PersonalDataIncidentModel, company_id, "INC"),
            created_by=actor_id,
        )
        self._assign_incident(row, draft)
        self._session.add(row)
        await self._session.flush()
        return self._incident(row)

    async def update_incident(
        self, company_id: uuid.UUID, incident_id: uuid.UUID, draft: IncidentDraft
    ) -> Incident:
        row = await self._incident_row(company_id, incident_id)
        assert row is not None
        self._assign_incident(row, draft)
        row.updated_at = _now()
        await self._session.flush()
        return self._incident(row)

    async def close_incident(
        self, company_id: uuid.UUID, incident_id: uuid.UUID, actor_id: uuid.UUID, now: datetime
    ) -> Incident:
        row = await self._incident_row(company_id, incident_id)
        assert row is not None
        row.status = "closed"
        row.closed_at = now
        row.closed_by = actor_id
        row.updated_at = now
        await self._session.flush()
        return self._incident(row)
