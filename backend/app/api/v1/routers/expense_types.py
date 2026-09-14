"""Read-only expense-type options for purchase-order forms."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.api.v1.company_access import request_company_id
from app.api.v1.deps import get_purchase_order_use_cases, require_permission
from app.api.v1.schemas.expense_type import ExpenseTypeResponse
from app.application.purchase_orders import PurchaseOrderUseCases

router = APIRouter(prefix="/expense-types", tags=["expense-types"])


@router.get(
    "",
    response_model=list[ExpenseTypeResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar tipos de gasto activos",
    dependencies=[Depends(require_permission("purchase_orders:read"))],
)
async def list_expense_types(
    request: Request,
    use_cases: PurchaseOrderUseCases = Depends(get_purchase_order_use_cases),
) -> list[ExpenseTypeResponse]:
    company_id = request_company_id(request)
    items = await use_cases.list_active_expense_types(company_id)
    return [
        ExpenseTypeResponse(
            id=item.id,
            name=item.name,
            description=item.description,
        )
        for item in items
    ]
