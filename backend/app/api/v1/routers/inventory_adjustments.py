from __future__ import annotations

import uuid
from collections.abc import Awaitable
from datetime import UTC, date, datetime
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.v1.company_access import (
    effective_company_id,
    get_branch_context,
    resolve_branch_scope,
)
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    get_document_service,
    require_permission,
)
from app.api.v1.routers.inventory import InventoryBoundaryError
from app.api.v1.schemas.documents import DownloadUrlOut, InitiateDocumentOut
from app.api.v1.schemas.inventory_adjustment import (
    InventoryAdjustmentApplyIn,
    InventoryAdjustmentApproveIn,
    InventoryAdjustmentCancelIn,
    InventoryAdjustmentCorrectionIn,
    InventoryAdjustmentCreateIn,
    InventoryAdjustmentDocumentInitiateIn,
    InventoryAdjustmentOptions,
    InventoryAdjustmentOut,
    InventoryAdjustmentPage,
    InventoryAdjustmentUpdateIn,
)
from app.application.audit.audit_service import AuditService
from app.application.documents import DocumentService, InitiateDocumentInput
from app.application.inventory_adjustments import InventoryAdjustmentUseCases
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.core.exceptions import AuthorizationError
from app.domain.entities.inventory import InventoryOperationError
from app.domain.entities.inventory_adjustment import InventoryAdjustmentError
from app.infrastructure.models.inventory_adjustment import (
    InventoryAdjustmentDocumentModel,
    InventoryAdjustmentModel,
)
from app.infrastructure.models.inventory_transfer import InventoryTransferModel
from app.infrastructure.models.organization import Warehouse
from app.infrastructure.repositories.inventory_adjustment_repository import (
    SqlAlchemyInventoryAdjustmentRepository,
)

router = APIRouter(prefix="/inventory/adjustments", tags=["inventory adjustments"])
T = TypeVar("T")


def _redact_adjustment_costs(response: InventoryAdjustmentOut) -> InventoryAdjustmentOut:
    for line in response.lines:
        line["documented_unit_cost"] = None
        line["documented_total_cost"] = None
    return response


def _use_cases(session: SessionDep) -> InventoryAdjustmentUseCases:
    return InventoryAdjustmentUseCases(SqlAlchemyInventoryAdjustmentRepository(session))


async def _require(checker: CheckPermissionUseCase, current: CurrentUser, company_id: uuid.UUID, code: str) -> None:
    decision = await checker.execute(current.id, company_id, code)
    if not decision.allowed:
        raise AuthorizationError(f"Permiso requerido: {code}", code="forbidden")


async def _persist(
    *, session: SessionDep, audit: AuditService, current: CurrentUser, request: Request,
    company_id: uuid.UUID, action: str, adjustment_id: uuid.UUID | None,
    operation: Awaitable[dict], model: type[T],
) -> T:
    try:
        async with session.begin_nested():
            result = await operation
            response = model.model_validate(result)
            audit_state = jsonable_encoder(response)
            for line in audit_state.get("lines", []):
                line.pop("documented_unit_cost", None)
                line.pop("documented_total_cost", None)
            await audit.record(
                action=action,
                user_id=current.id,
                company_id=company_id,
                resource_type="inventory_adjustments",
                resource_id=str(adjustment_id or getattr(response, "id", "")),
                after_state=audit_state,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                required=True,
            )
            return response
    except (InventoryAdjustmentError, InventoryOperationError) as exc:
        raise InventoryBoundaryError(exc.message, code=exc.code, status_code=exc.status_code) from exc
    except IntegrityError as exc:
        raise InventoryBoundaryError(
            "El ajuste cambió en paralelo o no cumple una relación de empresa, evidencia o inventario.",
            code="adjustment_integrity_conflict",
            status_code=409,
        ) from exc


