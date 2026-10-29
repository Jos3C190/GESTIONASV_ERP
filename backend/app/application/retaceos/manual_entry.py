"""Validation and arithmetic for explicitly entered fixed retaceo components."""

from dataclasses import replace
from decimal import Decimal

from app.core.exceptions import BusinessRuleError, ValidationError
from app.domain.entities.purchase import Purchase
from app.domain.entities.retaceo import (
    RetaceoCost,
    RetaceoCostAllocation,
    RetaceoCostClass,
    RetaceoImportData,
    RetaceoSourceLine,
    calculate_retaceo_allocation,
)


def protected_invoice(purchase: Purchase, data: RetaceoImportData | None) -> RetaceoImportData:
    fields = data or RetaceoImportData()
    if (
        fields.import_invoice_number is not None
        and fields.import_invoice_number != purchase.supplier_invoice_number
    ) or (
        fields.import_invoice_date is not None
        and fields.import_invoice_date != purchase.supplier_invoice_date
    ):
        raise BusinessRuleError(
            "La factura y su fecha ya están confirmadas en la recepción. Conserve ese documento y gestione su corrección desde el origen.",
            code="retaceo_invoice_locked",
        )
    return replace(
        fields,
        import_invoice_number=purchase.supplier_invoice_number,
        import_invoice_date=purchase.supplier_invoice_date,
    )


def fixed_allocations(
    sources: tuple[RetaceoSourceLine, ...],
    costs: tuple[RetaceoCost, ...],
    *,
    freight: Decimal,
    dai: Decimal,
    vat: Decimal,
) -> tuple[RetaceoCost, ...]:
    # Inputs are amounts typed by the operator. Only distribution arithmetic is automatic.
    result = []
    for kind, value in (
        (RetaceoCostClass.FREIGHT, freight),
        (RetaceoCostClass.DAI, dai),
        (RetaceoCostClass.IMPORT_VAT, vat),
    ):
        if not value.is_finite() or value < 0:
            raise ValidationError(
                "Flete, DAI e IVA requieren un importe explícito mayor o igual a cero.",
                code="retaceo_fixed_amount_invalid",
            )
        rows = [row for row in costs if row.is_active and row.classification is kind]
        if len(rows) > 1 or sum((row.amount for row in rows), Decimal("0")) != value:
            raise ValidationError(
                "Flete, DAI e IVA deben coincidir con su único componente. Evite duplicarlos como otros gastos.",
                code="retaceo_fixed_amount_mismatch",
            )
    for cost in costs:
        result_cost = cost
        if cost.is_active and cost.classification in {
            RetaceoCostClass.FREIGHT,
            RetaceoCostClass.DAI,
        }:
            allocation = calculate_retaceo_allocation(
                sources,
                total_freight=cost.amount
                if cost.classification is RetaceoCostClass.FREIGHT
                else Decimal("0"),
                total_dai=cost.amount
                if cost.classification is RetaceoCostClass.DAI
                else Decimal("0"),
                total_expenses=Decimal("0"),
            )
            result_cost = replace(
                cost,
                allocations=tuple(
                    RetaceoCostAllocation(
                        line.purchase_detail_id,
                        line.freight
                        if cost.classification is RetaceoCostClass.FREIGHT
                        else line.dai,
                    )
                    for line in allocation.lines
                ),
            )
        result.append(result_cost)
    return tuple(result)
