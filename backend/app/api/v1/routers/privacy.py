"""Protección de datos personales: aviso, consentimientos, solicitudes ARCO-POL y vulneraciones."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.company_access import request_company_id
from app.api.v1.deps import (
    CurrentUser,
    get_audit_service,
    get_privacy_use_cases,
    require_any_permission,
    require_permission,
)
from app.api.v1.schemas.privacy import (
    AnonymizeIn,
    ConsentIn,
    ConsentOut,
    ConsentRevokeIn,
    IncidentIn,
    IncidentOut,
    NoticeElementOut,
    NoticeIn,
    NoticeOut,
    NoticeTemplateOut,
    RequestActionIn,
    RequestAssigneeIn,
    RequestIn,
    RequestOut,
    UserOptionOut,
)
from app.application.audit.audit_service import AuditService
from app.application.privacy import PrivacyUseCases
from app.application.privacy.use_cases import today_in_el_salvador
from app.domain.entities.privacy import NOTICE_ELEMENTS
from app.domain.entities.privacy_records import (
    Consent,
    Incident,
    IncidentDraft,
    PrivacyNotice,
    RequestDraft,
    SubjectRequest,
)

router = APIRouter(tags=["privacy"])

UseCases = Annotated[PrivacyUseCases, Depends(get_privacy_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
_READ = [Depends(require_permission("privacy:read"))]
_MANAGE = [Depends(require_permission("privacy:manage"))]


def _notice_out(item: PrivacyNotice) -> NoticeOut:
    return NoticeOut(
        id=item.id,
        version=item.version,
        title=item.title,
        body=item.body,
        covered_elements=list(item.covered_elements),
        published_at=item.published_at,
        published_by_name=item.published_by_name,
    )


def _consent_out(item: Consent) -> ConsentOut:
    return ConsentOut(**asdict(item))


def _request_out(item: SubjectRequest) -> RequestOut:
    state = item.state
    return RequestOut(
        id=item.id,
        code=item.code,
        customer_id=item.customer_id,
        customer_name=item.customer_name,
        requester_name=item.requester_name,
        requester_document=item.requester_document,
        response_channel=item.response_channel,
        right_type=item.right_type,
        description=item.description,
        status=state.status,
        received_on=state.received_on,
        due_on=state.due_on,
        effective_due_on=state.effective_due_on,
        correction_due_on=state.correction_due_on,
        extended_due_on=state.extended_due_on,
        extension_reason=item.extension_reason,
        overdue=item.overdue(today_in_el_salvador()),
        assignee_id=item.assignee_id,
        assignee_name=item.assignee_name,
        resolution=item.resolution,
        closed_at=item.closed_at,
        created_at=item.created_at,
    )


def _incident_out(item: Incident) -> IncidentOut:
    return IncidentOut(**asdict(item), notification_deadline=item.notification_deadline)


def _incident_draft(body: IncidentIn) -> IncidentDraft:
    return IncidentDraft(**body.model_dump())


async def _record(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    company_id: uuid.UUID,
    resource_type: str,
    resource_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=company_id,
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=before,
        after_state=after,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


# --- aviso de privacidad ---
@router.get(
    "/privacy/notice",
    response_model=NoticeOut | None,
    summary="Aviso de privacidad vigente",
    dependencies=[Depends(require_any_permission("privacy:read", "sales_customers:read"))],
)
async def current_notice(request: Request, use_cases: UseCases) -> NoticeOut | None:
    notice = await use_cases.current_notice(request_company_id(request))
    return _notice_out(notice) if notice else None


@router.get(
    "/privacy/notices",
    response_model=list[NoticeOut],
    summary="Historial de versiones del aviso",
    dependencies=_READ,
)
async def list_notices(request: Request, use_cases: UseCases) -> list[NoticeOut]:
    return [_notice_out(n) for n in await use_cases.list_notices(request_company_id(request))]


@router.get(
    "/privacy/notice-template",
    response_model=NoticeTemplateOut,
    summary="Plantilla del aviso con los datos de la empresa",
    dependencies=_MANAGE,
)
async def notice_template(request: Request, use_cases: UseCases) -> NoticeTemplateOut:
    return NoticeTemplateOut(
        title="Aviso de privacidad",
        body=await use_cases.notice_template(request_company_id(request)),
        elements=[NoticeElementOut(key=k, description=v) for k, v in NOTICE_ELEMENTS.items()],
    )


@router.post(
    "/privacy/notices",
    response_model=NoticeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Publicar una versión nueva del aviso",
    dependencies=_MANAGE,
)
async def publish_notice(
    body: NoticeIn, request: Request, current: CurrentUser, use_cases: UseCases, audit: Audit
) -> NoticeOut:
    company_id = request_company_id(request)
    notice = _notice_out(
        await use_cases.publish_notice(
            company_id,
            title=body.title,
            body=body.body,
            covered=body.covered_elements,
            actor_id=current.id,
        )
    )
    await _record(
        audit,
        request,
        action="CREATE",
        actor=current.id,
        company_id=company_id,
        resource_type="privacy_notice",
        resource_id=str(notice.id),
        after=notice.model_dump(mode="json"),
    )
    return notice


# --- consentimientos ---
@router.get(
    "/customers/{customer_id}/consents",
    response_model=list[ConsentOut],
    summary="Consentimientos del cliente",
    dependencies=[Depends(require_permission("sales_customers:read"))],
)
async def list_consents(
    customer_id: uuid.UUID, request: Request, use_cases: UseCases
) -> list[ConsentOut]:
    items = await use_cases.list_consents(request_company_id(request), customer_id)
    return [_consent_out(c) for c in items]


@router.post(
    "/customers/{customer_id}/consents",
    response_model=ConsentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un consentimiento",
    dependencies=[Depends(require_permission("sales_customers:manage"))],
)
async def grant_consent(
    customer_id: uuid.UUID,
    body: ConsentIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> ConsentOut:
    company_id = request_company_id(request)
    consent = _consent_out(
        await use_cases.grant_consent(
            company_id,
            customer_id,
            purpose=body.purpose,
            channel=body.channel,
            notes=body.notes,
            actor_id=current.id,
        )
    )
    await _record(
        audit,
        request,
        action="CREATE",
        actor=current.id,
        company_id=company_id,
        resource_type="customer_consent",
        resource_id=str(consent.id),
        after=consent.model_dump(mode="json"),
    )
    return consent


@router.post(
    "/customers/{customer_id}/consents/{consent_id}/revoke",
    response_model=ConsentOut,
    summary="Revocar un consentimiento",
    dependencies=[Depends(require_permission("sales_customers:manage"))],
)
async def revoke_consent(
    customer_id: uuid.UUID,
    consent_id: uuid.UUID,
    body: ConsentRevokeIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> ConsentOut:
    company_id = request_company_id(request)
    before, after = await use_cases.revoke_consent(
        company_id, customer_id, consent_id, channel=body.channel, actor_id=current.id
    )
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        company_id=company_id,
        resource_type="customer_consent",
        resource_id=str(consent_id),
        before=_consent_out(before).model_dump(mode="json"),
        after=_consent_out(after).model_dump(mode="json"),
    )
    return _consent_out(after)


# --- solicitudes ARCO-POL ---
@router.get(
    "/privacy/requests",
    response_model=list[RequestOut],
    summary="Solicitudes de titulares",
    dependencies=_READ,
)
async def list_requests(
    request: Request,
    use_cases: UseCases,
    scope: Annotated[str, Query(pattern="^(open|closed|all)$")] = "open",
) -> list[RequestOut]:
    items = await use_cases.list_requests(request_company_id(request), scope)
    return [_request_out(r) for r in items]


@router.get(
    "/privacy/assignee-options",
    response_model=list[UserOptionOut],
    summary="Usuarios que pueden atender solicitudes",
    dependencies=_MANAGE,
)
async def assignee_options(request: Request, use_cases: UseCases) -> list[UserOptionOut]:
    items = await use_cases.user_options(request_company_id(request))
    return [UserOptionOut(id=u.id, name=u.name) for u in items]


@router.post(
    "/privacy/requests",
    response_model=RequestOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una solicitud de titular",
    dependencies=_MANAGE,
)
async def create_request(
    body: RequestIn, request: Request, current: CurrentUser, use_cases: UseCases, audit: Audit
) -> RequestOut:
    company_id = request_company_id(request)
    created = _request_out(
        await use_cases.create_request(company_id, RequestDraft(**body.model_dump()), current.id)
    )
    await _record(
        audit,
        request,
        action="CREATE",
        actor=current.id,
        company_id=company_id,
        resource_type="data_subject_request",
        resource_id=str(created.id),
        after=created.model_dump(mode="json"),
    )
    return created


@router.get(
    "/privacy/requests/{request_id}",
    response_model=RequestOut,
    summary="Detalle de una solicitud",
    dependencies=_READ,
)
async def get_request(request_id: uuid.UUID, request: Request, use_cases: UseCases) -> RequestOut:
    return _request_out(await use_cases.get_request(request_company_id(request), request_id))


@router.post(
    "/privacy/requests/{request_id}/actions",
    response_model=RequestOut,
    summary="Avanzar una solicitud (iniciar, prevenir, prorrogar, resolver, denegar…)",
    dependencies=_MANAGE,
)
async def act_on_request(
    request_id: uuid.UUID,
    body: RequestActionIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> RequestOut:
    company_id = request_company_id(request)
    before = _request_out(await use_cases.get_request(company_id, request_id))
    after = _request_out(
        await use_cases.act_on_request(
            company_id,
            request_id,
            action=body.action,
            text=body.text,
            extension_reason=body.extension_reason,
            actor_id=current.id,
        )
    )
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        company_id=company_id,
        resource_type="data_subject_request",
        resource_id=str(request_id),
        before=before.model_dump(mode="json"),
        after=after.model_dump(mode="json"),
    )
    return after


@router.put(
    "/privacy/requests/{request_id}/assignee",
    response_model=RequestOut,
    summary="Asignar el responsable de la solicitud",
    dependencies=_MANAGE,
)
async def assign_request(
    request_id: uuid.UUID,
    body: RequestAssigneeIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> RequestOut:
    company_id = request_company_id(request)
    after = _request_out(await use_cases.assign_request(company_id, request_id, body.assignee_id))
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        company_id=company_id,
        resource_type="data_subject_request",
        resource_id=str(request_id),
        after=after.model_dump(mode="json"),
    )
    return after


# --- datos de un cliente ---
@router.get(
    "/privacy/customers/{customer_id}/export",
    summary="Exportar los datos personales del cliente (acceso y portabilidad)",
    dependencies=_MANAGE,
)
async def export_customer(
    customer_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> dict[str, Any]:
    company_id = request_company_id(request)
    data = await use_cases.export_customer(company_id, customer_id)
    await _record(
        audit,
        request,
        action="EXPORT",
        actor=current.id,
        company_id=company_id,
        resource_type="sales_customer",
        resource_id=str(customer_id),
    )
    return data


@router.post(
    "/privacy/customers/{customer_id}/anonymize",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Anonimizar al cliente por cancelación u olvido",
    dependencies=[Depends(require_permission("privacy:erase"))],
)
async def anonymize_customer(
    customer_id: uuid.UUID,
    body: AnonymizeIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> None:
    company_id = request_company_id(request)
    source = await use_cases.anonymize_customer(
        company_id, customer_id, request_id=body.request_id, actor_id=current.id
    )
    await _record(
        audit,
        request,
        action="ANONYMIZE",
        actor=current.id,
        company_id=company_id,
        resource_type="sales_customer",
        resource_id=str(customer_id),
        after={"request_id": str(source.id), "request_code": source.code},
    )


# --- vulneraciones ---
@router.get(
    "/privacy/incidents",
    response_model=list[IncidentOut],
    summary="Vulneraciones de seguridad de datos",
    dependencies=_READ,
)
async def list_incidents(request: Request, use_cases: UseCases) -> list[IncidentOut]:
    return [_incident_out(i) for i in await use_cases.list_incidents(request_company_id(request))]


@router.post(
    "/privacy/incidents",
    response_model=IncidentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una vulneración",
    dependencies=_MANAGE,
)
async def create_incident(
    body: IncidentIn, request: Request, current: CurrentUser, use_cases: UseCases, audit: Audit
) -> IncidentOut:
    company_id = request_company_id(request)
    created = _incident_out(
        await use_cases.create_incident(company_id, _incident_draft(body), current.id)
    )
    await _record(
        audit,
        request,
        action="CREATE",
        actor=current.id,
        company_id=company_id,
        resource_type="personal_data_incident",
        resource_id=str(created.id),
        after=created.model_dump(mode="json"),
    )
    return created


@router.put(
    "/privacy/incidents/{incident_id}",
    response_model=IncidentOut,
    summary="Actualizar una vulneración y sus notificaciones",
    dependencies=_MANAGE,
)
async def update_incident(
    incident_id: uuid.UUID,
    body: IncidentIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> IncidentOut:
    company_id = request_company_id(request)
    before = _incident_out(await use_cases.get_incident(company_id, incident_id))
    after = _incident_out(
        await use_cases.update_incident(company_id, incident_id, _incident_draft(body))
    )
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        company_id=company_id,
        resource_type="personal_data_incident",
        resource_id=str(incident_id),
        before=before.model_dump(mode="json"),
        after=after.model_dump(mode="json"),
    )
    return after


@router.post(
    "/privacy/incidents/{incident_id}/close",
    response_model=IncidentOut,
    summary="Cerrar una vulneración",
    dependencies=_MANAGE,
)
async def close_incident(
    incident_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> IncidentOut:
    company_id = request_company_id(request)
    closed = _incident_out(await use_cases.close_incident(company_id, incident_id, current.id))
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        company_id=company_id,
        resource_type="personal_data_incident",
        resource_id=str(incident_id),
        after=closed.model_dump(mode="json"),
    )
    return closed