async def _authorize_header_scope(
    *, session: SessionDep, current: CurrentUser, company_id: uuid.UUID,
    adjustment: InventoryAdjustmentModel,
) -> None:
    if adjustment.transfer_id is not None:
        transfer = await session.scalar(select(InventoryTransferModel).where(
            InventoryTransferModel.company_id == company_id,
            InventoryTransferModel.id == adjustment.transfer_id,
        ))
        if transfer is None:
            raise HTTPException(404, "Traslado vinculado no encontrado.")
        origin = await session.scalar(select(Warehouse).where(
            Warehouse.company_id == company_id, Warehouse.id == transfer.origin_warehouse_id,
        ))
        destination = await session.scalar(select(Warehouse).where(
            Warehouse.company_id == company_id, Warehouse.id == transfer.destination_warehouse_id,
        ))
        context = await get_branch_context(session, current, company_id)
        has_access = bool(context.access_all_branches or (
            origin and context.can_access(origin.branch_id)
        ) or (destination and context.can_access(destination.branch_id)))
        if not has_access:
            raise HTTPException(403, "No tiene acceso al origen ni al destino de este traslado.")
        return
    warehouse = await session.scalar(select(Warehouse).where(
        Warehouse.company_id == company_id,
        Warehouse.id == adjustment.warehouse_id,
        Warehouse.deleted_at.is_(None),
    ))
    if warehouse is None or warehouse.is_transit:
        raise HTTPException(404, "Bodega del ajuste no encontrada.")
    context = await get_branch_context(session, current, company_id)
    if warehouse.branch_id is None:
        if not context.access_all_branches:
            raise HTTPException(403, "Se requiere alcance completo de empresa para esta bodega.")
    else:
        await resolve_branch_scope(session, current, company_id, warehouse.branch_id)


async def _authorize_create_scope(
    *, session: SessionDep, current: CurrentUser, company_id: uuid.UUID,
    warehouse_id: uuid.UUID, transfer_id: uuid.UUID | None,
) -> None:
    warehouse = await session.scalar(select(Warehouse).where(
        Warehouse.company_id == company_id,
        Warehouse.id == warehouse_id,
        Warehouse.deleted_at.is_(None),
    ))
    if warehouse is None:
        raise HTTPException(404, "Bodega no encontrada.")
    if transfer_id is not None:
        transfer = await session.scalar(select(InventoryTransferModel).where(
            InventoryTransferModel.company_id == company_id,
            InventoryTransferModel.id == transfer_id,
        ))
        if transfer is None or transfer.origin_warehouse_id != warehouse_id:
            raise HTTPException(422, "El ajuste de tránsito debe usar la bodega de origen del traslado como ámbito.")
        # Scope to either persisted leg. The transit warehouse itself is never
        # exposed as a general-purpose user-selected warehouse.
        origin = await session.scalar(select(Warehouse).where(Warehouse.company_id == company_id, Warehouse.id == transfer.origin_warehouse_id))
        destination = await session.scalar(select(Warehouse).where(Warehouse.company_id == company_id, Warehouse.id == transfer.destination_warehouse_id))
        context = await get_branch_context(session, current, company_id)
        if not (context.access_all_branches or (origin and context.can_access(origin.branch_id)) or (destination and context.can_access(destination.branch_id))):
            raise HTTPException(403, "No tiene acceso al origen ni al destino del traslado.")
        return
    if warehouse.is_transit:
        raise HTTPException(422, "La bodega técnica de tránsito solo se usa desde una incidencia autorizada.")
    context = await get_branch_context(session, current, company_id)
    if warehouse.branch_id is None:
        if not context.access_all_branches:
            raise HTTPException(403, "Se requiere alcance completo de empresa para esta bodega.")
    else:
        await resolve_branch_scope(session, current, company_id, warehouse.branch_id)


