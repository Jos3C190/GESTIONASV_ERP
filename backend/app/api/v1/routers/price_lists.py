"""Listas de precios de venta (bloque V2b)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.company_access import request_company_id
from app.api.v1.deps import (
    CurrentUser,
    get_audit_service,
    get_check_permission_use_case,
    get_price_list_use_cases,
    require_any_permission,
    require_permission,
)
from app.api.v1.schemas.price_list import (
    CategoryMarginOut,
    CategoryMarginsIn,
    CategoryOut,
    EndPriceIn,
    ListedPriceOut,
    PriceEntryOut,
    PriceIn,
    PriceListIn,
    PriceListOut,
    ResolvedPriceOut,
    SellableUnitOut,
)
from app.application.audit.audit_service import AuditService
from app.application.price_lists import PriceListUseCases, today_in_el_salvador
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.domain.entities.price_list import (
    ListedPrice,
    PriceEntry,
    PriceKey,
    PriceList,
    PriceListDraft,
    SellableUnit,
)
from app.domain.entities.sales_margin import margin_percent, suggested_price

router = APIRouter(tags=["price-lists"])

UseCases = Annotated[PriceListUseCases, Depends(get_price_list_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
Checker = Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)]
_READ = [Depends(require_permission("price_lists:read"))]
_MANAGE = [Depends(require_permission("price_lists:manage"))]


def _list_out(item: PriceList) -> PriceListOut:
    return PriceListOut(
        id=item.id,
        code=item.code,
        name=item.name,
        description=item.description,
        prices_include_vat=item.prices_include_vat,
        is_default=item.is_default,
        is_active=item.is_active,
        price_count=item.price_count,
        customer_count=item.customer_count,
        updated_at=item.updated_at,
        target_margin_percent=item.target_margin_percent,
    )


def _unit_out(unit: SellableUnit) -> SellableUnitOut:
    return SellableUnitOut(
        product_id=unit.product_id,
        variant_id=unit.variant_id,
        sku=unit.sku,
        name=unit.name,
        unit_id=unit.unit_id,
        unit_name=unit.unit_name,
        factor=unit.factor,
        is_base=unit.is_base,
    )


def _entry_out(entry: PriceEntry) -> PriceEntryOut:
    return PriceEntryOut(
        id=entry.id,
        price_list_id=entry.price_list_id,
        product_id=entry.key.product_id,
        variant_id=entry.key.variant_id,
        unit_id=entry.key.unit_id,
        branch_id=entry.key.branch_id,
        branch_name=entry.branch_name,
        price=entry.price,
        valid_from=entry.valid_from,
        valid_to=entry.valid_to,
        status=entry.status(today_in_el_salvador()).value,
        created_by_name=entry.created_by_name,
        created_at=entry.created_at,
    )


def _listed_out(row: ListedPrice, includes_vat: bool) -> ListedPriceOut:
    """Costo, margen y precio sugerido; solo llegan aquí si el usuario puede verlos."""
    margin = margin_percent(row.current.price, includes_vat, row.cost) if row.current else None
    suggested = (
        suggested_price(row.cost, row.target_margin_percent, includes_vat)
        if row.cost is not None and row.target_margin_percent is not None
        else None
    )
    return ListedPriceOut(
        unit=_unit_out(row.unit),
        current=_entry_out(row.current) if row.current else None,
        next=_entry_out(row.next) if row.next else None,
        branch_overrides=row.branch_overrides,
        cost=row.cost,
        margin_percent=margin,
        target_margin_percent=row.target_margin_percent,
        suggested_price=suggested,
        below_cost=margin is not None and margin < 0,
        below_target=margin is not None
        and row.target_margin_percent is not None
        and margin < row.target_margin_percent,
    )


def _state(value: object | None) -> dict[str, Any] | None:
    if isinstance(value, PriceList):
        return _list_out(value).model_dump(mode="json")
    if isinstance(value, PriceEntry):
        return _entry_out(value).model_dump(mode="json")
    return None


async def _record(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    resource_type: str,
    resource_id: uuid.UUID,
    before: object | None = None,
    after: object | None = None,
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=request_company_id(request),
        resource_type=resource_type,
        resource_id=str(resource_id),
        before_state=_state(before),
        after_state=_state(after),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


def _draft(body: PriceListIn) -> PriceListDraft:
    return PriceListDraft(
        code=body.code,
        name=body.name,
        description=body.description,
        prices_include_vat=body.prices_include_vat,
        is_default=body.is_default,
        is_active=body.is_active,
        target_margin_percent=body.target_margin_percent,
    )


@router.get(
    "/price-lists",
    response_model=list[PriceListOut],
    summary="Listas de precios de la empresa",
    dependencies=[
        Depends(require_any_permission("price_lists:read", "sales_customers:read", "sales:read"))
    ],
)
async def list_price_lists(request: Request, use_cases: UseCases) -> list[PriceListOut]:
    return [_list_out(i) for i in await use_cases.list_lists(request_company_id(request))]


@router.post(
    "/price-lists",
    response_model=PriceListOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una lista de precios",
    dependencies=_MANAGE,
)
async def create_price_list(
    body: PriceListIn, request: Request, current: CurrentUser, use_cases: UseCases, audit: Audit
) -> PriceListOut:
    created = await use_cases.create_list(request_company_id(request), _draft(body), current.id)
    await _record(
        audit,
        request,
        action="CREATE",
        actor=current.id,
        resource_type="price_list",
        resource_id=created.id,
        after=created,
    )
    return _list_out(created)


@router.get(
    "/price-lists/sellable-units",
    response_model=list[SellableUnitOut],
    summary="Productos y unidades que se pueden poner en una lista",
    dependencies=_READ,
)
async def sellable_units(
    request: Request,
    use_cases: UseCases,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> list[SellableUnitOut]:
    units = await use_cases.sellable_units(request_company_id(request), search)
    return [_unit_out(u) for u in units]


@router.get(
    "/price-lists/categories",
    response_model=list[CategoryOut],
    summary="Categorías de productos para los márgenes por categoría",
    dependencies=_READ,
)
async def categories(request: Request, use_cases: UseCases) -> list[CategoryOut]:
    rows = await use_cases.categories(request_company_id(request))
    return [CategoryOut(id=i, name=n) for i, n in rows]


@router.post(
    "/price-lists/items/{entry_id}/end",
    response_model=PriceEntryOut,
    summary="Terminar la vigencia de un precio",
    dependencies=_MANAGE,
)
async def end_price(
    entry_id: uuid.UUID,
    body: EndPriceIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> PriceEntryOut:
    before, after = await use_cases.end_price(request_company_id(request), entry_id, body.ends_on)
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        resource_type="price_list_item",
        resource_id=entry_id,
        before=before,
        after=after,
    )
    return _entry_out(after)


@router.delete(
    "/price-lists/items/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Anular un precio programado",
    dependencies=_MANAGE,
)
async def cancel_price(
    entry_id: uuid.UUID, request: Request, current: CurrentUser, use_cases: UseCases, audit: Audit
) -> None:
    cancelled = await use_cases.cancel_price(request_company_id(request), entry_id)
    await _record(
        audit,
        request,
        action="DELETE",
        actor=current.id,
        resource_type="price_list_item",
        resource_id=entry_id,
        before=cancelled,
    )


@router.get(
    "/price-lists/{list_id}",
    response_model=PriceListOut,
    summary="Una lista de precios",
    dependencies=_READ,
)
async def get_price_list(list_id: uuid.UUID, request: Request, use_cases: UseCases) -> PriceListOut:
    return _list_out(await use_cases.get_list(request_company_id(request), list_id))


@router.put(
    "/price-lists/{list_id}",
    response_model=PriceListOut,
    summary="Editar una lista de precios",
    dependencies=_MANAGE,
)
async def update_price_list(
    list_id: uuid.UUID,
    body: PriceListIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> PriceListOut:
    before, after = await use_cases.update_list(
        request_company_id(request), list_id, _draft(body), current.id
    )
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        resource_type="price_list",
        resource_id=list_id,
        before=before,
        after=after,
    )
    return _list_out(after)


@router.get(
    "/price-lists/{list_id}/prices",
    response_model=list[ListedPriceOut],
    summary="Precios de una lista para un día y una sucursal",
    dependencies=_READ,
)
async def listed_prices(
    list_id: uuid.UUID,
    request: Request,
    use_cases: UseCases,
    current: CurrentUser,
    checker: Checker,
    search: Annotated[str | None, Query(max_length=100)] = None,
    branch_id: uuid.UUID | None = None,
    on: date | None = None,
) -> list[ListedPriceOut]:
    company_id = request_company_id(request)
    with_costs = (await checker.execute(current.id, company_id, "sales_costs:read")).allowed
    price_list = await use_cases.get_list(company_id, list_id)
    rows = await use_cases.listed_prices(
        company_id, list_id, search=search, branch_id=branch_id, on=on, with_costs=with_costs
    )
    return [_listed_out(r, price_list.prices_include_vat) for r in rows]


@router.get(
    "/price-lists/{list_id}/category-margins",
    response_model=list[CategoryMarginOut],
    summary="Márgenes objetivo por categoría dentro de una lista",
    dependencies=_READ,
)
async def category_margins(
    list_id: uuid.UUID, request: Request, use_cases: UseCases
) -> list[CategoryMarginOut]:
    margins = await use_cases.category_margins(request_company_id(request), list_id)
    return [CategoryMarginOut(category_id=k, target_margin_percent=v) for k, v in margins.items()]


@router.put(
    "/price-lists/{list_id}/category-margins",
    response_model=list[CategoryMarginOut],
    summary="Reemplazar los márgenes objetivo por categoría de una lista",
    dependencies=_MANAGE,
)
async def replace_category_margins(
    list_id: uuid.UUID,
    body: CategoryMarginsIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> list[CategoryMarginOut]:
    company_id = request_company_id(request)
    margins = {m.category_id: m.target_margin_percent for m in body.margins}
    before, after = await use_cases.replace_category_margins(
        company_id, list_id, margins, current.id
    )
    await audit.record(
        action="UPDATE",
        user_id=current.id,
        company_id=company_id,
        resource_type="price_list_category_margins",
        resource_id=str(list_id),
        before_state={str(k): str(v) for k, v in before.items()},
        after_state={str(k): str(v) for k, v in after.items()},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )
    return [CategoryMarginOut(category_id=k, target_margin_percent=v) for k, v in after.items()]


@router.get(
    "/price-lists/{list_id}/history",
    response_model=list[PriceEntryOut],
    summary="Historial de precios de un producto y unidad, en todas las sucursales",
    dependencies=_READ,
)
async def price_history(
    list_id: uuid.UUID,
    request: Request,
    use_cases: UseCases,
    product_id: int,
    unit_id: int,
    variant_id: uuid.UUID | None = None,
) -> list[PriceEntryOut]:
    entries = await use_cases.history(
        request_company_id(request), list_id, product_id, variant_id, unit_id
    )
    return [_entry_out(e) for e in entries]


@router.post(
    "/price-lists/{list_id}/prices",
    response_model=PriceEntryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Fijar un precio desde una fecha",
    dependencies=_MANAGE,
)
async def set_price(
    list_id: uuid.UUID,
    body: PriceIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> PriceEntryOut:
    entry = await use_cases.set_price(
        request_company_id(request),
        list_id,
        PriceKey(body.product_id, body.variant_id, body.unit_id, body.branch_id),
        body.price,
        body.valid_from,
        current.id,
    )
    await _record(
        audit,
        request,
        action="CREATE",
        actor=current.id,
        resource_type="price_list_item",
        resource_id=entry.id,
        after=entry,
    )
    return _entry_out(entry)


@router.get(
    "/sales/prices/resolve",
    response_model=ResolvedPriceOut,
    summary="Precio que corresponde a un cliente en una sucursal y fecha",
    dependencies=[
        Depends(require_any_permission("price_lists:read", "sales_quotations:read", "sales:read"))
    ],
)
async def resolve_price(
    request: Request,
    use_cases: UseCases,
    product_id: int,
    unit_id: int,
    variant_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    on: date | None = None,
) -> ResolvedPriceOut:
    resolved = await use_cases.resolve(
        request_company_id(request),
        customer_id=customer_id,
        branch_id=branch_id,
        product_id=product_id,
        variant_id=variant_id,
        unit_id=unit_id,
        on=on,
    )
    price_list, entry = resolved.price_list, resolved.entry
    message = None
    if price_list is None:
        message = "La empresa no tiene una lista de precios predeterminada."
    elif entry is None:
        message = f"El producto no tiene precio en la lista «{price_list.name}» para esa fecha."
    return ResolvedPriceOut(
        found=entry is not None,
        price=entry.price if entry else None,
        prices_include_vat=price_list.prices_include_vat if price_list else None,
        price_list_id=price_list.id if price_list else None,
        price_list_name=price_list.name if price_list else None,
        source=resolved.source.value if resolved.source else None,
        branch_specific=bool(entry and entry.key.branch_id),
        entry_id=entry.id if entry else None,
        valid_to=entry.valid_to if entry else None,
        message=message,
    )
