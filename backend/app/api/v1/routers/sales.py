"""Company and branch scoped sales documents and physical fulfilment."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from app.api.v1.company_access import get_branch_context, request_company_id, resolve_branch_scope
from app.api.v1.deps import (
    CurrentUser,
    SessionDep,
    get_audit_service,
    get_check_permission_use_case,
    get_sales_delivery_service,
    get_sales_return_service,
    get_sales_service,
    require_any_permission,
    require_permission,
)
from app.api.v1.schemas.sales import (
    SalesCatalogItemOut,
    SalesDeliveryCancellation,
    SalesDeliveryCreate,
    SalesDeliveryDraftUpdate,
    SalesDeliveryOut,
    SalesDeliveryStockLineOut,
    SalesDocumentAction,
)
from app.api.v1.schemas.sales_return import (
    SalesReturnableAllocationOut,
    SalesReturnCancellation,
    SalesReturnCreate,
    SalesReturnOut,
    SalesReturnResolve,
)
from app.application.audit.audit_service import AuditService
from app.application.inventory import InventoryApplicationError
from app.application.rbac.check_permission import CheckPermissionUseCase
from app.application.sales.deliveries import SalesDeliveryService
from app.application.sales.returns import SalesReturnService
from app.application.sales.service import SalesService
from app.core.exceptions import AuthorizationError
from app.domain.entities.inventory import InventoryOperationError

T = TypeVar("T")

router = APIRouter(prefix="/sales", tags=["sales"])
SalesServiceDep = Annotated[SalesService, Depends(get_sales_service)]
SalesDeliveryServiceDep = Annotated[SalesDeliveryService, Depends(get_sales_delivery_service)]
SalesReturnServiceDep = Annotated[SalesReturnService, Depends(get_sales_return_service)]
AuditDep = Annotated[AuditService, Depends(get_audit_service)]


async def _delivery_call(awaitable: Awaitable[T]) -> T:
    try:
        return await awaitable
    except (InventoryApplicationError, InventoryOperationError) as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "sales_delivery_concurrency_conflict",
                "message": "El inventario cambió durante la operación. Recargue e intente de nuevo.",
            },
        ) from exc


async def _list_scope(
    session: SessionDep, current: CurrentUser, company_id: uuid.UUID, branch_id: uuid.UUID | None
) -> tuple[uuid.UUID | None, tuple[uuid.UUID, ...] | None]:
    context = await get_branch_context(session, current, company_id)
    if branch_id is not None:
        await resolve_branch_scope(session, current, company_id, branch_id)
        return branch_id, None
    if context.access_all_branches:
        return None, None
    return None, tuple(item.id for item in context.branches)


async def _authorize_sale_branch(
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    service: SalesService,
    sale_id: uuid.UUID,
) -> None:
    row = await service.get_sale(company_id, sale_id)
    await resolve_branch_scope(session, current, company_id, row.branch_id)


async def _authorize_delivery_branch(
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    service: SalesDeliveryService,
    delivery_id: uuid.UUID,
) -> None:
    row = await service.delivery_header(company_id, delivery_id)
    await resolve_branch_scope(session, current, company_id, row.branch_id)


async def _authorize_return_branch(
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    service: SalesReturnService,
    return_id: uuid.UUID,
) -> None:
    row = await service.return_header(company_id, return_id)
    await resolve_branch_scope(session, current, company_id, row.branch_id)


async def _authorize_return_evidence_access(
    session: SessionDep,
    current: CurrentUser,
    company_id: uuid.UUID,
    checker: CheckPermissionUseCase,
) -> None:
    context = await get_branch_context(session, current, company_id)
    if not context.access_all_branches:
        raise AuthorizationError(
            "La evidencia del archivo general requiere alcance empresarial completo.",
            code="sales_return_evidence_scope_forbidden",
        )
    if not current.is_superuser:
        result = await checker.execute(current.id, company_id, "documents:read")
        if not result.allowed:
            raise AuthorizationError(
                "No tiene permiso para consultar documentos de evidencia.",
                code="sales_return_evidence_read_forbidden",
            )


@router.get(
    "/catalog",
    response_model=list[SalesCatalogItemOut],
    dependencies=[Depends(require_any_permission("sales_quotations:manage", "sales:manage"))],
)
async def sales_catalog(
    service: SalesServiceDep, company_id: Annotated[uuid.UUID, Depends(request_company_id)]
) -> list[dict[str, Any]]:
    return await service.catalog(company_id)


@router.get(
    "/returns",
    response_model=list[SalesReturnOut],
    dependencies=[Depends(require_permission("sales_returns:read"))],
)
async def list_sales_returns(
    session: SessionDep,
    current: CurrentUser,
    service: SalesReturnServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
    branch_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    _scoped_branch, branch_ids = await _list_scope(session, current, company_id, branch_id)
    if branch_id is not None:
        branch_ids = (branch_id,)
    return await service.list_all(company_id, branch_ids=branch_ids)


@router.get(
    "/returns/{return_id}",
    response_model=SalesReturnOut,
    dependencies=[Depends(require_permission("sales_returns:read"))],
)
async def get_sales_return(
    return_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    service: SalesReturnServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
) -> dict[str, Any]:
    await _authorize_return_branch(session, current, company_id, service, return_id)
    return await service.return_out(company_id, return_id)


@router.get(
    "/{sale_id}/returnable-allocations",
    response_model=list[SalesReturnableAllocationOut],
    dependencies=[Depends(require_permission("sales_returns:manage"))],
)
async def returnable_sale_allocations(
    sale_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    sales: SalesServiceDep,
    service: SalesReturnServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
) -> list[dict[str, Any]]:
    await _authorize_sale_branch(session, current, company_id, sales, sale_id)
    return await service.returnable_allocations(company_id, sale_id)


@router.get(
    "/{sale_id}/returns",
    response_model=list[SalesReturnOut],
    dependencies=[Depends(require_permission("sales_returns:read"))],
)
async def list_sale_returns(
    sale_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    sales: SalesServiceDep,
    service: SalesReturnServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
) -> list[dict[str, Any]]:
    await _authorize_sale_branch(session, current, company_id, sales, sale_id)
    return await service.list_for_sale(company_id, sale_id)


@router.post(
    "/{sale_id}/returns",
    response_model=SalesReturnOut,
    status_code=201,
    dependencies=[Depends(require_permission("sales_returns:manage"))],
)
async def create_sale_return(
    sale_id: uuid.UUID,
    body: SalesReturnCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    sales: SalesServiceDep,
    service: SalesReturnServiceDep,
    checker: Annotated[CheckPermissionUseCase, Depends(get_check_permission_use_case)],
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=120)],
) -> dict[str, Any]:
    await _authorize_sale_branch(session, current, company_id, sales, sale_id)
    if body.document_ids:
        await _authorize_return_evidence_access(session, current, company_id, checker)
    return await _delivery_call(
        service.create_draft(
            company_id=company_id,
            actor_id=current.id,
            sale_id=sale_id,
            lines=[line.model_dump(mode="python") for line in body.lines],
            document_ids=body.document_ids,
            notes=body.notes,
            idempotency_key=idempotency_key,
            request=request,
        )
    )


@router.post(
    "/returns/{return_id}/receive",
    response_model=SalesReturnOut,
    dependencies=[Depends(require_permission("sales_returns:receive"))],
)
async def receive_sale_return(
    return_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: SalesReturnServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=120)],
) -> dict[str, Any]:
    await _authorize_return_branch(session, current, company_id, service, return_id)
    return await service.receive(
        company_id=company_id,
        actor_id=current.id,
        return_id=return_id,
        idempotency_key=idempotency_key,
        request=request,
    )


@router.post(
    "/returns/{return_id}/resolve",
    response_model=SalesReturnOut,
    dependencies=[Depends(require_permission("sales_returns:resolve"))],
)
async def resolve_sale_return(
    return_id: uuid.UUID,
    body: SalesReturnResolve,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: SalesReturnServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=120)],
) -> dict[str, Any]:
    await _authorize_return_branch(session, current, company_id, service, return_id)
    return await _delivery_call(
        service.resolve(
            company_id=company_id,
            actor_id=current.id,
            return_id=return_id,
            lines=[line.model_dump(mode="python") for line in body.lines],
            idempotency_key=idempotency_key,
            request=request,
        )
    )


@router.post(
    "/returns/{return_id}/cancel",
    response_model=SalesReturnOut,
    dependencies=[Depends(require_permission("sales_returns:cancel"))],
)
async def cancel_sale_return(
    return_id: uuid.UUID,
    body: SalesReturnCancellation,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: SalesReturnServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=120)],
) -> dict[str, Any]:
    await _authorize_return_branch(session, current, company_id, service, return_id)
    return await service.cancel_draft(
        company_id=company_id,
        actor_id=current.id,
        return_id=return_id,
        reason=body.reason,
        idempotency_key=idempotency_key,
        request=request,
    )


@router.get(
    "/{sale_id}/delivery-stock",
    response_model=list[SalesDeliveryStockLineOut],
    dependencies=[Depends(require_permission("sales_deliveries:manage"))],
)
async def delivery_stock_options(
    sale_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    service: SalesDeliveryServiceDep,
    sales: SalesServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
) -> list[dict[str, Any]]:
    await _authorize_sale_branch(session, current, company_id, sales, sale_id)
    return await service.stock_options(company_id, sale_id)


@router.get(
    "/{sale_id}/deliveries",
    response_model=list[SalesDeliveryOut],
    dependencies=[Depends(require_permission("sales_deliveries:read"))],
)
async def list_sale_deliveries(
    sale_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    service: SalesDeliveryServiceDep,
    sales: SalesServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
) -> list[dict[str, Any]]:
    await _authorize_sale_branch(session, current, company_id, sales, sale_id)
    return await service.deliveries_for_sale(company_id, sale_id)


@router.post(
    "/{sale_id}/deliveries",
    response_model=SalesDeliveryOut,
    status_code=201,
    dependencies=[Depends(require_permission("sales_deliveries:manage"))],
)
async def create_sale_delivery(
    sale_id: uuid.UUID,
    body: SalesDeliveryCreate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: SalesDeliveryServiceDep,
    sales: SalesServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=120)],
) -> dict[str, Any]:
    await _authorize_sale_branch(session, current, company_id, sales, sale_id)
    return await _delivery_call(
        service.create_draft(
            company_id=company_id,
            actor_id=current.id,
            sale_id=sale_id,
            assignments=[item.model_dump(mode="python") for item in body.assignments],
            notes=body.notes,
            idempotency_key=idempotency_key,
            request=request,
        )
    )


@router.get(
    "/deliveries/{delivery_id}",
    response_model=SalesDeliveryOut,
    dependencies=[Depends(require_permission("sales_deliveries:read"))],
)
async def get_sale_delivery(
    delivery_id: uuid.UUID,
    session: SessionDep,
    current: CurrentUser,
    service: SalesDeliveryServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
) -> dict[str, Any]:
    await _authorize_delivery_branch(session, current, company_id, service, delivery_id)
    return await service.delivery_out(company_id, delivery_id)


@router.put(
    "/deliveries/{delivery_id}",
    response_model=SalesDeliveryOut,
    dependencies=[Depends(require_permission("sales_deliveries:manage"))],
)
async def update_sale_delivery(
    delivery_id: uuid.UUID,
    body: SalesDeliveryDraftUpdate,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: SalesDeliveryServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
) -> dict[str, Any]:
    await _authorize_delivery_branch(session, current, company_id, service, delivery_id)
    return await _delivery_call(
        service.update_draft(
            company_id=company_id,
            actor_id=current.id,
            delivery_id=delivery_id,
            expected_version=body.expected_version,
            assignments=[item.model_dump(mode="python") for item in body.assignments],
            notes=body.notes,
            request=request,
        )
    )


@router.post(
    "/deliveries/{delivery_id}/confirm",
    response_model=SalesDeliveryOut,
    dependencies=[Depends(require_permission("sales_deliveries:confirm"))],
)
async def confirm_sale_delivery(
    delivery_id: uuid.UUID,
    body: SalesDocumentAction,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: SalesDeliveryServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=120)],
) -> dict[str, Any]:
    await _authorize_delivery_branch(session, current, company_id, service, delivery_id)
    return await _delivery_call(
        service.confirm(
            company_id=company_id,
            actor_id=current.id,
            delivery_id=delivery_id,
            expected_version=body.expected_version,
            idempotency_key=idempotency_key,
            request=request,
        )
    )


@router.post(
    "/deliveries/{delivery_id}/cancel",
    response_model=SalesDeliveryOut,
    dependencies=[Depends(require_permission("sales_deliveries:cancel"))],
)
async def cancel_sale_delivery(
    delivery_id: uuid.UUID,
    body: SalesDeliveryCancellation,
    request: Request,
    session: SessionDep,
    current: CurrentUser,
    service: SalesDeliveryServiceDep,
    company_id: Annotated[uuid.UUID, Depends(request_company_id)],
) -> dict[str, Any]:
    await _authorize_delivery_branch(session, current, company_id, service, delivery_id)
    return await _delivery_call(
        service.cancel_draft(
            company_id=company_id,
            actor_id=current.id,
            delivery_id=delivery_id,
            expected_version=body.expected_version,
            reason=body.reason,
            request=request,
        )
    )
