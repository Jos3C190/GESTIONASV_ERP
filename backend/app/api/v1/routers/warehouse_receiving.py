"""Warehouse work queue and receipt confirmation under explicit operational grants."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request

from app.api.v1.company_access import request_company_id, resolve_document_warehouse_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_purchase_use_cases,
    require_permission,
)
from app.api.v1.routers.inventory import _authorize_warehouse, _execute
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.purchase import PurchaseVerify
from app.api.v1.schemas.warehouse_receiving import WarehouseReceiptOut
from app.application.audit.audit_service import AuditService
from app.application.purchases import PurchaseUseCases
from app.application.purchases.warehouse_receiving import WarehouseReceiving
from app.domain.entities.purchase import PurchaseVerificationLine
from app.infrastructure.repositories.warehouse_receiving_repository import (
    SqlAlchemyWarehouseReceivingRepository,
)

router = APIRouter(
    prefix="/warehouse-receipts",
    tags=["warehouse-receipts"],
    dependencies=[Depends(require_permission("inventory:warehouse_receipts"))],
)


def _reads(session: SessionDep) -> WarehouseReceiving:
    return WarehouseReceiving(SqlAlchemyWarehouseReceivingRepository(session))


@router.get("", response_model=Page[WarehouseReceiptOut])
async def list_pending(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    warehouse_id: uuid.UUID,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
) -> Page[WarehouseReceiptOut]:
    company_id = await _authorize_warehouse(request, session, current, warehouse_id)
    items, total = await _reads(session).list_pending(
        company_id, warehouse_id, skip=(page - 1) * size, limit=size
    )
    return Page(
        items=[WarehouseReceiptOut.model_validate(item) for item in items],
        meta=PageMeta(page=page, size=size, total=total, pages=(total + size - 1) // size),
    )


@router.post(
    "/{purchase_id}/verify",
    response_model=WarehouseReceiptOut,
    dependencies=[
        Depends(require_permission("inventory:receive")),
        Depends(require_permission("locations.view")),
    ],
)
async def verify_receipt(
    purchase_id: uuid.UUID,
    payload: PurchaseVerify,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    use_cases: PurchaseUseCases = Depends(get_purchase_use_cases),
    audit: AuditService = Depends(get_audit_service),
) -> WarehouseReceiptOut:
    company_id = request_company_id(request)
    before = await use_cases.get_purchase(company_id, purchase_id)
    branch_id = await resolve_document_warehouse_scope(
        session,
        current,
        company_id,
        document_branch_id=before.branch_id,
        warehouse_id=before.warehouse_id,
    )
    async with session.begin_nested():
        updated = await _execute(
            session,
            use_cases.verify_purchase(
                company_id,
                purchase_id,
                actor_id=current.id,
                lines=tuple(
                    PurchaseVerificationLine(
                        line.purchase_detail_id, line.quantity_accepted, line.inventory_location_id
                    )
                    for line in payload.lines
                ),
                valuation_conversion=payload.valuation_conversion.to_domain()
                if payload.valuation_conversion
                else before.valuation_conversion,
            ),
        )
        await audit.record(
            action="VERIFY",
            user_id=current.id,
            company_id=company_id,
            branch_id=branch_id,
            resource_type="purchases",
            resource_id=str(purchase_id),
            before_state={"status": before.status.value},
            after_state={
                "status": updated.status.value,
                "inventory_movement_id": str(updated.inventory_movement_id)
                if updated.inventory_movement_id
                else None,
                "quantities": [
                    {"id": str(line.id), "accepted": str(line.quantity_accepted)}
                    for line in updated.details
                ],
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            required=True,
        )
    projected = await _reads(session).get_receipt(company_id, purchase_id)
    return WarehouseReceiptOut.model_validate(projected)
