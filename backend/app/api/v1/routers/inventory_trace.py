"""Authenticated issuance and public read-only resolution of inventory trace links."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.company_access import authorize_handling_unit_branch_scope, effective_company_id
from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.schemas.inventory_trace import (
    PublicHandlingUnitTraceOut,
    PublicTraceResolveIn,
    TraceCapabilityCreateIn,
    TraceCapabilityOut,
    TraceCapabilityRevokeOut,
)
from app.application.audit.audit_service import AuditService
from app.application.inventory import InventoryUseCases
from app.infrastructure.repositories.inventory_label_repository import (
    SqlAlchemyInventoryLabelRepository,
)
from app.infrastructure.repositories.inventory_repository import SqlAlchemyInventoryRepository
from app.infrastructure.repositories.inventory_trace_capability_repository import (
    SqlAlchemyInventoryTraceCapabilityRepository,
)
from app.infrastructure.repositories.inventory_valuation_repository import (
    SqlAlchemyInventoryValuationRepository,
)

router = APIRouter(
    prefix="/inventory/trace-capabilities",
    tags=["inventory trace capabilities"],
    dependencies=[Depends(require_permission("inventory:read"))],
)

public_router = APIRouter(prefix="/inventory/public-traces", tags=["public inventory trace"])


async def _authorize_unit(
    request: Request, session: SessionDep, current: CurrentUser, handling_unit_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID | None]:
    company_id = effective_company_id(request)
    await SqlAlchemyInventoryValuationRepository(session).lock(company_id)
    _, branch_id = await authorize_handling_unit_branch_scope(
        session, current, company_id, handling_unit_id
    )
    return company_id, branch_id


@router.post("", response_model=TraceCapabilityOut)
async def create_trace_capability(
    body: TraceCapabilityCreateIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> TraceCapabilityOut:
    company_id, branch_id = await _authorize_unit(request, session, current, body.handling_unit_id)
    # A QR is a read-only trace link, not a physical receipt label. Preserve
    # receipt/retaceo readiness for lot-linked units, while allowing legacy units
    # with no receipt lot to show their trace with an explicitly unknown origin.
    trace = await InventoryUseCases(
        SqlAlchemyInventoryRepository(session)
    ).get_handling_unit_traceability(
        company_id=company_id,
        handling_unit_id=body.handling_unit_id,
    )
    if trace is None:
        raise HTTPException(404, "Unidad logística no encontrada.")
    if trace["handling_unit"].get("receipt_lot_id") is not None:
        await SqlAlchemyInventoryLabelRepository(session).preview(
            company_id=company_id,
            handling_unit_id=body.handling_unit_id,
        )
    repository = SqlAlchemyInventoryTraceCapabilityRepository(session)
    issued = await repository.create(
        company_id=company_id,
        handling_unit_id=body.handling_unit_id,
        actor_id=current.id,
    )
    if issued is None:
        raise HTTPException(404, "Unidad logística no encontrada.")
    capability, token = issued
    await audit.record(
        action="CREATE_PUBLIC_INVENTORY_TRACE",
        user_id=current.id,
        company_id=company_id,
        branch_id=branch_id,
        resource_type="inventory_trace_capabilities",
        resource_id=str(capability.id),
        after_state={"handling_unit_id": str(body.handling_unit_id)},
        required=True,
    )
    return TraceCapabilityOut(token=token, created_at=capability.created_at)


@router.post(
    "/{handling_unit_id}/revoke",
    response_model=TraceCapabilityRevokeOut,
    dependencies=[Depends(require_permission("inventory:receive"))],
)
async def revoke_trace_capabilities(
    handling_unit_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> TraceCapabilityRevokeOut:
    company_id, branch_id = await _authorize_unit(request, session, current, handling_unit_id)
    revoked_count = await SqlAlchemyInventoryTraceCapabilityRepository(session).revoke_all(
        company_id=company_id,
        handling_unit_id=handling_unit_id,
        actor_id=current.id,
    )
    if revoked_count:
        await audit.record(
            action="REVOKE_PUBLIC_INVENTORY_TRACE",
            user_id=current.id,
            company_id=company_id,
            branch_id=branch_id,
            resource_type="inventory_handling_units",
            resource_id=str(handling_unit_id),
            after_state={"revoked_capability_count": revoked_count},
            required=True,
        )
    return TraceCapabilityRevokeOut(revoked_count=revoked_count)


@public_router.post("/resolve", response_model=PublicHandlingUnitTraceOut)
async def resolve_public_trace(
    body: PublicTraceResolveIn,
    session: SessionDep,
) -> PublicHandlingUnitTraceOut:
    repository = SqlAlchemyInventoryTraceCapabilityRepository(session)
    capability = await repository.get_active(body.token)
    if capability is None:
        raise HTTPException(404, "El enlace no es válido o fue revocado.")

    trace = await InventoryUseCases(
        SqlAlchemyInventoryRepository(session)
    ).get_handling_unit_traceability(
        company_id=capability.company_id,
        handling_unit_id=capability.handling_unit_id,
    )
    if trace is None:
        raise HTTPException(404, "El enlace no es válido o fue revocado.")

    unit = trace["handling_unit"]
    origin = trace["origin"]
    return PublicHandlingUnitTraceOut.model_validate(
        {
            "handling_unit_code": unit["code"],
            "product_sku": trace["product_sku"],
            "product_name": trace["product_name"],
            "quantity_base": unit["quantity_base"],
            "base_unit_symbol": trace["base_unit_symbol"],
            "lot_code": unit["lot_code"],
            "receipt_lot_code": unit.get("receipt_lot_code"),
            "receipt_lot_header_code": unit.get("receipt_lot_header_code"),
            "expiry_date": unit["expiry_date"],
            "stock_status": unit["stock_status"],
            "warehouse_code": trace["warehouse_code"],
            "warehouse_name": trace["warehouse_name"],
            "location_code": trace["location_code"],
            "origin": {
                "supplier_name": origin["supplier_name"],
                "purchase_code": origin["purchase_code"],
                "purchase_order_code": origin["purchase_order_code"],
                "received_at": origin["received_at"],
                "consolidation_code": origin["consolidation_code"],
            },
            "movements": [
                {
                    "movement_type": movement["movement_type"],
                    "posted_at": movement["posted_at"],
                    "from_warehouse_code": movement["from_warehouse_code"],
                    "from_warehouse_name": movement["from_warehouse_name"],
                    "from_location_code": movement["from_location_code"],
                    "from_stock_status": movement["from_stock_status"],
                    "to_warehouse_code": movement["to_warehouse_code"],
                    "to_warehouse_name": movement["to_warehouse_name"],
                    "to_location_code": movement["to_location_code"],
                    "to_stock_status": movement["to_stock_status"],
                    "quantity_base": movement["quantity_base"],
                }
                for movement in trace["movements"]
            ],
        }
    )


__all__ = ["public_router", "router"]
