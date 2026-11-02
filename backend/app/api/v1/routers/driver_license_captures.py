"""Guided capture of a driver's license. Everything needs ``drivers:documents``."""

from __future__ import annotations

import uuid
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
from app.api.v1.routers.drivers import _context, _view, scoped_driver
from app.api.v1.schemas.documents import DownloadUrlOut, InitiateDocumentOut
from app.api.v1.schemas.fleet import DriverOut
from app.api.v1.schemas.license_capture import (
    CaptureSideName,
    CaptureSideOut,
    CaptureUploadIn,
    LicenseCaptureCapabilitiesOut,
    LicenseCaptureOut,
    LicenseConfirmIn,
    LicenseFieldsPayload,
    LicenseIssueOut,
)
from app.application.audit.audit_service import AuditService
from app.application.documents import DocumentRecordService
from app.application.documents.service import DocumentService
from app.application.fleet.license_capture import (
    OVERRIDE_PERMISSION,
    CaptureView,
    LicenseCaptureService,
)
from app.application.fleet.license_rules import LicenseFields
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.domain.entities.document import DocumentAsset
from app.infrastructure.models.document_capture import DocumentCaptureModel
from app.infrastructure.models.fleet import DriverModel
from app.infrastructure.repositories.document_record_repository import (
    SqlAlchemyDocumentRecordRepository,
)
from app.infrastructure.vlm.job_queue import enqueue_capture, request_warmup, worker_available

router = APIRouter(tags=["driver-license-captures"])

Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
Documents = Annotated[DocumentService, Depends(get_document_service)]
Records = Annotated[DocumentRecordService, Depends(get_document_record_service)]
_MANAGE = [Depends(require_permission("drivers:documents"))]


def _enabled() -> None:
    if not settings.OBJECT_STORAGE_ENABLED:
        raise NotFoundError("Función no disponible.", code="license_capture_disabled")


def _service(
    session: SessionDep, documents: Documents, records: Records, audit: Audit
) -> LicenseCaptureService:
    return LicenseCaptureService(session, documents, records, audit)


Service = Annotated[LicenseCaptureService, Depends(_service)]


def _side(asset: DocumentAsset | None, capture: DocumentCaptureModel, side: str) -> CaptureSideOut:
    return CaptureSideOut(
        document_id=asset.id if asset else None,
        status=asset.status if asset else None,
        extracted=bool(capture.extracted and side in capture.extracted),
    )


async def _out(view: CaptureView) -> LicenseCaptureOut:
    values = view.values
    return LicenseCaptureOut(
        id=view.capture.id,
        status=view.capture.status,
        failure_code=view.capture.failure_code,
        extraction_available=await worker_available(),
        front=_side(view.front, view.capture, "front"),
        back=_side(view.back, view.capture, "back"),
        values=LicenseFieldsPayload(
            license_class=values.license_class,
            expires=values.expires,
            number=values.number,
            surnames=values.surnames,
            given_names=values.given_names,
            dui=values.dui,
            issued=values.issued,
            birth=values.birth,
            control_number=values.control_number,
        ),
        issues=[
            LicenseIssueOut(
                code=item.code, severity=item.severity, field=item.field, message=item.message
            )
            for item in view.issues
        ],
    )


async def _driver(
    driver_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: CheckPermissionUseCase,
    *,
    lock: bool = False,
) -> DriverModel:
    _enabled()
    _, scope, repo = await _context(request, session, current, checker)
    return await scoped_driver(repo, scope, driver_id, lock=lock)


@router.get(
    "/drivers/license-captures/capabilities",
    response_model=LicenseCaptureCapabilitiesOut,
    dependencies=_MANAGE,
)
async def capabilities() -> LicenseCaptureCapabilitiesOut:
    return LicenseCaptureCapabilitiesOut(
        enabled=settings.OBJECT_STORAGE_ENABLED,
        extraction_available=settings.OBJECT_STORAGE_ENABLED and await worker_available(),
    )


