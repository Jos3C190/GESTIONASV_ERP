"""Vitrina del punto de venta (bloque V6b).

- Crear la vitrina de una sucursal: ``pos:registers_manage``.
- Ver existencias de vitrina: ``pos:sell``, ``pos:showcase`` o ``pos:supervise``.
- Pasar a vitrina y contar la vitrina (merma): ``pos:showcase``.

Toda escritura queda en la bitácora y respeta el alcance por sucursal.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, Field

from app.api.v1.company_access import request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    require_any_permission,
    require_permission,
)
from app.api.v1.routers.pos import _branch_ids
from app.application.audit.audit_service import AuditService
from app.application.pos.showcase import (
    Candidate,
    CountLineInput,
    PosShowcaseService,
    Showcase,
    ShowcaseCount,
    ShowcaseStock,
)

router = APIRouter(prefix="/pos/showcases", tags=["pos"])
Audit = Annotated[AuditService, Depends(get_audit_service)]
CompanyId = Annotated[uuid.UUID, Depends(request_company_id)]

_MANAGE = [Depends(require_permission("pos:registers_manage"))]
_READ = [
    Depends(
        require_any_permission("pos:sell", "pos:showcase", "pos:supervise", "pos:registers_manage")
    )
]
_SHOWCASE = [Depends(require_permission("pos:showcase"))]


def _service(session: SessionDep) -> PosShowcaseService:
    return PosShowcaseService(session)


Service = Annotated[PosShowcaseService, Depends(_service)]


class ShowcaseOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    location_id: uuid.UUID
    location_code: str
    created_at: datetime


class WarehouseOptionOut(BaseModel):
    id: uuid.UUID
    name: str


class ShowcaseCreateIn(BaseModel):
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID


class ShowcaseUnitOut(BaseModel):
    handling_unit_id: uuid.UUID
    code: str
    quantity: Decimal
    lot_code: str | None
    expiry_date: date | None
    opened_at: datetime | None
    expired: bool


class ShowcaseStockOut(BaseModel):
    inventory_item_id: uuid.UUID
    product_name: str
    sku: str
    unit_symbol: str
    quantity: Decimal
    sellable: Decimal
    expired: Decimal
    next_expiry: date | None
    units: list[ShowcaseUnitOut]


class CandidateOut(BaseModel):
    handling_unit_id: uuid.UUID
    code: str
    inventory_item_id: uuid.UUID
    product_name: str
    sku: str
    unit_symbol: str
    quantity: Decimal
    lot_code: str | None
    expiry_date: date | None
    location_code: str


class OpenUnitsIn(BaseModel):
    handling_unit_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=120)


class OpenUnitsOut(BaseModel):
    movement_id: uuid.UUID
    stock: list[ShowcaseStockOut]


class CountLineIn(BaseModel):
    inventory_item_id: uuid.UUID
    counted_quantity: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    reason: str | None = Field(default=None, max_length=200)


class CountIn(BaseModel):
    lines: list[CountLineIn] = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=300)
    idempotency_key: str = Field(min_length=8, max_length=120)


class CountLineOut(BaseModel):
    inventory_item_id: uuid.UUID
    product_name: str
    unit_symbol: str
    system_quantity: Decimal
    counted_quantity: Decimal
    waste_quantity: Decimal
    reason: str | None


class ShowcaseCountOut(BaseModel):
    id: uuid.UUID
    number: int
    code: str
    counted_by_name: str
    counted_at: datetime
    notes: str | None
    waste_cost: Decimal
    movement_id: uuid.UUID | None
    lines: list[CountLineOut]


def _showcase(item: Showcase) -> ShowcaseOut:
    return ShowcaseOut(**item.__dict__)


def _stock(item: ShowcaseStock) -> ShowcaseStockOut:
    return ShowcaseStockOut(
        **{key: value for key, value in item.__dict__.items() if key != "units"},
        units=[ShowcaseUnitOut(**unit.__dict__) for unit in item.units],
    )


def _candidate(item: Candidate) -> CandidateOut:
    return CandidateOut(**item.__dict__)


def _count(item: ShowcaseCount) -> ShowcaseCountOut:
    return ShowcaseCountOut(
        id=item.id,
        number=item.number,
        code=f"CV-{item.number:06d}",
        counted_by_name=item.counted_by_name,
        counted_at=item.counted_at,
        notes=item.notes,
        waste_cost=item.waste_cost.quantize(Decimal("0.01")),
        movement_id=item.movement_id,
        lines=[CountLineOut(**line.__dict__) for line in item.lines],
    )


async def _audit(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    company_id: uuid.UUID,
    branch_id: uuid.UUID,
    resource_type: str,
    resource_id: uuid.UUID,
    after: dict[str, Any],
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=company_id,
        branch_id=branch_id,
        resource_type=resource_type,
        resource_id=str(resource_id),
        before_state=None,
        after_state=after,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get(
    "", response_model=list[ShowcaseOut], summary="Vitrinas de mis sucursales", dependencies=_READ
)
async def list_showcases(
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    service: Service,
    branch_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[ShowcaseOut]:
    branches = await _branch_ids(session, current, company_id, branch_id)
    return [_showcase(item) for item in await service.showcases(company_id, branches)]


@router.get(
    "/warehouse-options",
    response_model=list[WarehouseOptionOut],
    summary="Bodegas de la sucursal donde puede vivir la vitrina",
    dependencies=_MANAGE,
)
async def warehouse_options(
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    service: Service,
    branch_id: Annotated[uuid.UUID, Query()],
) -> list[WarehouseOptionOut]:
    await resolve_branch_scope(session, current, company_id, branch_id)
    return [
        WarehouseOptionOut(id=item.id, name=item.name)
        for item in await service.warehouse_options(company_id, branch_id)
    ]


@router.post(
    "",
    response_model=ShowcaseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear la vitrina de una sucursal",
    dependencies=_MANAGE,
)
async def create_showcase(
    body: ShowcaseCreateIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    service: Service,
    audit: Audit,
) -> ShowcaseOut:
    await resolve_branch_scope(session, current, company_id, body.branch_id)
    showcase = await service.create(company_id, body.branch_id, body.warehouse_id, current.id)
    out = _showcase(showcase)
    await _audit(
        audit,
        request,
        action="CREATE_POS_SHOWCASE",
        actor=current.id,
        company_id=company_id,
        branch_id=body.branch_id,
        resource_type="pos_showcase",
        resource_id=showcase.id,
        after=out.model_dump(mode="json"),
    )
    return out


@router.get(
    "/{branch_id:uuid}/stock",
    response_model=list[ShowcaseStockOut],
    summary="Existencia de la vitrina por producto, con vencimientos",
    dependencies=_READ,
)
async def showcase_stock(
    branch_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    service: Service,
) -> list[ShowcaseStockOut]:
    await resolve_branch_scope(session, current, company_id, branch_id)
    return [_stock(item) for item in await service.stock(company_id, branch_id)]


@router.get(
    "/{branch_id:uuid}/candidates",
    response_model=list[CandidateOut],
    summary="Unidades completas de la bodega que pueden pasar a vitrina",
    dependencies=_SHOWCASE,
)
async def showcase_candidates(
    branch_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    service: Service,
    search: Annotated[str | None, Query(max_length=80)] = None,
) -> list[CandidateOut]:
    await resolve_branch_scope(session, current, company_id, branch_id)
    return [_candidate(item) for item in await service.candidates(company_id, branch_id, search)]


@router.post(
    "/{branch_id:uuid}/open",
    response_model=OpenUnitsOut,
    status_code=status.HTTP_201_CREATED,
    summary="Pasar unidades completas a la vitrina (idempotente por llave)",
    dependencies=_SHOWCASE,
)
async def open_units(
    branch_id: uuid.UUID,
    body: OpenUnitsIn,
    request: Request,
    response: Response,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    service: Service,
    audit: Audit,
) -> OpenUnitsOut:
    await resolve_branch_scope(session, current, company_id, branch_id)
    movement_id, created = await service.open_units(
        company_id, branch_id, body.handling_unit_ids, current.id, body.idempotency_key
    )
    showcase = await service.showcase(company_id, branch_id)
    if created:
        await _audit(
            audit,
            request,
            action="POS_SHOWCASE_OPEN_UNITS",
            actor=current.id,
            company_id=company_id,
            branch_id=branch_id,
            resource_type="pos_showcase",
            resource_id=showcase.id,
            after={
                "movement_id": str(movement_id),
                "handling_unit_ids": [str(item) for item in body.handling_unit_ids],
            },
        )
    else:
        response.status_code = status.HTTP_200_OK
    return OpenUnitsOut(
        movement_id=movement_id,
        stock=[_stock(item) for item in await service.stock(company_id, branch_id)],
    )


@router.get(
    "/{branch_id:uuid}/counts",
    response_model=list[ShowcaseCountOut],
    summary="Conteos de cierre de la vitrina, del más reciente al más antiguo",
    dependencies=_SHOWCASE,
)
async def list_counts(
    branch_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    service: Service,
) -> list[ShowcaseCountOut]:
    await resolve_branch_scope(session, current, company_id, branch_id)
    return [_count(item) for item in await service.counts(company_id, branch_id)]


@router.post(
    "/{branch_id:uuid}/counts",
    response_model=ShowcaseCountOut,
    status_code=status.HTTP_201_CREATED,
    summary="Contar la vitrina y registrar la merma (idempotente por llave)",
    dependencies=_SHOWCASE,
)
async def count_showcase(
    branch_id: uuid.UUID,
    body: CountIn,
    request: Request,
    response: Response,
    session: SessionDep,
    current: CurrentUser,
    company_id: CompanyId,
    service: Service,
    audit: Audit,
) -> ShowcaseCountOut:
    await resolve_branch_scope(session, current, company_id, branch_id)
    count, created = await service.count(
        company_id,
        branch_id,
        [
            CountLineInput(line.inventory_item_id, line.counted_quantity, line.reason)
            for line in body.lines
        ],
        body.notes,
        current.id,
        body.idempotency_key,
    )
    out = _count(count)
    if created:
        await _audit(
            audit,
            request,
            action="POS_SHOWCASE_COUNT",
            actor=current.id,
            company_id=company_id,
            branch_id=branch_id,
            resource_type="pos_showcase_count",
            resource_id=count.id,
            after=out.model_dump(mode="json"),
        )
    else:
        response.status_code = status.HTTP_200_OK
    return out
