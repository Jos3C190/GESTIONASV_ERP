"""Product master-data, identifiers and sourcing endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, update

from app.api.v1.company_access import (
    request_company_id,
    require_company_access,
    require_company_wide_scope,
)
from app.api.v1.deps import CurrentUser, SessionDep, get_audit_service, require_permission
from app.api.v1.schemas.catalog import (
    ProductBrandCreate,
    ProductBrandResponse,
    ProductBrandUpdate,
    ProductIdentifierCreate,
    ProductIdentifierResponse,
    ProductIdentifierUpdate,
    ProductManufacturerCreate,
    ProductManufacturerResponse,
    ProductManufacturerUpdate,
    ProductSupplierCreate,
    ProductSupplierReplace,
    ProductSupplierResponse,
    ProductSupplierUpdate,
)
from app.application.audit.audit_service import AuditService
from app.domain.product_master import normalize_identifier
from app.infrastructure.models.catalog import ProductModel
from app.infrastructure.models.product_master import (
    ProductBrandModel,
    ProductIdentifierModel,
    ProductManufacturerModel,
    ProductSupplierModel,
)
from app.infrastructure.models.supplier import SupplierModel

router = APIRouter(tags=["product-master"])


@router.get("/catalog/brands", response_model=list[ProductBrandResponse], dependencies=[Depends(require_permission("products:read"))])
async def list_brands(request: Request, session: SessionDep, current: CurrentUser) -> list[ProductBrandResponse]:
    company_id = _company(request)
    await require_company_access(session, current, company_id)
    rows = (await session.scalars(select(ProductBrandModel).where(ProductBrandModel.company_id == company_id).order_by(ProductBrandModel.name))).all()
    return [ProductBrandResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/catalog/brands", response_model=ProductBrandResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("products:master_data"))])
async def create_brand(payload: ProductBrandCreate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> ProductBrandResponse:
    company_id = _company(request)
    await require_company_wide_scope(session, current, company_id)
    normalized = " ".join(payload.name.strip().split()).casefold()
    if await session.scalar(select(ProductBrandModel).where(ProductBrandModel.company_id == company_id, ProductBrandModel.normalized_name == normalized)):
        raise HTTPException(status_code=409, detail="La marca ya existe.")
    row = ProductBrandModel(company_id=company_id, code=payload.code.strip().upper(), name=payload.name.strip(), normalized_name=normalized)
    session.add(row)
    await session.flush()
    await audit.record(action="CREATE", user_id=current.id, company_id=company_id, resource_type="product_brands", resource_id=str(row.id), after_state={"code": row.code, "name": row.name})
    return ProductBrandResponse.model_validate(row, from_attributes=True)


@router.patch("/catalog/brands/{brand_id}", response_model=ProductBrandResponse, dependencies=[Depends(require_permission("products:master_data"))])
async def update_brand(brand_id: uuid.UUID, payload: ProductBrandUpdate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> ProductBrandResponse:
    company_id = _company(request)
    await require_company_wide_scope(session, current, company_id)
    row = await session.scalar(select(ProductBrandModel).where(ProductBrandModel.id == brand_id, ProductBrandModel.company_id == company_id).with_for_update())
    if row is None:
        raise HTTPException(status_code=404, detail="Marca no encontrada")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        data["name"] = data["name"].strip()
        data["normalized_name"] = " ".join(data["name"].split()).casefold()
    if "code" in data:
        data["code"] = data["code"].strip().upper()
    for key, value in data.items():
        setattr(row, key, value)
    await session.flush()
    await audit.record(action="UPDATE", user_id=current.id, company_id=company_id, resource_type="product_brands", resource_id=str(row.id), after_state={"code": row.code, "name": row.name})
    return ProductBrandResponse.model_validate(row, from_attributes=True)


@router.delete("/catalog/brands/{brand_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("products:master_data"))])
async def delete_brand(brand_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> None:
    company_id = _company(request)
    await require_company_wide_scope(session, current, company_id)
    row = await session.scalar(select(ProductBrandModel).where(ProductBrandModel.id == brand_id, ProductBrandModel.company_id == company_id).with_for_update())
    if row is None:
        raise HTTPException(status_code=404, detail="Marca no encontrada")
    row.is_active = False
    await audit.record(action="DEACTIVATE", user_id=current.id, company_id=company_id, resource_type="product_brands", resource_id=str(row.id), after_state={"is_active": False})


@router.get("/catalog/manufacturers", response_model=list[ProductManufacturerResponse], dependencies=[Depends(require_permission("products:read"))])
async def list_manufacturers(request: Request, session: SessionDep, current: CurrentUser) -> list[ProductManufacturerResponse]:
    company_id = _company(request)
    await require_company_access(session, current, company_id)
    rows = (await session.scalars(select(ProductManufacturerModel).where(ProductManufacturerModel.company_id == company_id).order_by(ProductManufacturerModel.legal_name))).all()
    return [ProductManufacturerResponse.model_validate(row, from_attributes=True) for row in rows]


@router.post("/catalog/manufacturers", response_model=ProductManufacturerResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("products:master_data"))])
async def create_manufacturer(payload: ProductManufacturerCreate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> ProductManufacturerResponse:
    company_id = _company(request)
    await require_company_wide_scope(session, current, company_id)
    row = ProductManufacturerModel(company_id=company_id, **payload.model_dump())
    session.add(row)
    await session.flush()
    await audit.record(action="CREATE", user_id=current.id, company_id=company_id, resource_type="product_manufacturers", resource_id=str(row.id), after_state={"legal_name": row.legal_name})
    return ProductManufacturerResponse.model_validate(row, from_attributes=True)


@router.patch("/catalog/manufacturers/{manufacturer_id}", response_model=ProductManufacturerResponse, dependencies=[Depends(require_permission("products:master_data"))])
async def update_manufacturer(manufacturer_id: uuid.UUID, payload: ProductManufacturerUpdate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> ProductManufacturerResponse:
    company_id = _company(request)
    await require_company_wide_scope(session, current, company_id)
    row = await session.scalar(select(ProductManufacturerModel).where(ProductManufacturerModel.id == manufacturer_id, ProductManufacturerModel.company_id == company_id).with_for_update())
    if row is None:
        raise HTTPException(status_code=404, detail="Fabricante no encontrado")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await session.flush()
    await audit.record(action="UPDATE", user_id=current.id, company_id=company_id, resource_type="product_manufacturers", resource_id=str(row.id), after_state={"legal_name": row.legal_name})
    return ProductManufacturerResponse.model_validate(row, from_attributes=True)


@router.delete("/catalog/manufacturers/{manufacturer_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("products:master_data"))])
async def delete_manufacturer(manufacturer_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> None:
    company_id = _company(request)
    await require_company_wide_scope(session, current, company_id)
    row = await session.scalar(select(ProductManufacturerModel).where(ProductManufacturerModel.id == manufacturer_id, ProductManufacturerModel.company_id == company_id).with_for_update())
    if row is None:
        raise HTTPException(status_code=404, detail="Fabricante no encontrado")
    row.is_active = False
    await audit.record(action="DEACTIVATE", user_id=current.id, company_id=company_id, resource_type="product_manufacturers", resource_id=str(row.id), after_state={"is_active": False})


def _company(request: Request) -> uuid.UUID:
    return request_company_id(request)


async def _product(session: SessionDep, company_id: uuid.UUID, product_id: int, *, lock: bool = False) -> ProductModel:
    stmt = select(ProductModel).where(ProductModel.company_id == company_id, ProductModel.id_product == product_id)
    if lock:
        stmt = stmt.with_for_update()
    item = await session.scalar(stmt)
    if item is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return item


def _identifier(item: ProductIdentifierModel) -> ProductIdentifierResponse:
    return ProductIdentifierResponse.model_validate(item, from_attributes=True)


def _supplier(item: ProductSupplierModel) -> ProductSupplierResponse:
    return ProductSupplierResponse.model_validate(item, from_attributes=True)


@router.get("/catalog/products/{product_id}/identifiers", response_model=list[ProductIdentifierResponse], dependencies=[Depends(require_permission("products:read"))])
async def list_identifiers(product_id: int, request: Request, session: SessionDep, current: CurrentUser) -> list[ProductIdentifierResponse]:
    company_id = _company(request)
    await require_company_access(session, current, company_id)
    await _product(session, company_id, product_id)
    rows = (await session.scalars(select(ProductIdentifierModel).where(ProductIdentifierModel.company_id == company_id, ProductIdentifierModel.product_id == product_id).order_by(ProductIdentifierModel.identifier_type, ProductIdentifierModel.value))).all()
    return [_identifier(item) for item in rows]


@router.post("/catalog/products/{product_id}/identifiers", response_model=ProductIdentifierResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("products:identifiers"))])
async def create_identifier(product_id: int, payload: ProductIdentifierCreate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> ProductIdentifierResponse:
    company_id = _company(request)
    await require_company_wide_scope(session, current, company_id)
    await _product(session, company_id, product_id, lock=True)
    normalized = normalize_identifier(payload.value)
    if await session.scalar(select(ProductIdentifierModel).where(ProductIdentifierModel.company_id == company_id, ProductIdentifierModel.identifier_type == payload.identifier_type, ProductIdentifierModel.normalized_value == normalized)):
        raise HTTPException(status_code=409, detail="El identificador ya está registrado en esta empresa.")
    if payload.is_primary:
        await session.execute(update(ProductIdentifierModel).where(ProductIdentifierModel.product_id == product_id, ProductIdentifierModel.identifier_type == payload.identifier_type).values(is_primary=False))
    item = ProductIdentifierModel(company_id=company_id, product_id=product_id, identifier_type=payload.identifier_type, value=payload.value.strip(), normalized_value=normalized, is_primary=payload.is_primary)
    session.add(item)
    await session.flush()
    await audit.record(action="CREATE", user_id=current.id, company_id=company_id, resource_type="product_identifiers", resource_id=str(item.id), after_state={"product_id": product_id, "identifier_type": item.identifier_type, "is_primary": item.is_primary})
    return _identifier(item)


@router.patch("/catalog/products/{product_id}/identifiers/{identifier_id}", response_model=ProductIdentifierResponse, dependencies=[Depends(require_permission("products:identifiers"))])
async def update_identifier(product_id: int, identifier_id: uuid.UUID, payload: ProductIdentifierUpdate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> ProductIdentifierResponse:
    company_id = _company(request)
    await require_company_wide_scope(session, current, company_id)
    await _product(session, company_id, product_id, lock=True)
    item = await session.scalar(select(ProductIdentifierModel).where(ProductIdentifierModel.id == identifier_id, ProductIdentifierModel.company_id == company_id, ProductIdentifierModel.product_id == product_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Identificador no encontrado")
    data = payload.model_dump(exclude_unset=True)
    if "value" in data:
        data["value"] = str(data["value"]).strip()
        data["normalized_value"] = normalize_identifier(data["value"])
    if data.get("is_primary"):
        target_type = data.get("identifier_type", item.identifier_type)
        await session.execute(update(ProductIdentifierModel).where(ProductIdentifierModel.product_id == product_id, ProductIdentifierModel.identifier_type == target_type, ProductIdentifierModel.id != identifier_id).values(is_primary=False))
    for key, value in data.items():
        if hasattr(item, key):
            setattr(item, key, value)
    await session.flush()
    await audit.record(action="UPDATE", user_id=current.id, company_id=company_id, resource_type="product_identifiers", resource_id=str(item.id), after_state={"product_id": product_id, "identifier_type": item.identifier_type, "is_primary": item.is_primary})
    return _identifier(item)


@router.delete("/catalog/products/{product_id}/identifiers/{identifier_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("products:identifiers"))])
async def delete_identifier(product_id: int, identifier_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> None:
    company_id = _company(request)
    await require_company_wide_scope(session, current, company_id)
    item = await session.scalar(select(ProductIdentifierModel).where(ProductIdentifierModel.id == identifier_id, ProductIdentifierModel.company_id == company_id, ProductIdentifierModel.product_id == product_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Identificador no encontrado")
    await session.delete(item)
    await audit.record(action="DELETE", user_id=current.id, company_id=company_id, resource_type="product_identifiers", resource_id=str(identifier_id), after_state={"product_id": product_id})


@router.get("/catalog/products/{product_id}/suppliers", response_model=list[ProductSupplierResponse], dependencies=[Depends(require_permission("products:read"))])
async def list_product_suppliers(product_id: int, request: Request, session: SessionDep, current: CurrentUser) -> list[ProductSupplierResponse]:
    company_id = _company(request)
    await require_company_access(session, current, company_id)
    await _product(session, company_id, product_id)
    rows = (await session.scalars(select(ProductSupplierModel).where(ProductSupplierModel.company_id == company_id, ProductSupplierModel.product_id == product_id).order_by(ProductSupplierModel.is_preferred.desc(), ProductSupplierModel.created_at))).all()
    return [_supplier(item) for item in rows]


async def _validate_supplier(session: SessionDep, company_id: uuid.UUID, supplier_id: int) -> SupplierModel:
    supplier = await session.scalar(select(SupplierModel).where(SupplierModel.company_id == company_id, SupplierModel.id_supplier == supplier_id).with_for_update())
    if supplier is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return supplier


@router.put(
    "/catalog/products/{product_id}/suppliers",
    response_model=list[ProductSupplierResponse],
    dependencies=[Depends(require_permission("products:suppliers"))],
)
async def replace_product_suppliers(  # noqa: C901
    product_id: int,
    payload: ProductSupplierReplace,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    audit: AuditService = Depends(get_audit_service),
) -> list[ProductSupplierResponse]:
    """Replace the product's sourcing set atomically for the editor screen."""
    company_id = _company(request)
    await require_company_wide_scope(session, current, company_id)
    product = await _product(session, company_id, product_id, lock=True)
    incoming_ids = [item.supplier_id for item in payload.suppliers]
    if len(incoming_ids) != len(set(incoming_ids)):
        raise HTTPException(status_code=409, detail="Un proveedor no puede repetirse en el mismo producto.")
    preferred_count = sum(1 for item in payload.suppliers if item.is_preferred)
    if preferred_count > 1:
        raise HTTPException(status_code=409, detail="Solo puede existir un proveedor preferido.")
    if not product.can_purchase and any(item.status == "active" for item in payload.suppliers):
        raise HTTPException(status_code=409, detail="El producto no está habilitado para compras.")

    existing = (
        await session.scalars(
            select(ProductSupplierModel)
            .where(
                ProductSupplierModel.company_id == company_id,
                ProductSupplierModel.product_id == product_id,
            )
            .with_for_update()
        )
    ).all()
    existing_by_supplier = {item.supplier_id: item for item in existing}
    for item in payload.suppliers:
        supplier = await _validate_supplier(session, company_id, item.supplier_id)
        if item.is_preferred and item.status == "active" and (supplier.supplier_status != "approved" or not supplier.is_active):
            raise HTTPException(status_code=409, detail="Solo un proveedor activo y aprobado puede ser preferido.")

    desired_ids = set(incoming_ids)
    for item in existing:
        if item.supplier_id not in desired_ids:
            await session.delete(item)

    for incoming in payload.suppliers:
        data = incoming.model_dump()
        if data.get("currency_code"):
            data["currency_code"] = data["currency_code"].upper()
        current_item = existing_by_supplier.get(incoming.supplier_id)
        if current_item is None:
            session.add(ProductSupplierModel(company_id=company_id, product_id=product_id, **data))
        else:
            for key, value in data.items():
                setattr(current_item, key, value)
    await session.flush()
    await audit.record(
        action="REPLACE",
        user_id=current.id,
        company_id=company_id,
        resource_type="product_suppliers",
        resource_id=str(product_id),
        after_state={
            "product_id": product_id,
            "supplier_ids": incoming_ids,
            "preferred_supplier_id": next(
                (item.supplier_id for item in payload.suppliers if item.is_preferred), None
            ),
        },
    )
    rows = (
        await session.scalars(
            select(ProductSupplierModel)
            .where(
                ProductSupplierModel.company_id == company_id,
                ProductSupplierModel.product_id == product_id,
            )
            .order_by(ProductSupplierModel.is_preferred.desc(), ProductSupplierModel.created_at)
        )
    ).all()
    return [_supplier(item) for item in rows]


