"""Render-neutral statements from the same authorized Kardex read snapshots."""

from decimal import Decimal

from app.domain.entities.inventory_kardex import LOCAL_TZ
from app.domain.entities.tabular_report import ReportSection, TabularReport

PRECISE = "#,##0.000000"
KINDS = {
    "opening": "Saldo inicial",
    "receipt": "Recepción",
    "issue": "Salida",
    "transfer": "Traslado / reubicación",
    "putaway": "Ubicación",
    "adjustment_in": "Ajuste de entrada",
    "adjustment_out": "Ajuste de salida",
    "customer_return": "Devolución de cliente",
    "supplier_return": "Devolución a proveedor",
    "cost_adjustment": "Aplicación de retaceo",
    "supplier_credit": "Crédito del proveedor",
}


def _number(value):
    return value if value is not None else "No reconstruible"


def _local(value):
    return value.astimezone(LOCAL_TZ).strftime("%d/%m/%Y %H:%M")


def _physical(data):
    rows = tuple(
        (
            _local(row["posted_at"]),
            KINDS.get(row["movement_type"], row["movement_type"]),
            row.get("document_reference") or row.get("source_reference") or "Sin referencia",
            row.get("receipt_lot_code")
            or row.get("receipt_lot_header_code")
            or row.get("lot_code")
            or "Sin lote",
            f"Desde: {row.get('from_location_code') or 'Externo / fuera del alcance'}\nHacia: {row.get('to_location_code') or 'Externo / fuera del alcance'}",
            row.get("operator") or "No disponible",
            row["incoming_quantity"],
            row["outgoing_quantity"],
            _number(row["balance_after"]),
        )
        for row in data["items"]
    )
    return (
        ReportSection(
            "Resumen físico",
            ("Saldo inicial", "Entradas filtradas", "Salidas filtradas", "Saldo al cierre"),
            (
                (
                    _number(data["opening_quantity"]),
                    data["incoming_quantity"],
                    data["outgoing_quantity"],
                    _number(data["closing_quantity"]),
                ),
            ),
            (1, 1, 1, 1),
            dict.fromkeys(range(4), PRECISE),
        ),
        ReportSection(
            "Movimientos físicos",
            (
                "Fecha de registro",
                "Movimiento",
                "Documento",
                "Lote",
                "Recorrido",
                "Responsable",
                "Entrada",
                "Salida",
                "Saldo",
            ),
            rows,
            (1.4, 1.2, 1.5, 1.5, 2.4, 1.4, 0.8, 0.8, 0.9),
            dict.fromkeys(range(6, 9), PRECISE),
        ),
    )


def _valued(data):
    rows = []
    outgoing = {"issue", "supplier_return", "adjustment_out"}
    for row in data["entries"]:
        qty = row["quantity_base"]
        # Adjustments of value do not invent a physical incoming quantity.
        signed = -qty if row["kind"] in outgoing else qty
        document = row.get("document_reference") or row["source_reference"]
        if row.get("receipt_lot_code"):
            document += f"\nLote: {row['receipt_lot_code']}"
        rows.append(
            (
                row["accounting_date"].strftime("%d/%m/%Y"),
                KINDS.get(row["kind"], row["kind"]),
                document,
                row.get("operator") or "No disponible",
                signed,
                row.get("applied_unit_cost")
                if row.get("applied_unit_cost") is not None
                else "No aplica",
                row["inventory_delta"],
                row["balance_quantity"],
                row["balance_value"],
                row["average_unit_cost"],
            )
        )
    return (
        ReportSection(
            "Resumen valorado",
            (
                "Cantidad inicial",
                "Valor inicial",
                "Variación de valor",
                "Cantidad final",
                "Valor final",
            ),
            (
                (
                    _number(data["opening_quantity"]),
                    _number(data["opening_value"]),
                    _number(data["period_value_change"]),
                    _number(data["closing_quantity"]),
                    _number(data["closing_value"]),
                ),
            ),
            (1, 1, 1, 1, 1),
            dict.fromkeys(range(5), PRECISE),
        ),
        ReportSection(
            "Historial del costo",
            (
                "Fecha contable",
                "Evento",
                "Documento",
                "Responsable",
                "Cantidad +/-",
                "Costo aplicado",
                "Cambio de valor",
                "Saldo unidades",
                "Saldo valor",
                "Promedio histórico",
            ),
            tuple(rows),
            (1.1, 1.4, 1.6, 1.3, 0.8, 0.9, 1, 0.9, 1.1, 1.2),
            dict.fromkeys(range(4, 10), PRECISE),
        ),
    )


