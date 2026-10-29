"""Purchase-request queue and editable consolidation endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.api.v1.company_access import get_branch_context, request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_inventory_use_cases,
    get_purchase_consolidation_adjudication_use_cases,
    get_purchase_consolidation_use_cases,
    get_purchase_quotation_use_cases,
    require_permission,
)
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.purchase_consolidation import (
    ApprovedRequestCandidate,
    ConsolidationEventResponse,
    ConsolidationLineResponse,
    ConsolidationSourceResponse,
    PurchaseConsolidationAddRequests,
    PurchaseConsolidationAwardBoardResponse,
    PurchaseConsolidationAwardCreate,
    PurchaseConsolidationAwardDecisionResponse,
    PurchaseConsolidationAwardLineResponse,
    PurchaseConsolidationAwardOfferResponse,
    PurchaseConsolidationAwardRevoke,
    PurchaseConsolidationCancel,
    PurchaseConsolidationClose,
    PurchaseConsolidationCreate,
    PurchaseConsolidationInventorySnapshotResponse,
    PurchaseConsolidationResponse,
    PurchaseConsolidationUpdate,
    PurchaseWorkItemResponse,
    SelectedPurchaseRequestResolution,
)
from app.api.v1.schemas.purchase_quotation import (
    PurchaseQuotationFromConsolidationCreate,
    PurchaseQuotationResponse,
)
from app.application.audit.audit_service import AuditService
from app.application.inventory import InventoryUseCases
from app.application.procurement_reports import consolidation_report
from app.application.purchase_consolidations import (
    BranchDemandAssignment,
    CentralDemandDraft,
    PurchaseConsolidationAdjudicationUseCases,
    PurchaseConsolidationUseCases,
    SourceQuantityChange,
)
from app.application.purchase_quotations import PurchaseQuotationUseCases
from app.core.exceptions import NotFoundError
from app.domain.entities.purchase_consolidation import (
    PurchaseConsolidation,
    PurchaseConsolidationAward,
)
from app.infrastructure.models.organization import Branch, Warehouse
from app.infrastructure.procurement_report_renderer import render_pdf
from app.infrastructure.repositories.procurement_report_repository import (
    ProcurementReportRepository,
)

router = APIRouter(tags=["purchase-consolidations"])


@router.get(
    "/purchase-consolidations/{consolidation_id}/export",
    response_class=Response,
    dependencies=[Depends(require_permission("purchase_requests:read"))],
)
async def export_consolidation(
    consolidation_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
) -> Response:
    company_id = request_company_id(request)
    item = await use_cases.get(company_id, consolidation_id)
    await _assert_consolidation_scope(session, current, company_id, item)
    context = await ProcurementReportRepository(session).context(company_id)
    payload = await run_in_threadpool(render_pdf, consolidation_report(item, context))
    return Response(
        payload,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{item.code}.pdf"',
            "Cache-Control": "no-store",
        },
    )


def _response(item: PurchaseConsolidation) -> PurchaseConsolidationResponse:
    return PurchaseConsolidationResponse(
        id=item.id,
        company_id=item.company_id,
        code=item.code,
        period_start=item.period_start,
        period_end=item.period_end,
        status=item.status,
        created_by_id=item.created_by_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
        central_warehouse_id=item.central_warehouse_id,
        central_warehouse_name=item.central_warehouse_name,
        notes=item.notes,
        lines=tuple(
            ConsolidationLineResponse(
                id=line.id,
                product_id=line.product_id,
                product_sku=line.product_sku,
                product_name=line.product_name,
                unit_id=line.unit_id,
                unit_name=line.unit_name,
                branch_quantity=line.branch_quantity,
                central_quantity=line.central_quantity,
                central_reason=line.central_reason,
                total_quantity=line.total_quantity,
                sources=tuple(
                    ConsolidationSourceResponse.model_validate(source) for source in line.sources
                ),
            )
            for line in item.lines
        ),
        events=tuple(ConsolidationEventResponse.model_validate(event) for event in item.events),
    )


def _award_board_response(board) -> PurchaseConsolidationAwardBoardResponse:
    return PurchaseConsolidationAwardBoardResponse(
        consolidation_id=board.consolidation_id,
        consolidation_code=board.consolidation_code,
        currencies=board.currencies,
        lines=tuple(
            PurchaseConsolidationAwardLineResponse(
                id=line.id,
                product_id=line.product_id,
                product_sku=line.product_sku,
                product_name=line.product_name,
                unit_id=line.unit_id,
                unit_name=line.unit_name,
                demand_quantity=line.demand_quantity,
                awarded_quantity=line.awarded_quantity,
                remaining_quantity=line.remaining_quantity,
                offers=tuple(
                    PurchaseConsolidationAwardOfferResponse(
                        quotation_id=offer.quotation_id,
                        quotation_code=offer.quotation_code,
                        quotation_version=offer.quotation_version,
                        supplier_id=offer.supplier_id,
                        quotation_status=offer.quotation_status,
                        currency=offer.quotation_currency,
                        valid_until=offer.quotation_valid_until,
                        delivery_days=offer.quotation_delivery_days,
                        payment_terms=offer.quotation_payment_terms,
                        quotation_total=offer.quotation_total,
                        quotation_expenses_total=offer.quotation_expenses_total,
                        quotation_detail_id=offer.quotation_detail_id,
                        requested_quantity=offer.requested_quantity,
                        offered_quantity=offer.offered_quantity,
                        available_quantity=offer.available_quantity,
                        awarded_quantity=offer.awarded_quantity,
                        remaining_offer_quantity=offer.remaining_offer_quantity,
                        unit_price=offer.unit_price,
                        discount=offer.discount,
                        subtotal=offer.subtotal,
                        tax_rate=offer.tax_rate,
                        tax_amount=offer.tax_amount,
                        line_total=offer.line_total,
                        line_delivery_days=offer.delivery_days,
                        notes=offer.notes,
                        can_award=offer.can_award,
                        blocked_reason=offer.blocked_reason,
                    )
                    for offer in line.offers
                ),
                decisions=tuple(
                    PurchaseConsolidationAwardDecisionResponse(
                        id=decision.id,
                        quotation_id=decision.purchase_quotation_id,
                        quotation_code=decision.quotation_code,
                        supplier_id=decision.supplier_id,
                        quantity=decision.quantity,
                        reason=decision.reason,
                        decided_by_id=decision.decided_by_id,
                        created_at=decision.created_at,
                        revoked_at=decision.revoked_at,
                        revoked_by_id=decision.revoked_by_id,
                        revocation_reason=decision.revocation_reason,
                        ordered_quantity=decision.ordered_quantity,
                        remaining_to_order_quantity=decision.remaining_to_order_quantity,
                    )
                    for decision in line.decisions
                ),
            )
            for line in board.lines
        ),
    )


def _award_audit_state(award: PurchaseConsolidationAward) -> dict[str, object]:
    return {
        "id": str(award.id),
        "consolidation_id": str(award.consolidation_id),
        "consolidation_line_id": str(award.consolidation_line_id),
        "quotation_id": str(award.purchase_quotation_id),
        "quotation_detail_id": str(award.purchase_quotation_detail_id),
        "supplier_id": award.supplier_id,
        "quantity": str(award.quantity),
        "reason": award.reason,
        "decided_by_id": str(award.decided_by_id),
        "created_at": award.created_at.isoformat() if award.created_at else None,
        "revoked_at": award.revoked_at.isoformat() if award.revoked_at else None,
        "revoked_by_id": str(award.revoked_by_id) if award.revoked_by_id else None,
        "revocation_reason": award.revocation_reason,
    }


def _audit_state(item: PurchaseConsolidation) -> dict[str, object]:
    return {
        "id": str(item.id),
        "code": item.code,
        "period_start": item.period_start.isoformat(),
        "period_end": item.period_end.isoformat(),
        "status": item.status.value,
        "central_warehouse_id": str(item.central_warehouse_id)
        if item.central_warehouse_id
        else None,
        "lines": [
            {
                "id": str(line.id),
                "product_id": line.product_id,
                "unit_id": line.unit_id,
                "branch_quantity": str(line.branch_quantity),
                "central_quantity": str(line.central_quantity),
                "total_quantity": str(line.total_quantity),
                "sources": [
                    {
                        "id": str(source.id),
                        "request_id": str(source.purchase_request_id),
                        "request_detail_id": str(source.purchase_request_detail_id),
                        "requested": str(source.requested_quantity),
                        "included": str(source.included_quantity),
                        "reason": source.reason,
                        "demand_level": source.demand_level.value if source.demand_level else None,
                    }
                    for source in line.sources
                ],
            }
            for line in item.lines
        ],
    }


async def _assert_consolidation_scope(
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    item: PurchaseConsolidation,
) -> None:
    context = await get_branch_context(session, current, company_id)
    if not context.access_all_branches:
        inaccessible = {
            source.branch_id
            for line in item.lines
            for source in line.sources
            if not context.can_access(source.branch_id)
        }
        if inaccessible:
            raise HTTPException(
                status_code=403, detail="No tiene acceso a todas las sucursales del consolidado."
            )
    if item.central_warehouse_id is not None:
        await _resolve_warehouse_branch(session, current, company_id, item.central_warehouse_id)


async def _resolve_warehouse_branch(
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    *,
    selected_branch_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    row = await session.execute(
        select(
            Warehouse.company_id,
            Warehouse.branch_id,
            Warehouse.is_central,
            Branch.is_headquarters,
        )
        .outerjoin(
            Branch,
            (Branch.id == Warehouse.branch_id) & (Branch.company_id == Warehouse.company_id),
        )
        .where(
            Warehouse.id == warehouse_id,
            Warehouse.company_id == company_id,
            Warehouse.deleted_at.is_(None),
            Warehouse.is_active.is_(True),
            Warehouse.is_transit.is_(False),
            Warehouse.operational_status == "active",
        )
    )
    warehouse = row.one_or_none()
    if warehouse is None or warehouse.branch_id is None:
        raise HTTPException(status_code=404, detail="Almacén no encontrado.")
    if warehouse.is_central and not warehouse.is_headquarters:
        raise HTTPException(
            status_code=409, detail="La bodega central no está vinculada a la matriz."
        )
    await resolve_branch_scope(session, current, company_id, warehouse.branch_id)
    if (
        selected_branch_id is not None
        and not warehouse.is_central
        and warehouse.branch_id is not None
        and selected_branch_id != warehouse.branch_id
    ):
        raise HTTPException(
            status_code=422,
            detail="El almacén seleccionado no pertenece a la sucursal filtrada.",
        )
    return warehouse.branch_id


async def _assert_request_scope(
    *,
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    use_cases: PurchaseConsolidationUseCases,
    request_ids: tuple[uuid.UUID, ...],
) -> None:
    for request_id in request_ids:
        item = await use_cases.get_request_for_consolidation(company_id, request_id)
        if item is not None:
            await resolve_branch_scope(session, current, company_id, item.branch_id)


@router.get(
    "/purchase-work-items",
    response_model=Page[PurchaseWorkItemResponse],
    summary="Listar solicitudes y consolidados de compra",
    dependencies=[Depends(require_permission("purchase_requests:read"))],
)
async def list_purchase_work_items(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    item_type: Literal["individual", "consolidated"] | None = Query(None, alias="type"),
    status_filter: str | None = Query(None, alias="status", max_length=32),
    q: str | None = Query(None, max_length=120),
    branch_id: uuid.UUID | None = Query(None),
    warehouse_id: uuid.UUID | None = Query(None),
    category_id: int | None = Query(None, ge=1),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    consolidation_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    use_cases: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
) -> Page[PurchaseWorkItemResponse]:
    company_id = request_company_id(request)
    await resolve_branch_scope(session, current, company_id, branch_id)
    if warehouse_id is not None:
        await _resolve_warehouse_branch(
            session, current, company_id, warehouse_id, selected_branch_id=branch_id
        )
    if date_from and date_to and date_to < date_from:
        raise HTTPException(
            status_code=422, detail="La fecha final no puede ser anterior a la inicial."
        )
    items, total = await use_cases.list_work_items(
        company_id,
        item_type=item_type,
        status=status_filter,
        query=q,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        consolidation_id=consolidation_id,
        skip=(page - 1) * size,
        limit=size,
    )
    pages = (total + size - 1) // size if total else 0
    return Page(
        items=[PurchaseWorkItemResponse.model_validate(item) for item in items],
        meta=PageMeta(page=page, size=size, total=total, pages=pages),
    )


@router.get(
    "/purchase-consolidations/eligible-requests",
    response_model=Page[ApprovedRequestCandidate],
    summary="Listar solicitudes aprobadas disponibles para consolidar",
    dependencies=[Depends(require_permission("purchase_requests:read"))],
)
async def list_eligible_requests(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    date_from: date = Query(...),
    date_to: date = Query(...),
    branch_id: uuid.UUID | None = Query(None),
    warehouse_id: uuid.UUID | None = Query(None),
    q: str | None = Query(None, max_length=120),
    request_ids: list[uuid.UUID] = Query(default=[], max_length=100),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    use_cases: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
) -> Page[ApprovedRequestCandidate]:
    company_id = request_company_id(request)
    selected_request_ids = tuple(dict.fromkeys(request_ids))
    if selected_request_ids:
        await _assert_request_scope(
            session=session,
            current=current,
            company_id=company_id,
            use_cases=use_cases,
            request_ids=selected_request_ids,
        )
    else:
        await resolve_branch_scope(session, current, company_id, branch_id)
    if warehouse_id is not None and not selected_request_ids:
        await _resolve_warehouse_branch(
            session, current, company_id, warehouse_id, selected_branch_id=branch_id
        )
    if date_to < date_from:
        raise HTTPException(
            status_code=422, detail="La fecha final no puede ser anterior a la inicial."
        )
    items, total = await use_cases.list_approved_requests(
        company_id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        date_from=date_from,
        date_to=date_to,
        query=q,
        request_ids=selected_request_ids,
        skip=(page - 1) * size,
        limit=size,
    )
    pages = (total + size - 1) // size if total else 0
    return Page(
        items=[ApprovedRequestCandidate.model_validate(item) for item in items],
        meta=PageMeta(page=page, size=size, total=total, pages=pages),
    )


@router.get(
    "/purchase-consolidations/selected-requests",
    response_model=list[SelectedPurchaseRequestResolution],
    summary="Resolver el estado de solicitudes seleccionadas para consolidar",
    dependencies=[Depends(require_permission("purchase_requests:read"))],
)
async def resolve_selected_purchase_requests(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    request_ids: list[uuid.UUID] = Query(default=[], max_length=100),
    use_cases: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
) -> list[SelectedPurchaseRequestResolution]:
    company_id = request_company_id(request)
    selected_request_ids = tuple(dict.fromkeys(request_ids))
    if not selected_request_ids:
        return []

    await _assert_request_scope(
        session=session,
        current=current,
        company_id=company_id,
        use_cases=use_cases,
        request_ids=selected_request_ids,
    )
    resolutions = await use_cases.resolve_selected_requests(company_id, selected_request_ids)
    visible_resolutions: list[SelectedPurchaseRequestResolution] = []
    for request_resolution in resolutions:
        visible_resolution = request_resolution
        if request_resolution["eligibility"] == "already_consolidated":
            can_view_all_consolidations = True
            for consolidation_ref in request_resolution["consolidations"]:
                try:
                    consolidation = await use_cases.get(company_id, consolidation_ref["id"])
                except NotFoundError:
                    can_view_all_consolidations = False
                    break
                try:
                    await _assert_consolidation_scope(session, current, company_id, consolidation)
                except HTTPException as exc:
                    if exc.status_code not in (403, 404):
                        raise
                    can_view_all_consolidations = False
                    break
            if not can_view_all_consolidations:
                visible_resolution = {
                    **request_resolution,
                    "eligibility": "unavailable",
                    "consolidations": (),
                }
        visible_resolutions.append(
            SelectedPurchaseRequestResolution.model_validate(visible_resolution)
        )
    return visible_resolutions


@router.post(
    "/purchase-consolidations",
    response_model=PurchaseConsolidationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear borrador de consolidado",
    dependencies=[Depends(require_permission("purchase_requests:manage"))],
)
async def create_consolidation(
    payload: PurchaseConsolidationCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseConsolidationResponse:
    company_id = request_company_id(request)
    if payload.central_warehouse_id is not None:
        await _resolve_warehouse_branch(session, current, company_id, payload.central_warehouse_id)
    await _assert_request_scope(
        session=session,
        current=current,
        company_id=company_id,
        use_cases=use_cases,
        request_ids=payload.request_ids,
    )
    created = await use_cases.create(
        company_id=company_id,
        actor_id=current.id,
        request_ids=payload.request_ids,
        period_start=payload.period_start,
        period_end=payload.period_end,
        central_warehouse_id=payload.central_warehouse_id,
        notes=payload.notes,
        demand_levels=tuple(
            BranchDemandAssignment(
                branch_id=assignment.branch_id,
                product_id=assignment.product_id,
                level=assignment.level,
            )
            for assignment in payload.demand_levels
        ),
    )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=company_id,
        branch_id=None,
        resource_type="purchase_consolidations",
        resource_id=str(created.id),
        after_state=_audit_state(created),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return _response(created)


@router.get(
    "/purchase-consolidations/{consolidation_id}",
    response_model=PurchaseConsolidationResponse,
    summary="Consultar un consolidado",
    dependencies=[Depends(require_permission("purchase_requests:read"))],
)
async def get_consolidation(
    consolidation_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
) -> PurchaseConsolidationResponse:
    company_id = request_company_id(request)
    item = await use_cases.get(company_id, consolidation_id)
    await _assert_consolidation_scope(session, current, company_id, item)
    return _response(item)


@router.get(
    "/purchase-consolidations/{consolidation_id}/purchase-quotations",
    response_model=list[PurchaseQuotationResponse],
    summary="Listar RFQ preparadas para un consolidado",
    dependencies=[
        Depends(require_permission("purchase_requests:read")),
        Depends(require_permission("purchase_quotations:read")),
    ],
)
async def list_consolidation_quotations(
    consolidation_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    quotations: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
) -> list[PurchaseQuotationResponse]:
    company_id = request_company_id(request)
    consolidation = await consolidations.get(company_id, consolidation_id)
    await _assert_consolidation_scope(session, current, company_id, consolidation)
    items = await quotations.list_consolidation_quotations(company_id, consolidation_id)
    return [PurchaseQuotationResponse.model_validate(item) for item in items]


@router.get(
    "/purchase-consolidations/{consolidation_id}/adjudication",
    response_model=PurchaseConsolidationAwardBoardResponse,
    summary="Comparar ofertas y consultar adjudicaciones por producto",
    dependencies=[
        Depends(require_permission("purchase_requests:read")),
        Depends(require_permission("purchase_quotations:read")),
    ],
)
async def get_consolidation_adjudication_board(
    consolidation_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    adjudication: PurchaseConsolidationAdjudicationUseCases = Depends(
        get_purchase_consolidation_adjudication_use_cases
    ),
) -> PurchaseConsolidationAwardBoardResponse:
    company_id = request_company_id(request)
    item = await consolidations.get(company_id, consolidation_id)
    await _assert_consolidation_scope(session, current, company_id, item)
    return _award_board_response(await adjudication.get_board(company_id, consolidation_id))


@router.post(
    "/purchase-consolidations/{consolidation_id}/awards",
    response_model=PurchaseConsolidationAwardBoardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adjudicar cantidad de producto a una oferta de proveedor",
    dependencies=[
        Depends(require_permission("purchase_requests:read")),
        Depends(require_permission("purchase_quotations:read")),
        Depends(require_permission("purchase_quotations:select")),
    ],
)
async def create_consolidation_award(
    consolidation_id: uuid.UUID,
    payload: PurchaseConsolidationAwardCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    adjudication: PurchaseConsolidationAdjudicationUseCases = Depends(
        get_purchase_consolidation_adjudication_use_cases
    ),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseConsolidationAwardBoardResponse:
    company_id = request_company_id(request)
    item = await consolidations.get(company_id, consolidation_id)
    await _assert_consolidation_scope(session, current, company_id, item)
    award = await adjudication.award(
        company_id=company_id,
        consolidation_id=consolidation_id,
        consolidation_line_id=payload.consolidation_line_id,
        quotation_id=payload.quotation_id,
        quotation_detail_id=payload.quotation_detail_id,
        quantity=payload.quantity,
        reason=payload.reason,
        actor_id=current.id,
    )
    await audit.record(
        action="ADJUDICATE",
        user_id=current.id,
        company_id=company_id,
        branch_id=None,
        resource_type="purchase_consolidation_awards",
        resource_id=str(award.id),
        after_state=_award_audit_state(award),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return _award_board_response(await adjudication.get_board(company_id, consolidation_id))


@router.post(
    "/purchase-consolidations/{consolidation_id}/awards/{award_id}/revoke",
    response_model=PurchaseConsolidationAwardBoardResponse,
    summary="Revertir una adjudicación conservando su historial",
    dependencies=[
        Depends(require_permission("purchase_requests:read")),
        Depends(require_permission("purchase_quotations:read")),
        Depends(require_permission("purchase_quotations:select")),
    ],
)
async def revoke_consolidation_award(
    consolidation_id: uuid.UUID,
    award_id: uuid.UUID,
    payload: PurchaseConsolidationAwardRevoke,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    adjudication: PurchaseConsolidationAdjudicationUseCases = Depends(
        get_purchase_consolidation_adjudication_use_cases
    ),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseConsolidationAwardBoardResponse:
    company_id = request_company_id(request)
    item = await consolidations.get(company_id, consolidation_id)
    await _assert_consolidation_scope(session, current, company_id, item)
    award = await adjudication.revoke_award(
        company_id=company_id,
        consolidation_id=consolidation_id,
        award_id=award_id,
        actor_id=current.id,
        reason=payload.reason,
    )
    await audit.record(
        action="REVOKE_AWARD",
        user_id=current.id,
        company_id=company_id,
        branch_id=None,
        resource_type="purchase_consolidation_awards",
        resource_id=str(award.id),
        after_state=_award_audit_state(award),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return _award_board_response(await adjudication.get_board(company_id, consolidation_id))


@router.post(
    "/purchase-consolidations/{consolidation_id}/purchase-quotations",
    response_model=PurchaseQuotationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Preparar RFQ de proveedor desde un consolidado",
    dependencies=[
        Depends(require_permission("purchase_requests:read")),
        Depends(require_permission("purchase_quotations:manage")),
    ],
)
async def create_consolidation_quotation(
    consolidation_id: uuid.UUID,
    payload: PurchaseQuotationFromConsolidationCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    consolidations: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    quotations: PurchaseQuotationUseCases = Depends(get_purchase_quotation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseQuotationResponse:
    company_id = request_company_id(request)
    consolidation = await consolidations.get(company_id, consolidation_id)
    await _assert_consolidation_scope(session, current, company_id, consolidation)
    created = await quotations.create_from_consolidation(
        company_id=company_id,
        created_by_id=current.id,
        consolidation=consolidation,
        supplier_id=payload.supplier_id,
        currency=payload.currency,
        line_ids=payload.consolidation_line_ids,
        notes=payload.notes,
    )
    await audit.record(
        action="CREATE",
        user_id=current.id,
        company_id=company_id,
        branch_id=None,
        resource_type="purchase_quotations",
        resource_id=str(created.id),
        after_state={
            "id": str(created.id),
            "code": created.code,
            "supplier_id": created.supplier_id,
            "consolidation_id": str(created.consolidation_id),
            "consolidation_code": created.consolidation_code,
            "version_number": created.version_number,
            "sent_at": created.sent_at.isoformat() if created.sent_at else None,
            "lines": [
                {
                    "product_id": detail.product_id,
                    "unit_id": detail.unit_id,
                    "quantity": str(detail.quantity),
                    "snapshot": {
                        "product_sku": snapshot.product_sku,
                        "product_name": snapshot.product_name,
                        "unit_name": snapshot.unit_name,
                        "branch_quantity": str(snapshot.branch_quantity),
                        "central_quantity": str(snapshot.central_quantity),
                        "sources": [
                            {
                                "request_id": str(source.purchase_request_id),
                                "request_detail_id": str(source.purchase_request_detail_id),
                                "request_code": source.request_code,
                                "branch_name": source.branch_name,
                                "warehouse_name": source.warehouse_name,
                                "requester_name": source.requester_name,
                                "required_date": source.required_date.isoformat()
                                if source.required_date
                                else None,
                                "included_quantity": str(source.included_quantity),
                            }
                            for source in snapshot.sources
                        ],
                    },
                }
                for detail, snapshot in zip(created.details, created.snapshots, strict=True)
            ],
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return PurchaseQuotationResponse.model_validate(created)


@router.get(
    "/purchase-consolidations/{consolidation_id}/inventory-snapshot",
    response_model=PurchaseConsolidationInventorySnapshotResponse,
    summary="Consultar saldos actuales de inventario para la bodega central",
    dependencies=[
        Depends(require_permission("purchase_requests:read")),
        Depends(require_permission("inventory:read")),
    ],
)
async def get_consolidation_inventory_snapshot(
    consolidation_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    inventory: InventoryUseCases = Depends(get_inventory_use_cases),
) -> PurchaseConsolidationInventorySnapshotResponse:
    company_id = request_company_id(request)
    item = await use_cases.get(company_id, consolidation_id)
    await _assert_consolidation_scope(session, current, company_id, item)
    if item.central_warehouse_id is None:
        raise HTTPException(
            status_code=409,
            detail="Selecciona una bodega central antes de consultar sus existencias.",
        )
    product_ids = tuple(sorted({line.product_id for line in item.lines}))
    snapshots = await inventory.product_stock_snapshot(
        company_id=company_id,
        warehouse_id=item.central_warehouse_id,
        product_ids=product_ids,
    )
    return PurchaseConsolidationInventorySnapshotResponse(
        warehouse_id=item.central_warehouse_id,
        checked_at=datetime.now(UTC),
        reservation_data_available=False,
        items=tuple(snapshots),
    )


@router.post(
    "/purchase-consolidations/{consolidation_id}/requests",
    response_model=PurchaseConsolidationResponse,
    summary="Agregar solicitudes aprobadas al borrador",
    dependencies=[Depends(require_permission("purchase_requests:manage"))],
)
async def add_requests(
    consolidation_id: uuid.UUID,
    payload: PurchaseConsolidationAddRequests,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseConsolidationResponse:
    company_id = request_company_id(request)
    before = await use_cases.get(company_id, consolidation_id)
    await _assert_consolidation_scope(session, current, company_id, before)
    await _assert_request_scope(
        session=session,
        current=current,
        company_id=company_id,
        use_cases=use_cases,
        request_ids=payload.request_ids,
    )
    updated = await use_cases.add_requests(
        company_id=company_id,
        consolidation_id=consolidation_id,
        actor_id=current.id,
        request_ids=payload.request_ids,
        reason=payload.reason,
    )
    await audit.record(
        action="UPDATE",
        user_id=current.id,
        company_id=company_id,
        branch_id=None,
        resource_type="purchase_consolidations",
        resource_id=str(updated.id),
        before_state=_audit_state(before),
        after_state=_audit_state(updated),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return _response(updated)


@router.put(
    "/purchase-consolidations/{consolidation_id}",
    response_model=PurchaseConsolidationResponse,
    summary="Editar cantidades del consolidado en borrador",
    dependencies=[Depends(require_permission("purchase_requests:manage"))],
)
async def update_consolidation(
    consolidation_id: uuid.UUID,
    payload: PurchaseConsolidationUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseConsolidationResponse:
    company_id = request_company_id(request)
    before = await use_cases.get(company_id, consolidation_id)
    await _assert_consolidation_scope(session, current, company_id, before)
    central_warehouse_was_provided = "central_warehouse_id" in payload.model_fields_set
    if payload.central_warehouse_id is not None:
        await _resolve_warehouse_branch(session, current, company_id, payload.central_warehouse_id)
    updated = await use_cases.update_draft(
        company_id=company_id,
        consolidation_id=consolidation_id,
        actor_id=current.id,
        change_reason=payload.change_reason,
        source_changes=tuple(
            SourceQuantityChange(
                source_id=item.source_id,
                included_quantity=item.included_quantity,
                reason=item.reason,
                demand_level=item.demand_level,
                update_demand_level="demand_level" in item.model_fields_set,
            )
            for item in payload.source_changes
        ),
        central_demands=tuple(
            CentralDemandDraft(
                product_id=item.product_id,
                quantity=item.quantity,
                reason=item.reason,
                line_id=item.line_id,
            )
            for item in payload.central_demands
        ),
        notes=payload.notes,
        central_warehouse_id=payload.central_warehouse_id,
        update_central_warehouse=central_warehouse_was_provided,
    )
    await audit.record(
        action="UPDATE",
        user_id=current.id,
        company_id=company_id,
        branch_id=None,
        resource_type="purchase_consolidations",
        resource_id=str(updated.id),
        before_state=_audit_state(before),
        after_state=_audit_state(updated),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return _response(updated)


@router.post(
    "/purchase-consolidations/{consolidation_id}/cancel",
    response_model=PurchaseConsolidationResponse,
    summary="Cancelar borrador de consolidado",
    dependencies=[Depends(require_permission("purchase_requests:manage"))],
)
async def cancel_consolidation(
    consolidation_id: uuid.UUID,
    payload: PurchaseConsolidationCancel,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseConsolidationResponse:
    company_id = request_company_id(request)
    before = await use_cases.get(company_id, consolidation_id)
    await _assert_consolidation_scope(session, current, company_id, before)
    updated = await use_cases.cancel(
        company_id, consolidation_id, actor_id=current.id, reason=payload.reason
    )
    await audit.record(
        action="CANCEL",
        user_id=current.id,
        company_id=company_id,
        branch_id=None,
        resource_type="purchase_consolidations",
        resource_id=str(updated.id),
        before_state=_audit_state(before),
        after_state=_audit_state(updated),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return _response(updated)


@router.post(
    "/purchase-consolidations/{consolidation_id}/close",
    response_model=PurchaseConsolidationResponse,
    summary="Cerrar consolidado adjudicado o cubierto fuera del consolidado",
    dependencies=[Depends(require_permission("purchase_requests:manage"))],
)
async def close_consolidation(
    consolidation_id: uuid.UUID,
    payload: PurchaseConsolidationClose,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseConsolidationUseCases = Depends(get_purchase_consolidation_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> PurchaseConsolidationResponse:
    company_id = request_company_id(request)
    before = await use_cases.get(company_id, consolidation_id)
    await _assert_consolidation_scope(session, current, company_id, before)
    updated = await use_cases.close(
        company_id,
        consolidation_id,
        actor_id=current.id,
        reason=payload.reason,
        covered_outside_consolidation=payload.covered_outside_consolidation,
    )
    closure_event = next(
        (event for event in reversed(updated.events) if event.action == "closed"), None
    )
    await audit.record(
        action="CLOSE",
        user_id=current.id,
        company_id=company_id,
        branch_id=None,
        resource_type="purchase_consolidations",
        resource_id=str(updated.id),
        before_state=_audit_state(before),
        after_state=_audit_state(updated),
        metadata={
            "reason": payload.reason,
            "closure_details": closure_event.changes if closure_event else {},
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return _response(updated)
