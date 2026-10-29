"""Authenticated exports of the complete, authorized Kardex query."""

import uuid
from datetime import date
from functools import partial
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_inventory_kardex_read_use_cases,
    require_permission,
)
from app.api.v1.routers.inventory_kardex import physical_kardex, reconcile_inventory, valued_kardex
from app.application.inventory.kardex_read import InventoryKardexReadUseCases
from app.application.inventory.kardex_reports import kardex_report
from app.infrastructure.procurement_report_renderer import render_pdf, render_xlsx

router = APIRouter(prefix="/inventory/kardex", tags=["inventory kardex reports"])
Cases = Annotated[InventoryKardexReadUseCases, Depends(get_inventory_kardex_read_use_cases)]
MAX_REPORT_ROWS = 5000


async def _export(fetch, kind: str, export_format: str, filters: dict):
    first = await fetch(page=1, page_size=200)
    if first.total > MAX_REPORT_ROWS:
        raise HTTPException(
            422,
            "El reporte supera 5,000 filas. Reduce el período o aplica filtros para descargarlo completo.",
        )
    data = first.model_dump()
    key = "entries" if kind == "valuation" else "items"
    for page in range(2, (first.total + 199) // 200 + 1):
        part = await fetch(page=page, page_size=200)
        data[key].extend(part.model_dump()[key])
    report = kardex_report(kind, data, filters)
    payload = await run_in_threadpool(render_pdf if export_format == "pdf" else render_xlsx, report)
    return Response(
        payload,
        media_type="application/pdf"
        if export_format == "pdf"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{report.code}.{export_format}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/physical/export", dependencies=[Depends(require_permission("inventory:read"))])
async def export_physical(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    kardex: Cases,
    warehouse_id: uuid.UUID,
    inventory_item_id: uuid.UUID,
    period_from: date,
    period_to: date,
    movement_type: str | None = Query(None, max_length=24),
    lot_code: str | None = Query(None, max_length=120),
    source_reference: str | None = Query(None, max_length=160),
    export_format: Literal["pdf", "xlsx"] = Query("pdf", alias="format"),
):
    return await _export(
        partial(
            physical_kardex,
            request=request,
            session=session,
            current=current,
            kardex=kardex,
            warehouse_id=warehouse_id,
            inventory_item_id=inventory_item_id,
            period_from=period_from,
            period_to=period_to,
            movement_type=movement_type,
            lot_code=lot_code,
            source_reference=source_reference,
        ),
        "physical",
        export_format,
        {
            "Tipo de movimiento": movement_type,
            "Lote filtrado": lot_code,
            "Documento filtrado": source_reference,
        },
    )


@router.get("/valuation/export", dependencies=[Depends(require_permission("inventory:valuation"))])
async def export_valued(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    kardex: Cases,
    inventory_item_id: uuid.UUID,
    period_from: date,
    period_to: date,
    export_format: Literal["pdf", "xlsx"] = Query("pdf", alias="format"),
):
    return await _export(
        partial(
            valued_kardex,
            request=request,
            session=session,
            current=current,
            kardex=kardex,
            inventory_item_id=inventory_item_id,
            period_from=period_from,
            period_to=period_to,
        ),
        "valuation",
        export_format,
        {},
    )


@router.get(
    "/reconciliation/export", dependencies=[Depends(require_permission("inventory:valuation"))]
)
async def export_reconciliation(
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    kardex: Cases,
    as_of: date | None = None,
    q: str = Query("", max_length=120),
    difference_only: bool = False,
    export_format: Literal["pdf", "xlsx"] = Query("pdf", alias="format"),
):
    return await _export(
        partial(
            reconcile_inventory,
            request=request,
            session=session,
            current=current,
            kardex=kardex,
            as_of=as_of,
            q=q,
            difference_only=difference_only,
        ),
        "reconciliation",
        export_format,
        {
            "Producto buscado": q,
            "Estado": "Con diferencia o sin base verificable" if difference_only else "Todos",
        },
    )