def _reconciliation(data):
    return (
        ReportSection(
            "Resumen de conciliación",
            ("Conciliados", "Con diferencia", "Sin valoración / base", "Valor del inventario"),
            (
                (
                    Decimal(data["reconciled_items"]),
                    Decimal(data["discrepant_items"]),
                    Decimal(data["unvalued_items"]),
                    _number(data["inventory_value"]),
                ),
            ),
            (1, 1, 1.5, 1.5),
            {0: "#,##0", 1: "#,##0", 2: "#,##0", 3: PRECISE},
        ),
        ReportSection(
            "Conciliación por producto",
            (
                "Código",
                "Producto",
                "Unidad",
                "Cantidad física",
                "Cantidad valorada",
                "Diferencia",
                "Costo promedio",
                "Valor del inventario",
            ),
            tuple(
                (
                    row["sku"] or "Sin SKU",
                    row["product_name"],
                    row["base_unit_symbol"],
                    _number(row["physical_quantity"]),
                    _number(row["valued_quantity"]),
                    _number(row["quantity_difference"]),
                    _number(row["average_unit_cost"]),
                    _number(row["inventory_value"]),
                )
                for row in data["items"]
            ),
            (1.3, 3.2, 0.8, 1.1, 1.1, 1, 1.2, 1.3),
            dict.fromkeys(range(3, 8), PRECISE),
        ),
    )


def kardex_report(kind: str, data: dict, filters: dict) -> TabularReport:
    context = data.get("context") or {}
    title, code, sections = {
        "physical": ("Kardex de movimientos físicos", "KARDEX-FISICO", _physical),
        "valuation": ("Kardex valorado", "KARDEX-VALORADO", _valued),
        "reconciliation": ("Conciliación de inventario", "CONCILIACION", _reconciliation),
    }[kind]
    metadata = [
        ("NIT", context.get("nit") or "No informado"),
        ("NRC", context.get("nrc") or "No informado"),
        (
            "Producto / código",
            " · ".join(
                filter(
                    None, (context.get("product_name") or "Todos los productos", context.get("sku"))
                )
            ),
        ),
        ("Unidad base", context.get("base_unit_symbol") or "La indicada en cada fila"),
        (
            "Alcance",
            f"{context.get('warehouse_code') or ''} {context.get('warehouse_name') or 'Toda la empresa'}",
        ),
        ("Sucursal", context.get("branch_name") or "Consolidado de la empresa"),
    ]
    if kind == "reconciliation":
        metadata.extend(
            (
                (
                    "Corte por registro",
                    data["as_of"].strftime("%d/%m/%Y") if data.get("as_of") else "Lectura actual",
                ),
                ("Consulta realizada", _local(data["generated_at"])),
                ("Moneda", data.get("currency") or "Sin valoración"),
            )
        )
    else:
        metadata.append(
            ("Período", f"{data['period_from']:%d/%m/%Y} al {data['period_to']:%d/%m/%Y}")
        )
        if kind == "valuation":
            metadata.append(
                ("Moneda", (data.get("setting") or {}).get("currency", "Sin valoración"))
            )
    metadata.extend((name, str(value)) for name, value in filters.items() if value)
    notes = [
        "Consulta de solo lectura. El archivo contiene todas las filas que cumplen los filtros, no solo la página visible.",
        "Cada producto conserva su unidad. No se suman cantidades de unidades distintas.",
    ]
    if kind == "physical":
        notes.extend(
            (
                data["balance_basis"],
                "El filtro de tipo o documento selecciona filas y totales de entradas/salidas; los saldos mantienen la secuencia completa del producto en la bodega.",
            )
        )
    elif kind == "valuation":
        notes.extend(
            (
                "El costo aplicado corresponde al valor de cada movimiento dividido entre sus unidades. Los ajustes solo de valor no tienen costo físico unitario.",
                "El promedio de cada fila es histórico. El saldo y el promedio actuales no sustituyen los importes guardados en movimientos anteriores.",
            )
        )
    else:
        notes.append(
            "El corte reconstruye lo registrado hasta el final del día en El Salvador. No es un recálculo por fecha contable ni incluye unidades pendientes de ingreso."
        )
        if data.get("unvalued_items"):
            notes.append(
                "Hay productos sin valoración verificable. El total suma únicamente los valores registrados del resultado filtrado."
            )
    return TabularReport(
        title,
        code,
        context.get("company_name") or "Empresa",
        tuple(metadata),
        sections(data),
        tuple(notes),
    )