@router.post(
    "/drivers/{driver_id}/license-captures",
    response_model=LicenseCaptureOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=_MANAGE,
)
async def open_capture(
    driver_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> LicenseCaptureOut:
    driver = await _driver(driver_id, request, session, current, checker)
    capture = await service.open(driver, current.id)
    view = await service.view(driver, capture)
    await session.commit()
    # Abrir el asistente adelanta la carga del modelo: al tomar la foto ya suele estar listo.
    await request_warmup()
    return await _out(view)


@router.get(
    "/drivers/{driver_id}/license-captures/{capture_id}",
    response_model=LicenseCaptureOut,
    dependencies=_MANAGE,
)
async def get_capture(
    driver_id: uuid.UUID,
    capture_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> LicenseCaptureOut:
    driver = await _driver(driver_id, request, session, current, checker)
    capture = await service.get_capture(driver, capture_id)
    return await _out(await service.view(driver, capture))


@router.post(
    "/drivers/{driver_id}/license-captures/{capture_id}/sides/{side}/upload",
    response_model=InitiateDocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=_MANAGE,
)
async def initiate_side(
    driver_id: uuid.UUID,
    capture_id: uuid.UUID,
    side: CaptureSideName,
    body: CaptureUploadIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> InitiateDocumentOut:
    driver = await _driver(driver_id, request, session, current, checker)
    capture = await service.get_capture(driver, capture_id, lock=True)
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
    "/drivers/{driver_id}/license-captures/{capture_id}/sides/{side}/complete",
    response_model=LicenseCaptureOut,
    dependencies=_MANAGE,
)
async def complete_side(
    driver_id: uuid.UUID,
    capture_id: uuid.UUID,
    side: CaptureSideName,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> LicenseCaptureOut:
    driver = await _driver(driver_id, request, session, current, checker)
    capture = await service.get_capture(driver, capture_id)
    queued = await service.complete_side(capture, side, current.id)
    view = await service.view(driver, capture)
    await session.commit()
    if queued:
        await enqueue_capture(capture.id)
    return await _out(view)


@router.post(
    "/drivers/{driver_id}/license-captures/{capture_id}/sides/{side}/preview-url",
    response_model=DownloadUrlOut,
    dependencies=_MANAGE,
)
async def preview_side(
    driver_id: uuid.UUID,
    capture_id: uuid.UUID,
    side: CaptureSideName,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
    documents: Documents,
) -> DownloadUrlOut:
    driver = await _driver(driver_id, request, session, current, checker)
    capture = await service.get_capture(driver, capture_id)
    document_id = capture.front_document_id if side == "front" else capture.back_document_id
    if document_id is None:
        raise NotFoundError("Foto no encontrada.", code="license_capture_side_missing")
    url, expires_at = await documents.preview_url(capture.company_id, document_id, current.id)
    return DownloadUrlOut(url=url, expires_at=expires_at)


@router.post(
    "/drivers/{driver_id}/license-captures/{capture_id}/check",
    response_model=list[LicenseIssueOut],
    dependencies=_MANAGE,
)
async def check_values(
    driver_id: uuid.UUID,
    capture_id: uuid.UUID,
    body: LicenseFieldsPayload,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> list[LicenseIssueOut]:
    """Run the rules over what the user typed, so confirming holds no surprises."""
    driver = await _driver(driver_id, request, session, current, checker)
    await service.get_capture(driver, capture_id)
    check = await service.check_values(driver, LicenseFields(**body.model_dump()))
    return [
        LicenseIssueOut(
            code=item.code, severity=item.severity, field=item.field, message=item.message
        )
        for item in check.issues
    ]


@router.post(
    "/drivers/{driver_id}/license-captures/{capture_id}/confirm",
    response_model=DriverOut,
    dependencies=_MANAGE,
)
async def confirm_capture(
    driver_id: uuid.UUID,
    capture_id: uuid.UUID,
    body: LicenseConfirmIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> DriverOut:
    driver = await _driver(driver_id, request, session, current, checker, lock=True)
    capture = await service.get_capture(driver, capture_id, lock=True)
    company_id = capture.company_id
    await service.confirm(
        driver,
        capture,
        LicenseFields(**body.values.model_dump()),
        actor_id=current.id,
        acknowledged=set(body.acknowledged_warnings),
        override_reason=body.override_reason,
        can_override=(await checker.execute(current.id, company_id, OVERRIDE_PERMISSION)).allowed,
        can_update_driver=(await checker.execute(current.id, company_id, "drivers:update")).allowed,
    )
    _, _, repo = await _context(request, session, current, checker)
    return await _view(repo, company_id, driver.id)


@router.delete(
    "/drivers/{driver_id}/license-captures/{capture_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_MANAGE,
)
async def cancel_capture(
    driver_id: uuid.UUID,
    capture_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    service: Service,
) -> None:
    driver = await _driver(driver_id, request, session, current, checker)
    capture = await service.get_capture(driver, capture_id, lock=True)
    await service.cancel(capture, current.id)


@router.post(
    "/drivers/{driver_id}/license-back/preview-url",
    response_model=DownloadUrlOut,
    dependencies=_MANAGE,
)
async def preview_license_back(
    driver_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Checker,
    documents: Documents,
) -> DownloadUrlOut:
    """The back carries health data, so it is not reachable with ``drivers:read``."""
    driver = await _driver(driver_id, request, session, current, checker)
    repository = SqlAlchemyDocumentRecordRepository(session)
    categories = await repository.categories(driver.company_id, module="employees")
    category = next((item for item in categories if item.code == "driver_license_back"), None)
    current_back = (
        await repository.current_for_owner(
            driver.company_id,
            module="employees",
            owner_type="employee",
            owner_id=driver.employee_id,
            category_id=category.id,
        )
        if category
        else []
    )
    if not current_back:
        raise NotFoundError("Reverso no encontrado.", code="license_back_not_found")
    url, expires_at = await documents.preview_url(
        driver.company_id, current_back[0].document_id, current.id
    )
    return DownloadUrlOut(url=url, expires_at=expires_at)
