"""Build reports from persisted procurement records, without changing their costs."""

from app.domain.entities.purchase_consolidation import PurchaseConsolidation
from app.domain.entities.retaceo import Retaceo
from app.domain.entities.tabular_report import (
    ProcurementReportContext,
    ReportSection,
    TabularReport,
)

MONEY = "#,##0.00"
PRECISE = "#,##0.000000"
STATUS = {
    "draft": "Borrador",
    "frozen": "Congelado",
    "calculated": "Calculado",
    "verified": "Verificado",
    "closed": "Cerrado",
    "cancelled": "Cancelado",
}
CLASSES = {
    "freight": "Flete",
    "expense": "Otro gasto",
    "dai": "DAI",
    "import_vat": "IVA de importación",
}


def retaceo_report(item: Retaceo, context: ProcurementReportContext) -> TabularReport:
    details = tuple(
        (
            *context.product_labels.get(line.product_id, (str(line.product_id), "Producto")),
            context.unit_labels.get(line.unit_id, str(line.unit_id)),
            line.quantity,
            line.cost_fob,
            line.freight,
            line.expenses,
            line.dai,
            line.total_cost,
            line.unit_cost,
        )
        for line in item.details
    )
    costs = tuple(
        (
            CLASSES.get(cost.classification.value, cost.classification.value),
            cost.title,
            cost.incurred_on.strftime("%d/%m/%Y") if cost.incurred_on else "Sin fecha",
            cost.description or "",
            cost.amount,
            "; ".join(doc.file_name for doc in cost.documents) or "Sin adjuntos",
        )
        for cost in item.costs
        if cost.is_active
    )
    return TabularReport(
        title="Retaceo de compra",
        code=item.code,
        company_name=context.company_name,
        metadata=(
            ("Estado", STATUS.get(item.status.value, item.status.value)),
            ("NIT / NRC", f"{context.nit} / {context.nrc}"),
            ("Compra / orden", f"{context.purchase_code} / {context.order_code}"),
            ("Proveedor", context.supplier_name),
            ("Moneda", item.currency),
            ("País de origen", item.origin_country or "No informado"),
            ("Factura", item.import_invoice_number or "No informada"),
            (
                "Fecha de factura",
                item.import_invoice_date.strftime("%d/%m/%Y")
                if item.import_invoice_date
                else "No informada",
            ),
            ("Póliza", item.import_policy_number or "No informada"),
            (
                "Fecha de póliza",
                item.import_policy_date.strftime("%d/%m/%Y")
                if item.import_policy_date
                else "No informada",
            ),
        ),
        sections=(
            ReportSection(
                "Costos por producto",
                (
                    "Código",
                    "Producto",
                    "Unidad",
                    "Cantidad",
                    "FOB",
                    "Flete",
                    "Otros gastos",
                    "DAI",
                    "Costo total",
                    "Costo unitario",
                ),
                details,
                (1.3, 3.1, 1, 1, 1.2, 1.1, 1.2, 1.1, 1.3, 1.4),
                {3: PRECISE, **{n: MONEY for n in range(4, 9)}, 9: PRECISE},
            ),
            ReportSection(
                "Resumen del retaceo",
                (
                    "FOB",
                    "Flete",
                    "Otros gastos",
                    "DAI",
                    "Costo aterrizado",
                    "IVA de importación (fuera del costo)",
                ),
                (
                    (
                        item.total_fob,
                        item.total_freight,
                        item.total_expenses,
                        item.total_dai,
                        item.total_cost,
                        item.import_vat,
                    ),
                ),
                (1, 1, 1, 1, 1.5, 2),
                {index: MONEY for index in range(6)},
            ),
            ReportSection(
                "Gastos reales y respaldo",
                (
                    "Rubro",
                    "Concepto",
                    "Fecha",
                    "Descripción / referencia",
                    "Importe",
                    "Archivos adjuntos",
                ),
                costs,
                (1.2, 1.5, 1, 3, 1.1, 2.5),
                {4: MONEY},
            ),
        ),
        notes=(
            "Importes tomados del cálculo guardado. Descargar este reporte no modifica el retaceo ni el inventario.",
            "El IVA de importación se muestra por separado y no integra el costo aterrizado.",
            "El costo unitario de esta entrada y el costo promedio global del producto son datos distintos. Consulte la comparación de promedio en el sistema.",
            *((f"Observaciones: {item.notes}",) if item.notes else ()),
        ),
    )


def consolidation_report(
    item: PurchaseConsolidation, context: ProcurementReportContext
) -> TabularReport:
    rows = tuple(
        (
            line.product_sku,
            line.product_name,
            line.unit_name,
            line.branch_quantity,
            line.central_quantity,
            line.total_quantity,
        )
        for line in item.lines
    )
    origins = tuple(
        (
            line.product_sku,
            source.branch_name or "Sucursal",
            source.request_code,
            line.unit_name,
            source.requested_quantity,
            source.included_quantity,
            source.reason or "",
        )
        for line in item.lines
        for source in line.sources
    )
    return TabularReport(
        title="Consolidado general de compra",
        code=item.code,
        company_name=context.company_name,
        metadata=(
            ("Estado", STATUS.get(item.status.value, item.status.value)),
            ("NIT / NRC", f"{context.nit} / {context.nrc}"),
            ("Período", f"{item.period_start:%d/%m/%Y} al {item.period_end:%d/%m/%Y}"),
            ("Bodega central", item.central_warehouse_name or "Sin demanda central"),
        ),
        sections=(
            ReportSection(
                "Demanda consolidada por producto",
                (
                    "Código",
                    "Producto",
                    "Unidad",
                    "Sucursales",
                    "Demanda central",
                    "Total solicitado",
                ),
                rows,
                (1.5, 4, 1.5, 1.5, 1.5, 1.5),
                {3: PRECISE, 4: PRECISE, 5: PRECISE},
            ),
            ReportSection(
                "Solicitudes de origen",
                (
                    "Producto",
                    "Sucursal",
                    "Solicitud",
                    "Unidad",
                    "Original",
                    "Incluida",
                    "Motivo de ajuste",
                ),
                origins,
                (1.5, 2.5, 1.3, 1.2, 1, 1, 2.5),
                {4: PRECISE, 5: PRECISE},
            ),
        ),
        notes=(
            "Reporte interno de demanda guardada. Cada producto y unidad conserva su propia cantidad; no se suman unidades distintas.",
            "Las solicitudes de cotización por proveedor se generan por separado y pueden reunir varios productos de este consolidado.",
            *((f"Observaciones: {item.notes}",) if item.notes else ()),
        ),
    )
