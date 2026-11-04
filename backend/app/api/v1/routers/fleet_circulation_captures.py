"""Guided capture of a circulation card. Everything needs ``fleet_documents:upload``."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    get_document_record_service,
    get_document_service,
    require_permission,
)
from app.api.v1.routers.fleet import _context, _view, scoped_vehicle
from app.api.v1.schemas.circulation_capture import (
    CirculationCaptureOut,
    CirculationCheckOut,
    CirculationConfirmIn,
    CirculationConfirmOut,
    CirculationFieldsPayload,
)
from app.api.v1.schemas.documents import DownloadUrlOut, InitiateDocumentOut
from app.api.v1.schemas.license_capture import (
    CaptureSideName,
    CaptureSideOut,
    CaptureUploadIn,
    LicenseCaptureCapabilitiesOut,
    LicenseIssueOut,
)
from app.application.audit.audit_service import AuditService
from app.application.documents import DocumentRecordService
from app.application.documents.service import DocumentService
from app.application.fleet.circulation_capture import (
    CirculationCaptureService,
    CirculationCaptureView,
)
from app.application.fleet.circulation_rules import CirculationFields
from app.application.fleet.license_rules import LicenseIssue
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.domain.entities.document import DocumentAsset
from app.infrastructure.models.document_capture import DocumentCaptureModel
from app.infrastructure.models.fleet import FleetVehicleModel
from app.infrastructure.vlm.job_queue import enqueue_capture, request_warmup, worker_available

router = APIRouter(prefix="/fleet", tags=["fleet-circulation-captures"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
Documents = Annotated[DocumentService, Depends(get_document_service)]
Records = Annotated[DocumentRecordService, Depends(get_document_record_service)]
_MANAGE = [Depends(require_permission("fleet_documents:upload"))]
_BASE = "/vehicles/{vehicle_id}/circulation-captures"


def _enabled() -> None:
    if not settings.OBJECT_STORAGE_ENABLED:
        raise NotFoundError("Función no disponible.", code="circulation_capture_disabled")


def _service(
    session: SessionDep, documents: Documents, records: Records, audit: Audit
) -> CirculationCaptureService:
    return CirculationCaptureService(session, documents, records, audit)


Service = Annotated[CirculationCaptureService, Depends(_service)]


def _side(asset: DocumentAsset | None, capture: DocumentCaptureModel, side: str) -> CaptureSideOut:
    return CaptureSideOut(
        document_id=asset.id if asset else None,
        status=asset.status if asset else None,
        extracted=bool(capture.extracted and side in capture.extracted),
    )


def _issues(issues: tuple[LicenseIssue, ...]) -> list[LicenseIssueOut]:
    return [
        LicenseIssueOut(
            code=item.code, severity=item.severity, field=item.field, message=item.message
        )
        for item in issues
    ]


async def _out(view: CirculationCaptureView) -> CirculationCaptureOut:
    return CirculationCaptureOut(
        id=view.capture.id,
        status=view.capture.status,
        failure_code=view.capture.failure_code,
        extraction_available=await worker_available(),
        front=_side(view.front, view.capture, "front"),
        back=_side(view.back, view.capture, "back"),
        values=CirculationFieldsPayload(**asdict(view.values)),
        issues=_issues(view.issues),
        fills=list(view.fills),
    )


async def _vehicle(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    *,
    lock: bool = False,
) -> FleetVehicleModel:
    _enabled()
    _, scope, repo = await _context(request, session, current, checker)
    return await scoped_vehicle(repo, scope, vehicle_id, lock=lock)


@router.get(
    "/circulation-captures/capabilities",
    response_model=LicenseCaptureCapabilitiesOut,
    dependencies=_MANAGE,
)
async def capabilities() -> LicenseCaptureCapabilitiesOut:
    return LicenseCaptureCapabilitiesOut(
        enabled=settings.OBJECT_STORAGE_ENABLED,
        extraction_available=settings.OBJECT_STORAGE_ENABLED and await worker_available(),
    )


@router.post(
    _BASE,
    response_model=CirculationCaptureOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=_MANAGE,
)
async def open_capture(
    vehicle_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> CirculationCaptureOut:
    vehicle = await _vehicle(vehicle_id, request, session, current, checker)
    capture = await service.open(vehicle, current.id)
    view = await service.view(vehicle, capture)
    await session.commit()
    # Abrir el asistente adelanta la carga del modelo: al tomar la foto ya suele estar listo.
    await request_warmup()
    return await _out(view)


@router.get(
    f"{_BASE}/{{capture_id}}",
    response_model=CirculationCaptureOut,
    dependencies=_MANAGE,
)
async def get_capture(
    vehicle_id: uuid.UUID,
    capture_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> CirculationCaptureOut:
    vehicle = await _vehicle(vehicle_id, request, session, current, checker)
    capture = await service.get_capture(vehicle, capture_id)
    return await _out(await service.view(vehicle, capture))


@router.post(
    f"{_BASE}/{{capture_id}}/sides/{{side}}/upload",
    response_model=InitiateDocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=_MANAGE,
)
async def initiate_side(
    vehicle_id: uuid.UUID,
    capture_id: uuid.UUID,
    side: CaptureSideName,
    body: CaptureUploadIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> InitiateDocumentOut:
    vehicle = await _vehicle(vehicle_id, request, session, current, checker)
    capture = await service.get_capture(vehicle, capture_id, lock=True)
    ticket = await service.initiate_side(
        capture,
        side,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
        checksum_sha256=body.checksum_sha256,
        actor_id=current.id,
    )
    return InitiateDocumentOut(
        document_id=ticket.document.id,
        upload_url=ticket.upload_url,
        required_headers=ticket.required_headers,
        expires_at=ticket.expires_at,
    )


@router.post(
    f"{_BASE}/{{capture_id}}/sides/{{side}}/complete",
    response_model=CirculationCaptureOut,
    dependencies=_MANAGE,
)
async def complete_side(
    vehicle_id: uuid.UUID,
    capture_id: uuid.UUID,
    side: CaptureSideName,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> CirculationCaptureOut:
    vehicle = await _vehicle(vehicle_id, request, session, current, checker)
    capture = await service.get_capture(vehicle, capture_id)
    queued = await service.complete_side(capture, side, current.id)
    view = await service.view(vehicle, capture)
    await session.commit()
    if queued:
        await enqueue_capture(capture.id)
    return await _out(view)


@router.post(
    f"{_BASE}/{{capture_id}}/sides/{{side}}/preview-url",
    response_model=DownloadUrlOut,
    dependencies=_MANAGE,
)
async def preview_side(
    vehicle_id: uuid.UUID,
    capture_id: uuid.UUID,
    side: CaptureSideName,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
    documents: Documents,
) -> DownloadUrlOut:
    vehicle = await _vehicle(vehicle_id, request, session, current, checker)
    capture = await service.get_capture(vehicle, capture_id)
    document_id = capture.front_document_id if side == "front" else capture.back_document_id
    if document_id is None:
        raise NotFoundError("Foto no encontrada.", code="circulation_capture_side_missing")
    url, expires_at = await documents.preview_url(capture.company_id, document_id, current.id)
    return DownloadUrlOut(url=url, expires_at=expires_at)


@router.post(
    f"{_BASE}/{{capture_id}}/check",
    response_model=CirculationCheckOut,
    dependencies=_MANAGE,
)
async def check_values(
    vehicle_id: uuid.UUID,
    capture_id: uuid.UUID,
    body: CirculationFieldsPayload,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> CirculationCheckOut:
    """Run the rules over what the user typed, so confirming holds no surprises."""
    vehicle = await _vehicle(vehicle_id, request, session, current, checker)
    await service.get_capture(vehicle, capture_id)
    values = CirculationFields(**body.model_dump())
    return CirculationCheckOut(
        issues=_issues(service.check_values(vehicle, values).issues),
        fills=list(service.fills(vehicle, values)),
    )


@router.post(
    f"{_BASE}/{{capture_id}}/confirm",
    response_model=CirculationConfirmOut,
    dependencies=_MANAGE,
)
async def confirm_capture(
    vehicle_id: uuid.UUID,
    capture_id: uuid.UUID,
    body: CirculationConfirmIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> CirculationConfirmOut:
    vehicle = await _vehicle(vehicle_id, request, session, current, checker, lock=True)
    capture = await service.get_capture(vehicle, capture_id, lock=True)
    company_id = capture.company_id
    result = await service.confirm(
        vehicle,
        capture,
        CirculationFields(**body.values.model_dump()),
        actor_id=current.id,
        acknowledged=set(body.acknowledged_warnings),
        can_update_vehicle=(await checker.execute(current.id, company_id, "fleet:update")).allowed,
    )
    _, _, repo = await _context(request, session, current, checker)
    return CirculationConfirmOut(
        vehicle=await _view(repo, company_id, vehicle),
        filled_fields=list(result.filled),
        skipped_fields=list(result.skipped),
    )


@router.delete(
    f"{_BASE}/{{capture_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_MANAGE,
)
async def cancel_capture(
    vehicle_id: uuid.UUID,
    capture_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> None:
    vehicle = await _vehicle(vehicle_id, request, session, current, checker)
    capture = await service.get_capture(vehicle, capture_id, lock=True)
    await service.cancel(capture, current.id)