@router.get("/options", response_model=InventoryAdjustmentOptions, dependencies=[Depends(require_permission("inventory:read"))])
async def adjustment_options(
    warehouse_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    q: str = Query(default="", max_length=120),
    limit: int | None = Query(default=None, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    include_items: bool = Query(default=True),
    include_locations: bool = Query(default=True),
) -> InventoryAdjustmentOptions:
    company_id = effective_company_id(request)
    await _authorize_create_scope(
        session=session,
        current=current,
        company_id=company_id,
        warehouse_id=warehouse_id,
        transfer_id=None,
    )
    result = await InventoryAdjustmentUseCases(SqlAlchemyInventoryAdjustmentRepository(session)).options(
        company_id=company_id,
        warehouse_id=warehouse_id,
        q=q,
        limit=limit,
        offset=offset,
        include_items=include_items,
        include_locations=include_locations,
    )
    return InventoryAdjustmentOptions.model_validate(result)


def _line_payloads(lines) -> list[dict]:
    return [line.model_dump() for line in lines]


@router.get("", response_model=InventoryAdjustmentPage, dependencies=[Depends(require_permission("inventory:read"))])
async def list_adjustments(
    request: Request, session: SessionDep, current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    warehouse_id: uuid.UUID | None = Query(default=None),
    adjustment_status: str | None = Query(default=None, alias="status", pattern="^(draft|approved|applied|cancelled)$"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> InventoryAdjustmentPage:
    company_id = effective_company_id(request)
    context = await get_branch_context(session, current, company_id)
    if warehouse_id is not None:
        warehouse = await session.scalar(select(Warehouse).where(Warehouse.company_id == company_id, Warehouse.id == warehouse_id))
        if warehouse is None:
            raise HTTPException(404, "Bodega no encontrada.")
        if warehouse.branch_id is None:
            if not context.access_all_branches:
                raise HTTPException(403, "Se requiere alcance completo de empresa para esta bodega.")
        else:
            await resolve_branch_scope(session, current, company_id, warehouse.branch_id)
        allowed_warehouses = None
    elif context.access_all_branches:
        allowed_warehouses = None
    else:
        branch_ids = [branch.id for branch in context.branches]
        allowed_warehouses = list((await session.scalars(select(Warehouse.id).where(
            Warehouse.company_id == company_id,
            Warehouse.branch_id.in_(branch_ids) if branch_ids else False,
            Warehouse.deleted_at.is_(None),
        ))).all())
    rows, total = await _use_cases(session).list(
        company_id=company_id, warehouse_id=warehouse_id,
        allowed_warehouse_ids=allowed_warehouses,
        status=adjustment_status, date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )
    if not (await checker.execute(current.id, company_id, "inventory:valuation")).allowed:
        for item in rows:
            for line in item["lines"]:
                line["documented_unit_cost"] = None
                line["documented_total_cost"] = None
    return InventoryAdjustmentPage(items=rows, total=total)


@router.post("", response_model=InventoryAdjustmentOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("inventory:read"))])
async def create_adjustment(
    body: InventoryAdjustmentCreateIn, request: Request, session: SessionDep, current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> InventoryAdjustmentOut:
    company_id = effective_company_id(request)
    await _require(checker, current, company_id, "inventory:adjust")
    await _authorize_create_scope(session=session, current=current, company_id=company_id, warehouse_id=body.warehouse_id, transfer_id=body.transfer_id)
    response = await _persist(
        session=session, audit=audit, current=current, request=request, company_id=company_id,
        action="CREATE", adjustment_id=None,
        operation=_use_cases(session).create(
            company_id=company_id, actor_id=current.id, warehouse_id=body.warehouse_id,
            idempotency_key=body.idempotency_key,
            operational_date=body.operational_date, accounting_date=body.accounting_date,
            reason=body.reason, document_reference=body.document_reference, notes=body.notes,
            lines=_line_payloads(body.lines), correction_of_id=body.correction_of_id,
            transfer_id=body.transfer_id, transfer_incident_id=body.transfer_incident_id,
        ), model=InventoryAdjustmentOut,
    )
    if not (await checker.execute(current.id, company_id, "inventory:valuation")).allowed:
        _redact_adjustment_costs(response)
    return response


@router.get("/{adjustment_id}", response_model=InventoryAdjustmentOut, dependencies=[Depends(require_permission("inventory:read"))])
async def get_adjustment(adjustment_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser, checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]) -> InventoryAdjustmentOut:
    company_id = effective_company_id(request)
    row = await session.scalar(select(InventoryAdjustmentModel).where(InventoryAdjustmentModel.company_id == company_id, InventoryAdjustmentModel.id == adjustment_id))
    if row is None:
        raise HTTPException(404, "Ajuste no encontrado.")
    await _authorize_header_scope(session=session, current=current, company_id=company_id, adjustment=row)
    data = await _use_cases(session).get(company_id, adjustment_id)
    assert data is not None
    if not (await checker.execute(current.id, company_id, "inventory:valuation")).allowed:
        for line in data["lines"]:
            line["documented_unit_cost"] = None
            line["documented_total_cost"] = None
    return InventoryAdjustmentOut.model_validate(data)


@router.put("/{adjustment_id}", response_model=InventoryAdjustmentOut, dependencies=[Depends(require_permission("inventory:read"))])
async def update_adjustment(adjustment_id: uuid.UUID, body: InventoryAdjustmentUpdateIn, request: Request, session: SessionDep, current: CurrentUser, checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)], audit: Annotated[AuditService, Depends(get_audit_service)]) -> InventoryAdjustmentOut:
    company_id = effective_company_id(request)
    await _require(checker, current, company_id, "inventory:adjust")
    row = await session.scalar(select(InventoryAdjustmentModel).where(InventoryAdjustmentModel.company_id == company_id, InventoryAdjustmentModel.id == adjustment_id))
    if row is None:
        raise HTTPException(404, "Ajuste no encontrado.")
    await _authorize_header_scope(session=session, current=current, company_id=company_id, adjustment=row)
    response = await _persist(session=session, audit=audit, current=current, request=request, company_id=company_id, action="UPDATE", adjustment_id=adjustment_id,
        operation=_use_cases(session).update(company_id=company_id, adjustment_id=adjustment_id, actor_id=current.id,
            operational_date=body.operational_date, accounting_date=body.accounting_date, reason=body.reason,
            document_reference=body.document_reference, notes=body.notes, lines=_line_payloads(body.lines),
            approval_revocation_reason=body.approval_revocation_reason), model=InventoryAdjustmentOut)
    if not (await checker.execute(current.id, company_id, "inventory:valuation")).allowed:
        _redact_adjustment_costs(response)
    return response


