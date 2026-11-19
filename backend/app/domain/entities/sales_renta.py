"""Clasificación de renta de una venta (anexos de ventas del F-07, desde enero de 2025).

Cada documento lleva el tipo de operación y el tipo de ingreso que se declaran en renta. No es una
clasificación de IVA: una venta exenta de IVA puede ser gravada en renta, así que se elige y no se
deduce de los montos. Fuente: Manual de anexos del F-07 V14 (DGII, enero 2025), columnas R y S del
anexo de contribuyentes y U y V del de consumidor final.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import BusinessRuleError

OPERATION_TYPES = {
    1: "Gravada",
    2: "No gravada o exenta",
    3: "Excluido o no constituye renta",
    4: "Mixta (gravada y exenta en el mismo documento)",
    12: "Ingresos ya retenidos en el F910",
    13: "Sujetos pasivos excluidos (art. 6 LISR)",
}

INCOME_TYPES = {
    1: "Profesiones, artes y oficios",
    2: "Actividades de servicios",
    3: "Actividades comerciales",
    4: "Actividades industriales",
    5: "Actividades agropecuarias",
    6: "Utilidades y dividendos",
    7: "Exportaciones de bienes",
    8: "Servicios realizados en el exterior y utilizados en El Salvador",
    9: "Exportaciones de servicios",
    10: "Otras rentas gravables",
    12: "Ingresos ya retenidos en el F910",
    13: "Sujetos pasivos excluidos (art. 6 LISR)",
}

#: Conceptos que aparecen en los dos catálogos: las dos columnas llevan el mismo valor.
SHARED_TYPES = (12, 13)


@dataclass(frozen=True, slots=True)
class RentaClassification:
    operation_type: int
    income_type: int


def validate_renta(operation_type: int | None, income_type: int | None) -> RentaClassification:
    if operation_type not in OPERATION_TYPES or income_type not in INCOME_TYPES:
        raise BusinessRuleError(
            "Elige el tipo de operación y el tipo de ingreso de renta.",
            code="sales_renta_invalid",
        )
    if (operation_type in SHARED_TYPES or income_type in SHARED_TYPES) and (
        operation_type != income_type
    ):
        raise BusinessRuleError(
            "Los ingresos ya retenidos en el F910 y los sujetos excluidos llevan el mismo código en "
            "el tipo de operación y en el tipo de ingreso.",
            code="sales_renta_invalid",
        )
    return RentaClassification(operation_type, income_type)
