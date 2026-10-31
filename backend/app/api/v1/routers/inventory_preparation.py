import uuid

from fastapi import APIRouter, Depends, Query, Request

from app.api.v1.company_access import authorize_handling_unit_branch_scope, effective_company_id
from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.routers.inventory import InventoryBoundaryError, _authorize_warehouse
from app.api.v1.schemas.common import Page, PageMeta
from app.api.v1.schemas.inventory_preparation import (
    PlacementCommandIn,
    PreparationActionOut,
    PreparationCommandIn,
    PreparationUnitOut,
)
from app.application.audit.audit_service import AuditService
from app.domain.entities.inventory import InventoryOperationError
from app.infrastructure.repositories.inventory_preparation_repository import (
    SqlAlchemyInventoryPreparationRepository,
)

router = APIRouter(
    prefix="/inventory/preparation",
    tags=["warehouse preparation"],
    dependencies=[
        Depends(require_permission("inventory:warehouse_receipts")),
        Depends(require_permission("inventory:read")),
    ],
)


@router.get("", response_model=Page[PreparationUnitOut])
async def list_pending(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    warehouse_id: uuid.UUID,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    search: str = Query("", max_length=120),
) -> Page[PreparationUnitOut]:
    company_id = await _authorize_warehouse(request, session, current, warehouse_id)
    rows, total = await SqlAlchemyInventoryPreparationRepository(session).list_pending(
        company_id, warehouse_id, skip=(page - 1) * size, limit=size, search=search
    )
    return Page(
        items=[PreparationUnitOut.model_validate(row) for row in rows],
        meta=PageMeta(page=page, size=size, total=total, pages=(total + size - 1) // size),
    )


async def _command(
    action: str,
    unit_id: uuid.UUID,
    payload: PreparationCommandIn | PlacementCommandIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService,
) -> PreparationActionOut:
    company_id = effective_company_id(request)
    _, branch_id = await authorize_handling_unit_branch_scope(session, current, company_id, unit_id)
    try:
        async with session.begin_nested():
            result, created = await SqlAlchemyInventoryPreparationRepository(session).execute(
                company_id=company_id,
                unit_id=unit_id,
                actor_id=current.id,
                action=action,
                command=payload.model_dump(mode="json"),
            )
            if created:
                await audit.record(
                    action="PLACE_RECEIPT" if action == "place" else "SPLIT_PREPARATION",
                    user_id=current.id,
                    company_id=company_id,
                    branch_id=branch_id,
                    resource_type="inventory_handling_units",
                    resource_id=str(unit_id),
                    after_state=result,
                    required=True,
                )
    except InventoryOperationError as exc:
        raise InventoryBoundaryError(
            exc.message, code=exc.code, status_code=exc.status_code
        ) from exc
    return PreparationActionOut.model_validate(result)


@router.post(
    "/{unit_id}/split",
    response_model=PreparationActionOut,
    dependencies=[
        Depends(require_permission("inventory:receive")),
        Depends(require_permission("inventory:move")),
    ],
)
async def split(
    unit_id: uuid.UUID,
    payload: PreparationCommandIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> PreparationActionOut:
    return await _command("split", unit_id, payload, request, session, current, audit)


@router.post(
    "/{unit_id}/place",
    response_model=PreparationActionOut,
    dependencies=[
        Depends(require_permission("inventory:receive")),
        Depends(require_permission("inventory:move")),
    ],
)
async def place(
    unit_id: uuid.UUID,
    payload: PlacementCommandIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> PreparationActionOut:
    return await _command("place", unit_id, payload, request, session, current, audit)