@router.post("/{adjustment_id}/documents", response_model=InitiateDocumentOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("inventory:read"))])
async def initiate_document(adjustment_id: uuid.UUID, body: InventoryAdjustmentDocumentInitiateIn, request: Request, session: SessionDep, current: CurrentUser, checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)], documents: Annotated[DocumentService, Depends(get_document_service)], audit: Annotated[AuditService, Depends(get_audit_service)]) -> InitiateDocumentOut:
    company_id = effective_company_id(request)
    await _require(checker, current, company_id, "inventory:adjust")
    adjustment = await session.scalar(select(InventoryAdjustmentModel).where(InventoryAdjustmentModel.company_id == company_id, InventoryAdjustmentModel.id == adjustment_id).with_for_update())
    if adjustment is None:
        raise HTTPException(404, "Ajuste no encontrado.")
    await _authorize_header_scope(session=session, current=current, company_id=company_id, adjustment=adjustment)
    if adjustment.status != "draft":
        raise HTTPException(409, "Los comprobantes solo se agregan al borrador; revoque la aprobación primero.")
    try:
        async with session.begin_nested():
            ticket = await documents.initiate(InitiateDocumentInput(
                company_id=company_id, actor_id=current.id, filename=body.file_name,
                content_type=body.content_type, size_bytes=body.size_bytes,
                checksum_sha256=body.checksum_sha256,
            ))
            session.add(InventoryAdjustmentDocumentModel(
                company_id=company_id, adjustment_id=adjustment_id, document_id=ticket.document.id,
                checksum_sha256=ticket.document.checksum_sha256,
                original_filename=ticket.document.original_filename,
                linked_by_id=current.id, linked_at=ticket.document.created_at,
            ))
            await audit.record(action="ATTACH_DOCUMENT", user_id=current.id, company_id=company_id,
                resource_type="inventory_adjustments", resource_id=str(adjustment_id),
                after_state={"document_id": str(ticket.document.id), "status": ticket.document.status}, required=True)
            return InitiateDocumentOut(document_id=ticket.document.id, upload_url=ticket.upload_url,
                required_headers=ticket.required_headers, expires_at=ticket.expires_at)
    except InventoryAdjustmentError as exc:
        raise InventoryBoundaryError(exc.message, code=exc.code, status_code=exc.status_code) from exc
    except IntegrityError as exc:
        raise HTTPException(409, "No se pudo vincular el documento al ajuste.") from exc


