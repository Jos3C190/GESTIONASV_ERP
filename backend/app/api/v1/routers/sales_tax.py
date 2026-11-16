"""Cálculo fiscal de documentos de venta (bloque V2a).

Solo previsualiza: no guarda nada, así que no registra auditoría. Los documentos que lo
usen (cotización, pedido, DTE) guardan y auditan su propio resultado.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.v1.company_access import request_company_id
from app.api.v1.deps import get_sales_tax_use_cases, require_any_permission
from app.api.v1.schemas.sales_tax import (
    TaxCalculationIn,
    TaxCalculationLineOut,
    TaxCalculationOut,
    TaxSummaryOut,
)
from app.application.sales_tax import CalculationLine, CalculationRequest, SalesTaxUseCases
from app.domain.entities.sales_tax import GlobalDiscounts, SalesDocumentKind

router = APIRouter(tags=["sales-tax"])

UseCases = Annotated[SalesTaxUseCases, Depends(get_sales_tax_use_cases)]


@router.post(
    "/sales/tax-calculation",
    response_model=TaxCalculationOut,
    summary="Calcula los montos fiscales de un documento de venta sin guardarlo",
    dependencies=[Depends(require_any_permission("sales_quotations:read", "sales:read"))],
)
async def calculate_sales_tax(
    body: TaxCalculationIn, request: Request, use_cases: UseCases
) -> TaxCalculationOut:
    document = SalesDocumentKind(body.document_type)
    result = await use_cases.calculate(
        request_company_id(request),
        CalculationRequest(
            document=document,
            customer_id=body.customer_id,
            lines=tuple(
                CalculationLine(
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    price_includes_vat=line.price_includes_vat,
                    discount=line.discount,
                )
                for line in body.lines
            ),
            discounts=GlobalDiscounts(
                taxed=body.global_discounts.taxed,
                exempt=body.global_discounts.exempt,
                not_subject=body.global_discounts.not_subject,
            ),
        ),
    )
    calculation = result.calculation
    summary = calculation.summary
    return TaxCalculationOut(
        document_type=document.value,
        customer_id=result.customer_id,
        customer_name=result.customer_name,
        prices_include_vat=document is SalesDocumentKind.INVOICE,
        lines=[
            TaxCalculationLineOut(
                product_id=product.product_id,
                sku=product.sku,
                name=product.name,
                hacienda_unit_code=product.unit_code,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount=line.discount,
                not_subject=line.not_subject,
                exempt=line.exempt,
                taxed=line.taxed,
                vat_item=line.vat_item,
            )
            for product, line in zip(result.products, calculation.lines, strict=True)
        ],
        summary=TaxSummaryOut(
            total_not_subject=summary.total_not_subject,
            total_exempt=summary.total_exempt,
            total_taxed=summary.total_taxed,
            subtotal_sales=summary.subtotal_sales,
            discount_not_subject=summary.discount_not_subject,
            discount_exempt=summary.discount_exempt,
            discount_taxed=summary.discount_taxed,
            total_discount=summary.total_discount,
            subtotal=summary.subtotal,
            vat=summary.vat,
            vat_perceived=summary.vat_perceived,
            vat_withheld=summary.vat_withheld,
            total_operation=summary.total_operation,
            total_to_pay=summary.total_to_pay,
            total_in_words=summary.total_in_words,
        ),
    )