@router.post("/catalog/products/{product_id}/suppliers", response_model=ProductSupplierResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("products:suppliers"))])
async def create_product_supplier(product_id: int, payload: ProductSupplierCreate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> ProductSupplierResponse:
    company_id = _company(request)
    await require_company_wide_scope(session, current, company_id)
    product = await _product(session, company_id, product_id, lock=True)
    supplier = await _validate_supplier(session, company_id, payload.supplier_id)
    if product.can_purchase is not True and payload.status == "active":
        raise HTTPException(status_code=409, detail="El producto no está habilitado para compras.")
    if payload.is_preferred and (supplier.supplier_status != "approved" or not supplier.is_active):
        raise HTTPException(status_code=409, detail="Solo un proveedor activo y aprobado puede ser preferido.")
    existing = await session.scalar(select(ProductSupplierModel).where(ProductSupplierModel.company_id == company_id, ProductSupplierModel.product_id == product_id, ProductSupplierModel.supplier_id == payload.supplier_id))
    if existing:
        raise HTTPException(status_code=409, detail="El proveedor ya está relacionado con este producto.")
    if payload.is_preferred:
        await session.execute(update(ProductSupplierModel).where(ProductSupplierModel.product_id == product_id).values(is_preferred=False))
    item = ProductSupplierModel(company_id=company_id, product_id=product_id, **payload.model_dump())
    session.add(item)
    await session.flush()
    await audit.record(action="CREATE", user_id=current.id, company_id=company_id, resource_type="product_suppliers", resource_id=str(item.id), after_state={"product_id": product_id, "supplier_id": item.supplier_id, "is_preferred": item.is_preferred, "unit_cost": str(item.unit_cost) if item.unit_cost is not None else None})
    return _supplier(item)


@router.patch("/catalog/products/{product_id}/suppliers/{relation_id}", response_model=ProductSupplierResponse, dependencies=[Depends(require_permission("products:suppliers"))])
async def update_product_supplier(product_id: int, relation_id: uuid.UUID, payload: ProductSupplierUpdate, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> ProductSupplierResponse:
    company_id = _company(request)
    await require_company_wide_scope(session, current, company_id)
    await _product(session, company_id, product_id, lock=True)
    item = await session.scalar(select(ProductSupplierModel).where(ProductSupplierModel.id == relation_id, ProductSupplierModel.company_id == company_id, ProductSupplierModel.product_id == product_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Relación producto-proveedor no encontrada")
    data = payload.model_dump(exclude_unset=True)
    supplier = await _validate_supplier(session, company_id, int(data["supplier_id"])) if "supplier_id" in data and data["supplier_id"] is not None else await _validate_supplier(session, company_id, item.supplier_id)
    preferred = data.get("is_preferred", item.is_preferred)
    active = data.get("status", item.status) == "active"
    if preferred and active and (supplier.supplier_status != "approved" or not supplier.is_active):
        raise HTTPException(status_code=409, detail="Solo un proveedor activo y aprobado puede ser preferido.")
    if preferred:
        await session.execute(update(ProductSupplierModel).where(ProductSupplierModel.product_id == product_id, ProductSupplierModel.id != relation_id).values(is_preferred=False))
    for key, value in data.items():
        if hasattr(item, key):
            setattr(item, key, value)
    await session.flush()
    await audit.record(action="UPDATE", user_id=current.id, company_id=company_id, resource_type="product_suppliers", resource_id=str(item.id), after_state={"product_id": product_id, "supplier_id": item.supplier_id, "is_preferred": item.is_preferred, "unit_cost": str(item.unit_cost) if item.unit_cost is not None else None})
    return _supplier(item)


@router.delete("/catalog/products/{product_id}/suppliers/{relation_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("products:suppliers"))])
async def delete_product_supplier(product_id: int, relation_id: uuid.UUID, request: Request, session: SessionDep, current: CurrentUser, audit: AuditService = Depends(get_audit_service)) -> None:
    company_id = _company(request)
    await require_company_wide_scope(session, current, company_id)
    item = await session.scalar(select(ProductSupplierModel).where(ProductSupplierModel.id == relation_id, ProductSupplierModel.company_id == company_id, ProductSupplierModel.product_id == product_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Relación producto-proveedor no encontrada")
    await session.delete(item)
    await audit.record(action="DELETE", user_id=current.id, company_id=company_id, resource_type="product_suppliers", resource_id=str(relation_id), after_state={"product_id": product_id, "supplier_id": item.supplier_id})


@router.get("/suppliers/{supplier_id}/products", response_model=list[ProductSupplierResponse], dependencies=[Depends(require_permission("suppliers:read"))])
async def list_supplier_products(supplier_id: int, request: Request, session: SessionDep, current: CurrentUser, limit: int = Query(50, ge=1, le=200)) -> list[ProductSupplierResponse]:
    company_id = _company(request)
    await require_company_access(session, current, company_id)
    await _validate_supplier(session, company_id, supplier_id)
    rows = (await session.scalars(select(ProductSupplierModel).where(ProductSupplierModel.company_id == company_id, ProductSupplierModel.supplier_id == supplier_id).order_by(ProductSupplierModel.created_at).limit(limit))).all()
    return [_supplier(item) for item in rows]