@router.post("/{adjustment_id}/documents/{document_id}/complete", response_model=InventoryAdjustmentOut, dependencies=[Depends(require_permission("inventory:read"))])
async def complete_document(adjustment_id: uuid.UUID, document_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser, checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)], documents: Annotated[DocumentService, Depends(get_document_service)], audit: Annotated[AuditService, Depends(get_audit_service)]) -> InventoryAdjustmentOut:
    company_id = effective_company_id(request)
    await _require(checker, current, company_id, "inventory:adjust")
    adjustment = await session.scalar(select(InventoryAdjustmentModel).where(InventoryAdjustmentModel.company_id == company_id, InventoryAdjustmentModel.id == adjustment_id))
    if adjustment is None:
        raise HTTPException(404, "Ajuste no encontrado.")
    await _authorize_header_scope(session=session, current=current, company_id=company_id, adjustment=adjustment)
    link = await session.scalar(select(InventoryAdjustmentDocumentModel).where(
        InventoryAdjustmentDocumentModel.company_id == company_id,
        InventoryAdjustmentDocumentModel.adjustment_id == adjustment_id,
        InventoryAdjustmentDocumentModel.document_id == document_id,
        InventoryAdjustmentDocumentModel.detached_at.is_(None),
    ).with_for_update())
    if link is None:
        raise HTTPException(404, "El documento no está asociado a este ajuste.")
    if adjustment.status != "draft":
        raise HTTPException(409, "Complete la carga antes de aprobar el ajuste.")
    asset = await documents.complete(company_id, document_id, current.id)
    if asset.status != "active" or asset.checksum_sha256 != link.checksum_sha256:
        raise HTTPException(422, "El comprobante no quedó activo o su checksum no coincide.")
    link.upload_completed_at = asset.scanned_at or asset.updated_at
    await audit.record(action="COMPLETE_DOCUMENT", user_id=current.id, company_id=company_id,
        resource_type="inventory_adjustments", resource_id=str(adjustment_id),
        after_state={"document_id": str(document_id), "status": asset.status}, required=True)
    data = await _use_cases(session).get(company_id, adjustment_id)
    assert data is not None
    if not (await checker.execute(current.id, company_id, "inventory:valuation")).allowed:
        for line in data["lines"]:
            line["documented_unit_cost"] = None
            line["documented_total_cost"] = None
    return InventoryAdjustmentOut.model_validate(data)


@router.delete("/{adjustment_id}/documents/{document_id}", response_model=InventoryAdjustmentOut, dependencies=[Depends(require_permission("inventory:read"))])
async def detach_document(adjustment_id: uuid.UUID, document_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser, checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)], audit: Annotated[AuditService, Depends(get_audit_service)]) -> InventoryAdjustmentOut:
    company_id = effective_company_id(request)
    await _require(checker, current, company_id, "inventory:adjust")
    adjustment = await session.scalar(select(InventoryAdjustmentModel).where(InventoryAdjustmentModel.company_id == company_id, InventoryAdjustmentModel.id == adjustment_id).with_for_update())
    if adjustment is None:
        raise HTTPException(404, "Ajuste no encontrado.")
    await _authorize_header_scope(session=session, current=current, company_id=company_id, adjustment=adjustment)
    if adjustment.status != "draft":
        raise HTTPException(409, "El soporte aprobado se conserva en el historial; revoque la aprobación para reemplazarlo.")
    link = await session.scalar(select(InventoryAdjustmentDocumentModel).where(
        InventoryAdjustmentDocumentModel.company_id == company_id,
        InventoryAdjustmentDocumentModel.adjustment_id == adjustment_id,
        InventoryAdjustmentDocumentModel.document_id == document_id,
        InventoryAdjustmentDocumentModel.detached_at.is_(None),
    ).with_for_update())
    if link is None:
        raise HTTPException(404, "Documento no vinculado.")
    link.detached_at = datetime.now(UTC)
    link.detached_by_id = current.id
    await audit.record(action="DETACH_DOCUMENT", user_id=current.id, company_id=company_id,
        resource_type="inventory_adjustments", resource_id=str(adjustment_id),
        after_state={"document_id": str(document_id)}, required=True)
    data = await _use_cases(session).get(company_id, adjustment_id)
    assert data is not None
    if not (await checker.execute(current.id, company_id, "inventory:valuation")).allowed:
        for line in data["lines"]:
            line["documented_unit_cost"] = None
            line["documented_total_cost"] = None
    return InventoryAdjustmentOut.model_validate(data)


