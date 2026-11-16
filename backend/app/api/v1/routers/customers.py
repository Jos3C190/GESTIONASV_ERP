"""Maestro de clientes con identidad fiscal (bloque V1b del área de Ventas)."""

from __future__ import annotations

import uuid
from math import ceil
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.company_access import request_company_id
from app.api.v1.deps import (
    CurrentUser,
    get_audit_service,
    get_customer_use_cases,
    require_permission,
)
from app.api.v1.schemas.customer import (
    AddressOut,
    CustomerCreate,
    CustomerIn,
    CustomerOut,
    CustomerPage,
    CustomerStatusIn,
    DeliveryAddressIn,
    DeliveryAddressOut,
    GeographyIn,
)
from app.application.audit.audit_service import AuditService
from app.application.customers import CustomerUseCases
from app.domain.entities.customer import (
    Customer,
    CustomerAddress,
    CustomerDraft,
    CustomerType,
    DeliveryAddress,
    DeliveryAddressDraft,
    Geography,
)
from app.domain.ports.customer_repository import CustomerFilters

router = APIRouter(prefix="/customers", tags=["customers"])

UseCases = Annotated[CustomerUseCases, Depends(get_customer_use_cases)]
Audit = Annotated[AuditService, Depends(get_audit_service)]
_READ = [Depends(require_permission("sales_customers:read"))]
_MANAGE = [Depends(require_permission("sales_customers:manage"))]


def _geography(body: GeographyIn | None) -> Geography | None:
    if body is None:
        return None
    return Geography(body.department_id, body.municipality_id, body.district_id)


def _draft(body: CustomerIn) -> CustomerDraft:
    return CustomerDraft(
        customer_type=body.customer_type,
        name=body.name,
        person_type=body.person_type,
        taxpayer_category=body.taxpayer_category,
        is_withholding_agent=body.is_withholding_agent,
        commercial_name=body.commercial_name,
        document_type=body.document_type,
        document_number=body.document_number,
        nrc=body.nrc,
        activity_code=body.activity_code,
        geography=_geography(body.geography),
        address_line=body.address_line,
        country_code=body.country_code,
        phone=body.phone,
        email=str(body.email) if body.email else None,
        credit_days=body.credit_days,
        credit_limit=body.credit_limit,
        seller_employee_id=body.seller_employee_id,
    )


def _address_out(geography: Geography | None, address: CustomerAddress) -> AddressOut:
    return AddressOut(
        department_id=geography.department_id if geography else None,
        municipality_id=geography.municipality_id if geography else None,
        district_id=geography.district_id if geography else None,
        department=address.department,
        department_code=address.department_code,
        municipality=address.municipality,
        municipality_code=address.municipality_code,
        district=address.district,
        district_code=address.district_code,
    )


def _delivery_out(item: DeliveryAddress) -> DeliveryAddressOut:
    return DeliveryAddressOut(
        id=item.id,
        label=item.label,
        address_line=item.address_line,
        address=_address_out(item.geography, item.address),
        latitude=item.latitude,
        longitude=item.longitude,
        contact_name=item.contact_name,
        phone=item.phone,
        is_default=item.is_default,
        is_active=item.is_active,
    )


