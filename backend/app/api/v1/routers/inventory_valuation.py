"""Approval and read-only valuation ledger, scoped to the entire company."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select

from app.api.v1.company_access import effective_company_id, require_company_wide_scope
from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.routers.inventory import _execute
from app.api.v1.schemas.inventory_valuation import (
    SupplierCreditIn,
    ValuationBalanceOut,
    ValuationEntryOut,
    ValuationOpeningIn,
    ValuationOverviewOut,
    ValuationSettingOut,
)
from app.application.audit.audit_service import AuditService
from app.core.exceptions import ConflictError
from app.infrastructure.models.catalog import ProductModel, UnitModel
from app.infrastructure.models.inventory import InventoryItemModel
from app.infrastructure.models.inventory_valuation import InventoryValuationEntryModel
from app.infrastructure.models.product_variant import ProductVariantModel
from app.infrastructure.repositories.inventory_valuation_repository import (
    SqlAlchemyInventoryValuationRepository,
    fingerprint,
)

router = APIRouter(
    prefix="/inventory/valuation",
    tags=["inventory valuation"],
    dependencies=[Depends(require_permission("inventory:valuation"))],
)


async def _company(request: Request, session: SessionDep, current: CurrentUser) -> uuid.UUID:
    company_id = effective_company_id(request)
    await require_company_wide_scope(session, current, company_id)
    return company_id


@router.get("", response_model=ValuationOverviewOut)
async def overview(
    request: Request, session: SessionDep, current: CurrentUser
) -> ValuationOverviewOut:
    company_id = await _company(request, session, current)
    repository = SqlAlchemyInventoryValuationRepository(session)
    # A coherent snapshot of physical and financial projections.
    await repository.lock(company_id)
    setting = await repository.settings(company_id)
    snapshot = await repository.physical_snapshot(company_id)
    rows = (
        await session.execute(
            select(
                InventoryItemModel.id,
                ProductModel.name,
                func.coalesce(ProductVariantModel.sku, ProductModel.sku),
                UnitModel.symbol,
            )
            .select_from(InventoryItemModel)
            .outerjoin(ProductVariantModel, ProductVariantModel.id == InventoryItemModel.variant_id)
            .join(
                ProductModel,
                ProductModel.id_product
                == func.coalesce(InventoryItemModel.product_id, ProductVariantModel.product_id),
            )
            .join(UnitModel, UnitModel.id_unit == InventoryItemModel.base_unit_id)
            .where(InventoryItemModel.company_id == company_id)
            .order_by(ProductModel.name)
        )
    ).all()
    return ValuationOverviewOut(
        setting=ValuationSettingOut.model_validate(setting) if setting else None,
        snapshot_fingerprint=fingerprint(snapshot),
        physical_stock=snapshot,
        items=[
            {
                "inventory_item_id": row[0],
                "product_name": row[1],
                "sku": row[2],
                "base_unit": row[3] or "unidad base",
            }
            for row in rows
        ],
        balances=[
            ValuationBalanceOut.model_validate(row) for row in await repository.balances(company_id)
        ],
    )


@router.post("/opening", response_model=ValuationSettingOut)
async def approve_opening(
    body: ValuationOpeningIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> ValuationSettingOut:
    company_id = await _company(request, session, current)
    repository = SqlAlchemyInventoryValuationRepository(session)
    async with session.begin_nested():
        setting = await _execute(
            session,
            repository.open_valuation(
                company_id=company_id,
                currency=body.currency,
                reference=body.reference,
                lines=[line.model_dump() for line in body.lines],
                actor_id=current.id,
                snapshot_fingerprint=body.snapshot_fingerprint,
            ),
        )
        response = ValuationSettingOut.model_validate(setting)
        await audit.record(
            action="APPROVE_OPENING",
            user_id=current.id,
            company_id=company_id,
            resource_type="inventory_valuation",
            resource_id=str(company_id),
            after_state={
                "currency": body.currency,
                "reference": body.reference,
                "lines": len(body.lines),
            },
            required=True,
        )
    return response


@router.get("/items/{item_id}/ledger", response_model=list[ValuationEntryOut])
async def ledger(
    item_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[ValuationEntryOut]:
    company_id = await _company(request, session, current)
    item = await session.get(InventoryItemModel, item_id)
    if item is None or item.company_id != company_id:
        raise HTTPException(404, "Producto de inventario no encontrado.")
    rows = await SqlAlchemyInventoryValuationRepository(session).ledger(
        company_id, item_id, skip=skip, limit=limit
    )
    return [ValuationEntryOut.model_validate(row) for row in rows]


@router.post("/supplier-credits", response_model=ValuationEntryOut)
async def supplier_credit(
    body: SupplierCreditIn,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> ValuationEntryOut:
    company_id = await _company(request, session, current)
    repository = SqlAlchemyInventoryValuationRepository(session)
    async with session.begin_nested():
        await repository.lock(company_id)
        source = await session.get(InventoryValuationEntryModel, body.supplier_return_entry_id)
        if source is None or source.company_id != company_id or source.kind != "supplier_return":
            raise HTTPException(404, "Devolución a proveedor no encontrada.")
        setting = await repository.settings(company_id)
        if setting is None or body.currency != setting.currency:
            raise ConflictError(
                "La moneda debe coincidir con la valoración de la empresa.",
                code="valuation_currency_mismatch",
            )
        entry = await _execute(
            session,
            repository.append(
                company_id=company_id,
                item_id=source.inventory_item_id,
                kind="supplier_credit",
                quantity=Decimal("0"),
                value=body.credit_net,
                actor_id=current.id,
                key=f"credit:{body.idempotency_key}",
                reference=body.reference,
                original_id=source.id,
            ),
        )
        response = ValuationEntryOut.model_validate(entry)
        await audit.record(
            action="SUPPLIER_CREDIT",
            user_id=current.id,
            company_id=company_id,
            resource_type="inventory_valuation",
            resource_id=str(entry.id),
            after_state=response.model_dump(mode="json"),
            required=True,
        )
    return response