@router.get("/{adjustment_id}/documents/{document_id}/download", response_model=DownloadUrlOut, dependencies=[Depends(require_permission("inventory:read"))])
async def download_document(
    adjustment_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    documents: Annotated[DocumentService, Depends(get_document_service)],
) -> DownloadUrlOut:
    company_id = effective_company_id(request)
    adjustment = await session.scalar(select(InventoryAdjustmentModel).where(InventoryAdjustmentModel.company_id == company_id, InventoryAdjustmentModel.id == adjustment_id))
    if adjustment is None:
        raise HTTPException(404, "Ajuste no encontrado.")
    await _authorize_header_scope(session=session, current=current, company_id=company_id, adjustment=adjustment)
    await _require(checker, current, company_id, "inventory:valuation")
    link = await session.scalar(select(InventoryAdjustmentDocumentModel).where(
        InventoryAdjustmentDocumentModel.company_id == company_id,
        InventoryAdjustmentDocumentModel.adjustment_id == adjustment_id,
        InventoryAdjustmentDocumentModel.document_id == document_id,
        InventoryAdjustmentDocumentModel.detached_at.is_(None),
    ))
    if link is None:
        raise HTTPException(404, "Documento no asociado a este ajuste.")
    asset = await documents.get(company_id, document_id)
    if asset.status != "active" or asset.checksum_sha256 != link.checksum_sha256:
        raise HTTPException(409, "El comprobante no está activo o ya no coincide con el archivo vinculado.")
    url, expires_at = await documents.download_url(company_id, document_id, current.id)
    return DownloadUrlOut(url=url, expires_at=expires_at)


@router.post("/{adjustment_id}/approve", response_model=InventoryAdjustmentOut, dependencies=[Depends(require_permission("inventory:read"))])
async def approve_adjustment(adjustment_id: uuid.UUID, body: InventoryAdjustmentApproveIn, request: Request, session: SessionDep, current: CurrentUser, checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)], audit: Annotated[AuditService, Depends(get_audit_service)]) -> InventoryAdjustmentOut:
    company_id = effective_company_id(request)
    await _require(checker, current, company_id, "inventory:adjust_approve")
    row = await session.scalar(select(InventoryAdjustmentModel).where(InventoryAdjustmentModel.company_id == company_id, InventoryAdjustmentModel.id == adjustment_id))
    if row is None:
        raise HTTPException(404, "Ajuste no encontrado.")
    await _authorize_header_scope(session=session, current=current, company_id=company_id, adjustment=row)
    response = await _persist(session=session, audit=audit, current=current, request=request, company_id=company_id,
        action="APPROVE", adjustment_id=adjustment_id,
        operation=_use_cases(session).approve(company_id=company_id, adjustment_id=adjustment_id, actor_id=current.id, expected_version=body.expected_version),
        model=InventoryAdjustmentOut)
    if not (await checker.execute(current.id, company_id, "inventory:valuation")).allowed:
        _redact_adjustment_costs(response)
    return response


