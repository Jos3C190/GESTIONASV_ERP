"""Clasificación fiscal de productos y código de Hacienda de las unidades (bloque V1c)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.api.v1.company_access import request_company_id
from app.api.v1.deps import (
    CurrentUser,
    get_audit_service,
    get_product_fiscal_use_cases,
    require_permission,
)
from app.api.v1.schemas.product_fiscal import (
    CatalogEntryOut,
    FiscalOptionsOut,
    ProductFiscalIn,
    ProductFiscalOut,
    UnitFiscalIn,
    UnitFiscalOut,
)
from app.application.audit.audit_service import AuditService
from app.application.product_fiscal import ProductFiscalUseCases
from app.domain.entities.product_fiscal import ProductFiscal, UnitFiscal

router = APIRouter(tags=["product-fiscal"])

UseCases = Annotated[ProductFiscalUseCases, Depends(get_product_fiscal_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]


def unit_out(unit: UnitFiscal) -> UnitFiscalOut:
    return UnitFiscalOut(
        unit_id=unit.unit_id,
        code=unit.code,
        name=unit.name,
        symbol=unit.symbol,
        is_enabled=unit.is_enabled,
        hacienda_unit_code=unit.hacienda_unit_code,
        suggested_code=unit.suggested_code,
        effective_code=unit.effective_code,
        hacienda_unit_name=unit.hacienda_unit_name,
    )


def product_out(product: ProductFiscal) -> ProductFiscalOut:
    return ProductFiscalOut(
        product_id=product.product_id,
        product_uuid=product.product_uuid,
        sku=product.sku,
        name=product.name,
        product_kind=product.product_kind,
        can_sell=product.can_sell,
        tax_treatment=product.tax_treatment,
        dte_item_type=product.dte_item_type,
        effective_item_type=product.effective_item_type,
        additional_taxes=[
            CatalogEntryOut(code=t.code, name=t.name) for t in product.additional_taxes
        ],
        sale_unit=unit_out(product.sale_unit) if product.sale_unit else None,
        billing_issues=product.billing_issues,
    )


async def _record(
    audit: AuditService,
    request: Request,
    *,
    actor: uuid.UUID,
    company_id: uuid.UUID,
    resource_type: str,
    resource_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    await audit.record(
        action="UPDATE",
        user_id=actor,
        company_id=company_id,
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=before,
        after_state=after,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


@router.get(
    "/product-fiscal/options",
    response_model=FiscalOptionsOut,
    summary="Tributos y unidades de Hacienda para clasificar productos",
    dependencies=[Depends(require_permission("products:read"))],
)
async def fiscal_options(use_cases: UseCases) -> FiscalOptionsOut:
    return FiscalOptionsOut(
        taxes=[CatalogEntryOut(code=e.code, name=e.name) for e in await use_cases.tax_options()],
        units=[CatalogEntryOut(code=e.code, name=e.name) for e in await use_cases.unit_options()],
    )


@router.get(
    "/products/{product_id}/fiscal",
    response_model=ProductFiscalOut,
    summary="Clasificación fiscal del producto",
    dependencies=[Depends(require_permission("products:read"))],
)
async def get_product_fiscal(
    product_id: int, request: Request, use_cases: UseCases
) -> ProductFiscalOut:
    return product_out(await use_cases.get_product(request_company_id(request), product_id))


@router.put(
    "/products/{product_id}/fiscal",
    response_model=ProductFiscalOut,
    summary="Guardar la clasificación fiscal del producto",
    dependencies=[Depends(require_permission("products:fiscal"))],
)
async def update_product_fiscal(
    product_id: int,
    body: ProductFiscalIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> ProductFiscalOut:
    company_id = request_company_id(request)
    before = product_out(await use_cases.get_product(company_id, product_id))
    saved = product_out(
        await use_cases.update_product(
            company_id,
            product_id,
            tax_treatment=body.tax_treatment,
            dte_item_type=body.dte_item_type,
            additional_tax_codes=body.additional_tax_codes,
        )
    )
    await _record(
        audit,
        request,
        actor=current.id,
        company_id=company_id,
        resource_type="product_fiscal",
        resource_id=str(product_id),
        before=before.model_dump(mode="json"),
        after=saved.model_dump(mode="json"),
    )
    return saved


@router.get(
    "/fiscal/units",
    response_model=list[UnitFiscalOut],
    summary="Unidades de la empresa y su código de Hacienda",
    dependencies=[Depends(require_permission("fiscal_settings:read"))],
)
async def list_fiscal_units(request: Request, use_cases: UseCases) -> list[UnitFiscalOut]:
    return [unit_out(u) for u in await use_cases.list_units(request_company_id(request))]


@router.put(
    "/fiscal/units/{unit_id}",
    response_model=UnitFiscalOut,
    summary="Asignar el código de Hacienda de una unidad",
    dependencies=[Depends(require_permission("fiscal_settings:manage"))],
)
async def update_fiscal_unit(
    unit_id: int,
    body: UnitFiscalIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> UnitFiscalOut:
    company_id = request_company_id(request)
    before = unit_out(await use_cases.get_unit(company_id, unit_id))
    saved = unit_out(await use_cases.update_unit(company_id, unit_id, body.hacienda_unit_code))
    await _record(
        audit,
        request,
        actor=current.id,
        company_id=company_id,
        resource_type="fiscal_unit",
        resource_id=str(unit_id),
        before=before.model_dump(mode="json"),
        after=saved.model_dump(mode="json"),
    )
    return saved
