"""HTTP authorization and DTO boundary for Kardex read queries."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.v1.company_access import (
    assigned_warehouse_ids,
    authorize_warehouse_assignment,
    effective_company_id,
    get_branch_context,
    require_company_wide_scope,
    require_resource_company,
    resolve_branch_scope,
)
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_inventory_kardex_read_use_cases,
    require_permission,
)
from app.api.v1.schemas.inventory_kardex import (
    KardexContextOut,
    KardexItemOptionOut,
    KardexReconciliationOut,
    KardexReconciliationRowOut,
    PhysicalKardexOut,
    PhysicalKardexRowOut,
    ValuedKardexOut,
)
from app.api.v1.schemas.inventory_valuation import ValuationEntryOut, ValuationSettingOut
from app.application.inventory.kardex_read import InventoryKardexReadUseCases
from app.domain.entities.inventory_kardex import LOCAL_TZ

router = APIRouter(prefix="/inventory/kardex", tags=["inventory kardex"])


async def _authorize_warehouse(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    warehouse_id: uuid.UUID,
    kardex: InventoryKardexReadUseCases,
) -> uuid.UUID:
    scope = await kardex.get_warehouse_scope(warehouse_id=warehouse_id)
    if scope is None:
        raise HTTPException(404, "Bodega no encontrada.")
    company_id, branch_id = scope
    require_resource_company(request, company_id, not_found_detail="Bodega no encontrada.")
    await resolve_branch_scope(session, current, company_id, branch_id)
    await authorize_warehouse_assignment(session, current, company_id, warehouse_id)
    return company_id


async def _authorize_company_values(
    session: SessionDep, current: CurrentUser, company_id: uuid.UUID
) -> None:
    await require_company_wide_scope(session, current, company_id)
    if await assigned_warehouse_ids(session, current, company_id) is not None:
        raise HTTPException(
            403, "Esta consulta requiere alcance de todas las bodegas de la empresa."
        )


@router.get(
    "/items",
    response_model=list[KardexItemOptionOut],
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def search_kardex_items(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    warehouse_id: uuid.UUID,
    kardex: Annotated[InventoryKardexReadUseCases, Depends(get_inventory_kardex_read_use_cases)],
    q: str = Query("", max_length=120),
) -> list[KardexItemOptionOut]:
    company_id = await _authorize_warehouse(request, session, current, warehouse_id, kardex)
    rows = await kardex.search_items(company_id=company_id, warehouse_id=warehouse_id, query=q)
    return [KardexItemOptionOut.model_validate(row) for row in rows]


@router.get(
    "/physical",
    response_model=PhysicalKardexOut,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def physical_kardex(
    warehouse_id: uuid.UUID,
    inventory_item_id: uuid.UUID,
    period_from: date,
    period_to: date,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    kardex: Annotated[InventoryKardexReadUseCases, Depends(get_inventory_kardex_read_use_cases)],
    movement_type: str | None = Query(None, min_length=1, max_length=24),
    lot_code: str | None = Query(None, max_length=120),
    source_reference: str | None = Query(None, min_length=1, max_length=160),
    page: int = Query(1, ge=1, le=100000),
    page_size: int = Query(50, ge=1, le=200),
) -> PhysicalKardexOut:
    if period_from > period_to:
        raise HTTPException(422, "La fecha inicial debe ser anterior o igual a la final.")
    company_id = await _authorize_warehouse(request, session, current, warehouse_id, kardex)
    context = await get_branch_context(session, current, company_id)
    assigned = await assigned_warehouse_ids(session, current, company_id)
    data = await kardex.physical_kardex(
        company_id=company_id,
        warehouse_id=warehouse_id,
        inventory_item_id=inventory_item_id,
        period_from=period_from,
        period_to=period_to,
        movement_type=movement_type,
        lot_code=lot_code,
        source_reference=source_reference,
        page=page,
        page_size=page_size,
        access_all_branches=context.access_all_branches,
        accessible_branch_ids={branch.id for branch in context.branches},
        accessible_warehouse_ids=set(assigned) if assigned is not None else None,
    )
    if data is None:
        raise HTTPException(404, "Artículo de inventario no encontrado.")
    items = []
    for row in data["items"]:
        payload = {field: row[field] for field in PhysicalKardexRowOut.model_fields if field in row}
        items.append(PhysicalKardexRowOut(**payload))
    cut = data["cut_opened_at"]
    basis = (
        f"Saldo reconstruido desde el corte físico de valoración del "
        f"{cut.astimezone(LOCAL_TZ):%d/%m/%Y %H:%M} y los movimientos posteriores."
        if cut is not None
        else "No hay corte físico aprobado. Los movimientos se muestran, pero no se inventan saldos históricos."
    )
    return PhysicalKardexOut.model_validate(
        {
            "context": await kardex.context(
                company_id=company_id, item_id=inventory_item_id, warehouse_id=warehouse_id
            ),
            "warehouse_id": warehouse_id,
            "inventory_item_id": inventory_item_id,
            "period_from": period_from,
            "period_to": period_to,
            "balance_basis": basis,
            "opening_known": data["opening_known"],
            "opening_quantity": data["opening_quantity"],
            "incoming_quantity": data["incoming_quantity"],
            "outgoing_quantity": data["outgoing_quantity"],
            "closing_known": data["closing_known"],
            "closing_quantity": data["closing_quantity"],
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": data["total"],
        }
    )


@router.get(
    "/reconciliation",
    response_model=KardexReconciliationOut,
    dependencies=[Depends(require_permission("inventory:valuation"))],
)
async def reconcile_inventory(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    kardex: Annotated[InventoryKardexReadUseCases, Depends(get_inventory_kardex_read_use_cases)],
    page: int = Query(1, ge=1, le=100000),
    page_size: int = Query(50, ge=1, le=200),
    as_of: date | None = None,
    q: str = Query("", max_length=120),
    difference_only: bool = False,
) -> KardexReconciliationOut:
    company_id = effective_company_id(request)
    await _authorize_company_values(session, current, company_id)
    if as_of and as_of > datetime.now(LOCAL_TZ).date():
        raise HTTPException(422, "El corte no puede estar en el futuro.")
    data = await kardex.reconciliation(
        company_id=company_id,
        page=page,
        page_size=page_size,
        as_of=as_of,
        query=q,
        difference_only=difference_only,
    )
    return KardexReconciliationOut(
        context=KardexContextOut.model_validate(await kardex.context(company_id=company_id)),
        **{
            key: data[key]
            for key in (
                "as_of",
                "generated_at",
                "balance_known",
                "inventory_value",
                "reconciled_items",
                "discrepant_items",
                "unvalued_items",
            )
        },
        valuation_enabled=data["valuation_enabled"],
        currency=data["currency"],
        items=[KardexReconciliationRowOut(**row) for row in data["items"]],
        page=data["page"],
        page_size=data["page_size"],
        total=data["total"],
    )


@router.get(
    "/valuation",
    response_model=ValuedKardexOut,
    dependencies=[Depends(require_permission("inventory:valuation"))],
)
async def valued_kardex(
    inventory_item_id: uuid.UUID,
    period_from: date,
    period_to: date,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    kardex: Annotated[InventoryKardexReadUseCases, Depends(get_inventory_kardex_read_use_cases)],
    page: int = Query(1, ge=1, le=100000),
    page_size: int = Query(50, ge=1, le=200),
) -> ValuedKardexOut:
    if period_from > period_to:
        raise HTTPException(422, "La fecha inicial debe ser anterior o igual a la final.")
    company_id = effective_company_id(request)
    await _authorize_company_values(session, current, company_id)
    data = await kardex.valued_kardex(
        company_id=company_id,
        inventory_item_id=inventory_item_id,
        period_from=period_from,
        period_to=period_to,
        page=page,
        page_size=page_size,
    )
    if data is None:
        raise HTTPException(404, "Artículo de inventario no encontrado.")
    return ValuedKardexOut.model_validate(
        {
            "context": await kardex.context(company_id=company_id, item_id=inventory_item_id),
            "inventory_item_id": inventory_item_id,
            "setting": ValuationSettingOut.model_validate(data["setting"])
            if data["setting"]
            else None,
            "period_from": period_from,
            "period_to": period_to,
            "opening_known": data["opening_known"],
            "opening_quantity": data["opening_quantity"],
            "opening_value": data["opening_value"],
            "closing_known": data["closing_known"],
            "closing_quantity": data["closing_quantity"],
            "closing_value": data["closing_value"],
            "period_value_change": data["period_value_change"],
            "entries": [ValuationEntryOut.model_validate(row) for row in data["entries"]],
            "page": data["page"],
            "page_size": data["page_size"],
            "total": data["total"],
        }
    )