@router.post("/{adjustment_id}/cancel", response_model=InventoryAdjustmentOut, dependencies=[Depends(require_permission("inventory:read"))])
async def cancel_adjustment(adjustment_id: uuid.UUID, body: InventoryAdjustmentCancelIn, request: Request, session: SessionDep, current: CurrentUser, checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)], audit: Annotated[AuditService, Depends(get_audit_service)]) -> InventoryAdjustmentOut:
    company_id = effective_company_id(request)
    await _require(checker, current, company_id, "inventory:adjust")
    row = await session.scalar(select(InventoryAdjustmentModel).where(InventoryAdjustmentModel.company_id == company_id, InventoryAdjustmentModel.id == adjustment_id))
    if row is None:
        raise HTTPException(404, "Ajuste no encontrado.")
    await _authorize_header_scope(session=session, current=current, company_id=company_id, adjustment=row)
    response = await _persist(session=session, audit=audit, current=current, request=request, company_id=company_id,
        action="CANCEL", adjustment_id=adjustment_id,
        operation=_use_cases(session).cancel(company_id=company_id, adjustment_id=adjustment_id, actor_id=current.id, reason=body.reason),
        model=InventoryAdjustmentOut)
    if not (await checker.execute(current.id, company_id, "inventory:valuation")).allowed:
        _redact_adjustment_costs(response)
    return response


@router.post("/{adjustment_id}/apply", response_model=InventoryAdjustmentOut, dependencies=[Depends(require_permission("inventory:read"))])
async def apply_adjustment(adjustment_id: uuid.UUID, body: InventoryAdjustmentApplyIn, request: Request, session: SessionDep, current: CurrentUser, checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)], audit: Annotated[AuditService, Depends(get_audit_service)]) -> InventoryAdjustmentOut:
    company_id = effective_company_id(request)
    await _require(checker, current, company_id, "inventory:adjust_approve")
    row = await session.scalar(select(InventoryAdjustmentModel).where(InventoryAdjustmentModel.company_id == company_id, InventoryAdjustmentModel.id == adjustment_id))
    if row is None:
        raise HTTPException(404, "Ajuste no encontrado.")
    await _authorize_header_scope(session=session, current=current, company_id=company_id, adjustment=row)
    response = await _persist(session=session, audit=audit, current=current, request=request, company_id=company_id,
        action="APPLY", adjustment_id=adjustment_id,
        operation=_use_cases(session).apply(company_id=company_id, adjustment_id=adjustment_id, actor_id=current.id, idempotency_key=body.idempotency_key),
        model=InventoryAdjustmentOut)
    if not (await checker.execute(current.id, company_id, "inventory:valuation")).allowed:
        _redact_adjustment_costs(response)
    return response


@router.post("/{adjustment_id}/correction", response_model=InventoryAdjustmentOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("inventory:read"))])
async def create_correction(adjustment_id: uuid.UUID, body: InventoryAdjustmentCorrectionIn, request: Request, session: SessionDep, current: CurrentUser, checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)], audit: Annotated[AuditService, Depends(get_audit_service)]) -> InventoryAdjustmentOut:
    company_id = effective_company_id(request)
    await _require(checker, current, company_id, "inventory:adjust")
    original = await session.scalar(select(InventoryAdjustmentModel).where(InventoryAdjustmentModel.company_id == company_id, InventoryAdjustmentModel.id == adjustment_id))
    if original is None:
        raise HTTPException(404, "Ajuste original no encontrado.")
    await _authorize_header_scope(session=session, current=current, company_id=company_id, adjustment=original)
    response = await _persist(session=session, audit=audit, current=current, request=request, company_id=company_id,
        action="CREATE_CORRECTION", adjustment_id=adjustment_id,
        operation=_use_cases(session).correct(company_id=company_id, adjustment_id=adjustment_id, actor_id=current.id,
            reason=body.reason, document_reference=body.document_reference,
            operational_date=body.operational_date, accounting_date=body.accounting_date),
        model=InventoryAdjustmentOut)
    if not (await checker.execute(current.id, company_id, "inventory:valuation")).allowed:
        _redact_adjustment_costs(response)
    return response
