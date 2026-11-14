"""Validation and by-FOB arithmetic for the fixed retaceo components."""

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


def distribute_by_fob(
    sources: tuple[RetaceoSourceLine, ...],
    costs: tuple[RetaceoCost, ...],
    *,
    freight: Decimal,
    dai: Decimal,
    enforce_fixed: bool = True,
) -> tuple[RetaceoCost, ...]:
    """Distribute every active cost across the received lines in proportion to their FOB.

    Freight and DAI are amounts typed by the operator; they must match their single
    component. Nothing else is entered per line: the split is always arithmetic.
    """
    if enforce_fixed:
        for kind, value in (
            (RetaceoCostClass.FREIGHT, freight),
            (RetaceoCostClass.DAI, dai),
        ):
            if not value.is_finite() or value < 0:
                raise ValidationError(
                    "Flete y seguro y DAI requieren un importe mayor o igual a cero; escribe 0 si no aplican.",
                    code="retaceo_fixed_amount_invalid",
                )
            rows = [row for row in costs if row.is_active and row.classification is kind]
            if len(rows) > 1 or sum((row.amount for row in rows), Decimal("0")) != value:
                raise ValidationError(
                    "Flete y seguro y DAI deben coincidir con su único componente; no los dupliques como gastos adicionales.",
                    code="retaceo_fixed_amount_mismatch",
                )
    result = []
    for cost in costs:
        if not cost.is_active:
            result.append(cost)
            continue
        allocation = calculate_retaceo_allocation(
            sources,
            total_freight=cost.amount
            if cost.classification is RetaceoCostClass.FREIGHT
            else Decimal("0"),
            total_dai=cost.amount if cost.classification is RetaceoCostClass.DAI else Decimal("0"),
            total_expenses=cost.amount
            if cost.classification is RetaceoCostClass.EXPENSE
            else Decimal("0"),
        )
        result.append(
            replace(
                cost,
                allocations=tuple(
                    RetaceoCostAllocation(
                        line.purchase_detail_id,
                        line.freight
                        if cost.classification is RetaceoCostClass.FREIGHT
                        else line.dai
                        if cost.classification is RetaceoCostClass.DAI
                        else line.expenses,
                    )
                    for line in allocation.lines
                ),
            )
        )
    return tuple(result)