def _out(customer: Customer) -> CustomerOut:
    draft = customer.draft
    return CustomerOut(
        id=customer.id,
        company_id=customer.company_id,
        code=customer.code,
        customer_type=draft.customer_type,
        name=draft.name,
        person_type=draft.person_type,
        taxpayer_category=draft.taxpayer_category,
        is_withholding_agent=draft.is_withholding_agent,
        commercial_name=draft.commercial_name,
        document_type=draft.document_type,
        document_number=draft.document_number,
        nrc=draft.nrc,
        activity_code=draft.activity_code,
        activity_name=customer.activity_name,
        address=_address_out(draft.geography, customer.address),
        address_line=draft.address_line,
        country_code=draft.country_code,
        country_name=customer.country_name,
        phone=draft.phone,
        email=draft.email,
        credit_days=draft.credit_days,
        credit_limit=draft.credit_limit,
        seller_employee_id=draft.seller_employee_id,
        is_active=customer.is_active,
        is_generic=customer.is_generic,
        branch_id=customer.branch_id,
        receivable_documents=customer.receivable_documents,
        tax_credit_missing=customer.tax_credit_missing,
        delivery_addresses=[_delivery_out(d) for d in customer.delivery_addresses],
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


def _state(value: object | None) -> dict[str, Any] | None:
    if isinstance(value, Customer):
        return _out(value).model_dump(mode="json")
    if isinstance(value, DeliveryAddress):
        return _delivery_out(value).model_dump(mode="json")
    return None


async def _record(
    audit: AuditService,
    request: Request,
    *,
    action: str,
    actor: uuid.UUID,
    company_id: uuid.UUID,
    resource_type: str,
    resource_id: uuid.UUID,
    before: object | None = None,
    after: object | None = None,
) -> None:
    await audit.record(
        action=action,
        user_id=actor,
        company_id=company_id,
        resource_type=resource_type,
        resource_id=str(resource_id),
        before_state=_state(before),
        after_state=_state(after),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        required=True,
    )


@router.get("", response_model=CustomerPage, summary="Listar clientes", dependencies=_READ)
async def list_customers(
    request: Request,
    use_cases: UseCases,
    search: Annotated[str | None, Query(max_length=120)] = None,
    customer_type: CustomerType | None = None,
    active: bool | None = None,
    include_generic: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    items, total = await use_cases.list_customers(
        request_company_id(request),
        CustomerFilters(
            search=search,
            customer_type=customer_type,
            active=active,
            include_generic=include_generic,
        ),
        page=page,
        size=size,
    )
    return {
        "items": [_out(item) for item in items],
        "meta": {"page": page, "size": size, "total": total, "pages": ceil(total / size)},
    }


@router.post(
    "",
    response_model=CustomerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un cliente",
    dependencies=_MANAGE,
)
async def create_customer(
    body: CustomerCreate,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> CustomerOut:
    company_id = request_company_id(request)
    customer = await use_cases.create_customer(company_id, _draft(body), current.id, code=body.code)
    await _record(
        audit,
        request,
        action="CREATE",
        actor=current.id,
        company_id=company_id,
        resource_type="sales_customer",
        resource_id=customer.id,
        after=customer,
    )
    return _out(customer)


@router.get(
    "/generic",
    response_model=CustomerOut,
    summary="Cliente «Consumidor final» de una sucursal",
    dependencies=_READ,
)
async def generic_customer(
    branch_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> CustomerOut:
    company_id = request_company_id(request)
    customer, created = await use_cases.generic_customer(company_id, branch_id, current.id)
    if created:
        await _record(
            audit,
            request,
            action="CREATE",
            actor=current.id,
            company_id=company_id,
            resource_type="sales_customer",
            resource_id=customer.id,
            after=customer,
        )
    return _out(customer)


@router.get(
    "/{customer_id}", response_model=CustomerOut, summary="Ficha del cliente", dependencies=_READ
)
async def get_customer(
    customer_id: uuid.UUID, request: Request, use_cases: UseCases
) -> CustomerOut:
    return _out(await use_cases.get_customer(request_company_id(request), customer_id))


@router.put(
    "/{customer_id}",
    response_model=CustomerOut,
    summary="Editar el cliente",
    dependencies=_MANAGE,
)
async def update_customer(
    customer_id: uuid.UUID,
    body: CustomerIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> CustomerOut:
    company_id = request_company_id(request)
    before = await use_cases.get_customer(company_id, customer_id)
    customer = await use_cases.update_customer(company_id, customer_id, _draft(body), current.id)
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        company_id=company_id,
        resource_type="sales_customer",
        resource_id=customer.id,
        before=before,
        after=customer,
    )
    return _out(customer)


@router.patch(
    "/{customer_id}/status",
    response_model=CustomerOut,
    summary="Activar o desactivar el cliente",
    dependencies=_MANAGE,
)
async def set_customer_status(
    customer_id: uuid.UUID,
    body: CustomerStatusIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> CustomerOut:
    company_id = request_company_id(request)
    before = await use_cases.get_customer(company_id, customer_id)
    customer = await use_cases.set_active(company_id, customer_id, body.is_active, current.id)
    if before.is_active != customer.is_active:
        await _record(
            audit,
            request,
            action="UPDATE",
            actor=current.id,
            company_id=company_id,
            resource_type="sales_customer",
            resource_id=customer.id,
            before=before,
            after=customer,
        )
    return _out(customer)


def _delivery_draft(body: DeliveryAddressIn) -> DeliveryAddressDraft:
    return DeliveryAddressDraft(
        label=body.label,
        address_line=body.address_line,
        geography=_geography(body.geography),
        latitude=body.latitude,
        longitude=body.longitude,
        contact_name=body.contact_name,
        phone=body.phone,
        is_default=body.is_default,
        is_active=body.is_active,
    )


@router.post(
    "/{customer_id}/delivery-addresses",
    response_model=DeliveryAddressOut,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar una dirección de entrega",
    dependencies=_MANAGE,
)
async def add_delivery_address(
    customer_id: uuid.UUID,
    body: DeliveryAddressIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> DeliveryAddressOut:
    company_id = request_company_id(request)
    address = await use_cases.save_delivery_address(company_id, customer_id, _delivery_draft(body))
    await _record(
        audit,
        request,
        action="CREATE",
        actor=current.id,
        company_id=company_id,
        resource_type="sales_customer_delivery_address",
        resource_id=address.id,
        after=address,
    )
    return _delivery_out(address)


@router.put(
    "/{customer_id}/delivery-addresses/{address_id}",
    response_model=DeliveryAddressOut,
    summary="Editar una dirección de entrega",
    dependencies=_MANAGE,
)
async def update_delivery_address(
    customer_id: uuid.UUID,
    address_id: uuid.UUID,
    body: DeliveryAddressIn,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> DeliveryAddressOut:
    company_id = request_company_id(request)
    customer = await use_cases.get_customer(company_id, customer_id)
    before = next((d for d in customer.delivery_addresses if d.id == address_id), None)
    address = await use_cases.save_delivery_address(
        company_id, customer_id, _delivery_draft(body), address_id=address_id
    )
    await _record(
        audit,
        request,
        action="UPDATE",
        actor=current.id,
        company_id=company_id,
        resource_type="sales_customer_delivery_address",
        resource_id=address.id,
        before=before,
        after=address,
    )
    return _delivery_out(address)


@router.delete(
    "/{customer_id}/delivery-addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar una dirección de entrega",
    dependencies=_MANAGE,
)
async def delete_delivery_address(
    customer_id: uuid.UUID,
    address_id: uuid.UUID,
    request: Request,
    current: CurrentUser,
    use_cases: UseCases,
    audit: Audit,
) -> None:
    company_id = request_company_id(request)
    removed = await use_cases.delete_delivery_address(company_id, customer_id, address_id)
    await _record(
        audit,
        request,
        action="DELETE",
        actor=current.id,
        company_id=company_id,
        resource_type="sales_customer_delivery_address",
        resource_id=address_id,
        before=removed,
    )
