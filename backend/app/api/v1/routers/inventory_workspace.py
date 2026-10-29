"""Warehouse consultation and administrator-only individual opening."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.encoders import jsonable_encoder

from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.routers.inventory import _authorize_warehouse, _execute
from app.api.v1.schemas.inventory import MovementOut
from app.api.v1.schemas.inventory_adjustment import InventoryAdjustmentOptions
from app.api.v1.schemas.inventory_workspace import ProductOpeningIn, WarehouseStockPage
from app.application.audit.audit_service import AuditService
from app.application.inventory.workspace import InventoryWorkspace
from app.infrastructure.repositories.inventory_workspace_repository import SqlAlchemyInventoryWorkspaceRepository
from app.infrastructure.repositories.inventory_adjustment_repository import SqlAlchemyInventoryAdjustmentRepository

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/warehouses/{warehouse_id}/workspace-items", response_model=InventoryAdjustmentOptions,
            dependencies=[Depends(require_permission("inventory:read"))])
async def items(warehouse_id: uuid.UUID, request: Request, session: SessionDep,
                current: CurrentUser, q: str = Query("", max_length=120), offset: int = Query(0, ge=0)) -> InventoryAdjustmentOptions:
    company_id = await _authorize_warehouse(request, session, current, warehouse_id)
    result = await SqlAlchemyInventoryAdjustmentRepository(session).list_options(
        company_id=company_id, warehouse_id=warehouse_id, q=q, offset=offset,
        limit=20, include_locations=False)
    return InventoryAdjustmentOptions.model_validate(result)


@router.get("/warehouses/{warehouse_id}/stock", response_model=WarehouseStockPage,
            dependencies=[Depends(require_permission("inventory:read"))])
async def stock(warehouse_id: uuid.UUID, request: Request, session: SessionDep,
                current: CurrentUser, q: str = Query("", max_length=120),
                location_id: uuid.UUID | None = None, stock_status: str | None = None,
                page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=100)) -> WarehouseStockPage:
    company_id = await _authorize_warehouse(request, session, current, warehouse_id)
    result = await InventoryWorkspace(SqlAlchemyInventoryWorkspaceRepository(session)).stock(
        company_id=company_id, warehouse_id=warehouse_id, q=q, location_id=location_id,
        stock_status=stock_status, page=page, size=size)
    return WarehouseStockPage.model_validate(result)


@router.post("/product-opening", response_model=MovementOut,
             dependencies=[Depends(require_permission("inventory:valuation")),
                           Depends(require_permission("inventory:receive"))])
async def open_product(body: ProductOpeningIn, request: Request, session: SessionDep,
                       current: CurrentUser,
                       audit: Annotated[AuditService, Depends(get_audit_service)]) -> MovementOut:
    company_id = await _authorize_warehouse(request, session, current, body.warehouse_id)
    result = await _execute(session, InventoryWorkspace(SqlAlchemyInventoryWorkspaceRepository(session)).open_product(
        company_id=company_id, actor_id=current.id, command=body.model_dump()))
    response = MovementOut.model_validate(result)
    if result["created"]:
        await audit.record(action="CREATE", user_id=current.id, company_id=company_id,
            resource_type="inventory_product_opening", resource_id=str(response.id),
            after_state=jsonable_encoder(body.model_dump(exclude={"idempotency_key"})), required=True)
    return response
