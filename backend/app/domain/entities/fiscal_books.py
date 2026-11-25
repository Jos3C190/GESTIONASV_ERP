"""Libros de IVA y anexos del F-07 de un mes (dominio puro).

Fuentes:
- Manual de usuario para carga de archivo de los anexos del F-07, V14 (DGII, enero 2025):
  anexo 1 (contribuyentes, 20 columnas), anexo 2 (consumidor final, 23), anexo 3 (compras, 21),
  anexo 9 (casilla 169, percepción del 1 % cobrada, 10) y documentos anulados (10).
- Código Tributario art. 141 y su reglamento, arts. 83, 85, 86 y 87: los tres libros.
- Plantilla «PLANTILLAS IVA F-07» v11.7.4 de contaportable, que usan los contadores.

Reglas entre meses (las mismas del proyecto de referencia, probadas con el portal):
- CCF y sus notas: un documento invalidado sale del anexo 1 de su mes y va a los anulados de ese
  mes (se invalida hasta el décimo día hábil del mes siguiente, el plazo de la declaración).
- Factura: su mes la cuenta si se invalidó después; el mes de la invalidación la resta con una
  fila negativa con su fecha original (art. 111 CT) y la reporta en anulados. Igual resta el mes
  de un evento de retorno (art. 87 del reglamento).
- Los anexos no llevan negativos, salvo esas filas del anexo 2. Las notas de crédito van en el
  anexo 1 con su tipo (05) y en positivo: el portal las resta. En los libros restan.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.core.exceptions import BusinessRuleError

ZERO = Decimal("0")
CENT = Decimal("0.01")
VAT_RATE = Decimal("0.13")

CONTRIBUTOR_TYPES = ("03", "05", "06")
CONSUMER_TYPES = ("01",)
CREDIT_NOTE = "05"
DTE_CLASS = 4
DUI_LENGTH = 9
CONTROL_PARTS = 4  # DTE-TT-M001P001-000000000000001
LAST_MONTH = 12

MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)

DOCUMENT_TYPE_LABELS = {
    "01": "Factura",
    "03": "Crédito fiscal",
    "05": "Nota de crédito",
    "06": "Nota de débito",
    "12": "Declaración de mercancías",
    "13": "Mandamiento de ingreso",
}


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def compact(code: str | None) -> str:
    """Número de control o código de generación sin guiones, como piden los anexos."""

    return (code or "").replace("-", "").upper()


@dataclass(frozen=True)
class Period:
    year: int
    month: int

    @classmethod
    def parse(cls, value: str) -> Period:
        match = re.fullmatch(r"(\d{4})-(\d{2})", value)
        if not match or not 1 <= int(match.group(2)) <= LAST_MONTH:
            raise ValueError("fiscal_book_period_invalid")
        return cls(int(match.group(1)), int(match.group(2)))

    @property
    def first(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def last(self) -> date:
        return date(self.year, self.month, calendar.monthrange(self.year, self.month)[1])

    @property
    def key(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def label(self) -> str:
        return f"{MONTHS[self.month - 1]} de {self.year}"

    def contains(self, day: date | None) -> bool:
        return day is not None and self.first <= day <= self.last


@dataclass(frozen=True)
class Party:
    """Cliente o proveedor tal como quedó en el documento, con identificadores sin guiones."""

    name: str
    nit: str | None = None
    nrc: str | None = None
    dui: str | None = None

    def annex_ids(self) -> tuple[str, str]:
        """(NIT o NRC, DUI): uno de los dos, nunca ambos (manual F-07 V14)."""

        nit = digits(self.nit)
        if len(nit) == DUI_LENGTH:
            return "", nit
        if nit:
            return nit, ""
        dui = digits(self.dui)
        if dui:
            return "", dui
        return digits(self.nrc), ""

    @property
    def registry(self) -> str:
        """NRC para los libros; sin NRC, el identificador del anexo."""

        nrc = digits(self.nrc)
        if nrc:
            return nrc
        nit, dui = self.annex_ids()
        return nit or dui


@dataclass(frozen=True)
class SaleDocument:
    document_type: str
    issued_on: date
    control_number: str
    generation_code: str
    seal: str
    receiver: Party
    exempt: Decimal
    not_subject: Decimal
    # En la factura (01) el gravado incluye el IVA; en CCF y notas va sin IVA.
    taxed: Decimal
    vat: Decimal
    perception: Decimal = ZERO
    renta_operation: int | None = None
    renta_income: int | None = None
    invalidated_on: date | None = None

    @property
    def point_of_sale(self) -> str:
        parts = self.control_number.split("-")
        return parts[2] if len(parts) == CONTROL_PARTS else ""

    @property
    def total(self) -> Decimal:
        return (
            self.exempt
            + self.not_subject
            + self.taxed
            + (ZERO if self.document_type in CONSUMER_TYPES else self.vat)
        )


@dataclass(frozen=True)
class ReturnEvent:
    invoice: SaleDocument
    returned_on: date
    generation_code: str
    seal: str
    exempt: Decimal
    not_subject: Decimal
    taxed: Decimal  # con IVA, como la factura


@dataclass(frozen=True)
class PurchaseDocument:
    purchase_code: str
    issued_on: date
    document_class: int
    document_type: str
    number: str
    supplier: Party
    exempt: Decimal
    taxed: Decimal
    vat: Decimal
    renta_operation: int
    renta_classification: int
    renta_sector: int
    renta_cost_type: int

    @property
    def is_import(self) -> bool:
        return self.document_type in ("12", "13")

    @property
    def annex_number(self) -> str:
        return compact(self.number) if self.document_class == DTE_CLASS else self.number.strip()


def _amount(value: Decimal) -> str:
    return f"{money(value):.2f}"


def _text(value: str | None) -> str:
    """Texto limpio para el CSV: sin punto y coma, comillas, apóstrofos ni saltos de línea."""

    cleaned = re.sub(r"[;\"'\r\n\t]", " ", value or "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _day(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _renta(value: int | None) -> str:
    return str(value) if value is not None else "0"


# --- Anexos -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ContributorRow:
    """Anexo 1: un renglón por CCF, nota de crédito o de débito vigente."""

    document: SaleDocument

    @property
    def total(self) -> Decimal:
        doc = self.document
        return money(doc.exempt) + money(doc.not_subject) + money(doc.taxed) + money(doc.vat)

    def cells(self) -> list[str]:
        doc = self.document
        nit, dui = doc.receiver.annex_ids()
        return [
            _day(doc.issued_on),
            str(DTE_CLASS),
            doc.document_type,
            compact(doc.control_number),
            doc.seal,
            compact(doc.generation_code),
            "",
            nit,
            _text(doc.receiver.name),
            _amount(doc.exempt),
            _amount(doc.not_subject),
            _amount(doc.taxed),
            _amount(doc.vat),
            "0.00",
            "0.00",
            _amount(self.total),
            dui,
            _renta(doc.renta_operation),
            _renta(doc.renta_income),
            "1",
        ]


@dataclass(frozen=True)
class ConsumerRow:
    """Anexo 2: facturas de un día (o una fila negativa por invalidación o retorno)."""

    day: date
    first_code: str
    last_code: str
    first_control: str
    last_control: str
    point_of_sale: str
    exempt: Decimal
    not_subject: Decimal
    taxed: Decimal  # con IVA
    renta_operation: int | None
    renta_income: int | None
    documents: int = 1
    note: str = ""

    @property
    def negative(self) -> bool:
        return bool(self.note)

    @property
    def total(self) -> Decimal:
        return money(self.exempt) + money(self.not_subject) + money(self.taxed)

    def cells(self) -> list[str]:
        return [
            _day(self.day),
            str(DTE_CLASS),
            "01",
            "N/A",
            "N/A",
            "N/A",
            "N/A",
            compact(self.first_code),
            compact(self.last_code),
            "",
            _amount(self.exempt),
            "0.00",
            _amount(self.not_subject),
            _amount(self.taxed),
            "0.00",
            "0.00",
            "0.00",
            "0.00",
            "0.00",
            _amount(self.total),
            _renta(self.renta_operation),
            _renta(self.renta_income),
            "2",
        ]


@dataclass(frozen=True)
class AnnulledRow:
    document: SaleDocument

    def cells(self) -> list[str]:
        doc = self.document
        return [
            compact(doc.control_number),
            str(DTE_CLASS),
            "0",
            "0",
            doc.document_type,
            "D",
            doc.seal,
            "0",
            "0",
            compact(doc.generation_code),
        ]


@dataclass(frozen=True)
class PerceptionRow:
    """Anexo 9 (casilla 169): percepción del 1 % que la empresa cobró."""

    document: SaleDocument

    def cells(self) -> list[str]:
        doc = self.document
        nit, dui = doc.receiver.annex_ids()
        return [
            nit,
            _day(doc.issued_on),
            doc.document_type,
            compact(doc.control_number),
            doc.seal,
            compact(doc.generation_code),
            _amount(doc.taxed),
            _amount(doc.perception),
            dui,
            "9",
        ]


@dataclass(frozen=True)
class PurchaseRow:
    """Anexo 3: un renglón por documento de proveedor."""

    document: PurchaseDocument

    @property
    def internal_exempt(self) -> Decimal:
        return ZERO if self.document.is_import else self.document.exempt

    @property
    def import_exempt(self) -> Decimal:
        return self.document.exempt if self.document.is_import else ZERO

    @property
    def internal_taxed(self) -> Decimal:
        return ZERO if self.document.is_import else self.document.taxed

    @property
    def import_taxed(self) -> Decimal:
        return self.document.taxed if self.document.is_import else ZERO

    @property
    def total(self) -> Decimal:
        """Columnas G a M, sin el crédito fiscal (manual F-07 V14, anexo de compras, columna O)."""

        return money(self.document.exempt) + money(self.document.taxed)

    def cells(self) -> list[str]:
        doc = self.document
        nit, dui = doc.supplier.annex_ids()
        return [
            _day(doc.issued_on),
            str(doc.document_class),
            doc.document_type,
            _text(doc.annex_number),
            nit,
            _text(doc.supplier.name),
            _amount(self.internal_exempt),
            "0.00",
            _amount(self.import_exempt),
            _amount(self.internal_taxed),
            "0.00",
            _amount(self.import_taxed),
            "0.00",
            _amount(doc.vat),
            _amount(self.total),
            dui,
            str(doc.renta_operation),
            str(doc.renta_classification),
            str(doc.renta_sector),
            str(doc.renta_cost_type),
            "3",
        ]


def _vigent_in(document: SaleDocument, period: Period) -> bool:
    """La factura cuenta en su mes salvo que se haya invalidado dentro de ese mismo mes."""

    if not period.contains(document.issued_on):
        return False
    if document.document_type in CONSUMER_TYPES:
        return document.invalidated_on is None or document.invalidated_on > period.last
    return document.invalidated_on is None


def _order(document: SaleDocument) -> tuple[date, str]:
    return document.issued_on, document.control_number


def contributor_rows(documents: Iterable[SaleDocument], period: Period) -> list[ContributorRow]:
    chosen = [
        doc
        for doc in documents
        if doc.document_type in CONTRIBUTOR_TYPES and _vigent_in(doc, period)
    ]
    return [ContributorRow(doc) for doc in sorted(chosen, key=_order)]


def consumer_rows(
    documents: Iterable[SaleDocument], returns: Iterable[ReturnEvent], period: Period
) -> list[ConsumerRow]:
    docs = list(documents)
    groups: dict[tuple[date, int | None, int | None], list[SaleDocument]] = {}
    for doc in sorted(docs, key=_order):
        if doc.document_type in CONSUMER_TYPES and _vigent_in(doc, period):
            groups.setdefault((doc.issued_on, doc.renta_operation, doc.renta_income), []).append(
                doc
            )
    rows = [
        ConsumerRow(
            day=day,
            first_code=items[0].generation_code,
            last_code=items[-1].generation_code,
            first_control=items[0].control_number,
            last_control=items[-1].control_number,
            point_of_sale=", ".join(sorted({item.point_of_sale for item in items})),
            exempt=sum((item.exempt for item in items), ZERO),
            not_subject=sum((item.not_subject for item in items), ZERO),
            taxed=sum((item.taxed for item in items), ZERO),
            renta_operation=operation,
            renta_income=income,
            documents=len(items),
        )
        for (day, operation, income), items in groups.items()
    ]
    for doc in sorted(docs, key=_order):
        if (
            doc.document_type in CONSUMER_TYPES
            and period.contains(doc.invalidated_on)
            and doc.issued_on < period.first
        ):
            rows.append(
                ConsumerRow(
                    day=doc.issued_on,
                    first_code=doc.generation_code,
                    last_code=doc.generation_code,
                    first_control=doc.control_number,
                    last_control=doc.control_number,
                    point_of_sale=doc.point_of_sale,
                    exempt=-doc.exempt,
                    not_subject=-doc.not_subject,
                    taxed=-doc.taxed,
                    renta_operation=doc.renta_operation,
                    renta_income=doc.renta_income,
                    note=f"Invalidada el {_day(doc.invalidated_on)}"
                    if doc.invalidated_on
                    else "Invalidada",
                )
            )
    for event in sorted(returns, key=lambda item: (item.returned_on, item.generation_code)):
        if not period.contains(event.returned_on):
            continue
        invoice = event.invoice
        rows.append(
            ConsumerRow(
                day=invoice.issued_on,
                first_code=invoice.generation_code,
                last_code=invoice.generation_code,
                first_control=invoice.control_number,
                last_control=invoice.control_number,
                point_of_sale=invoice.point_of_sale,
                exempt=-event.exempt,
                not_subject=-event.not_subject,
                taxed=-event.taxed,
                renta_operation=invoice.renta_operation,
                renta_income=invoice.renta_income,
                note=f"Evento de retorno del {_day(event.returned_on)}",
            )
        )
    return rows


def annulled_rows(documents: Iterable[SaleDocument], period: Period) -> list[AnnulledRow]:
    chosen = []
    for doc in documents:
        if doc.invalidated_on is None:
            continue
        if doc.document_type in CONSUMER_TYPES:
            if period.contains(doc.invalidated_on):
                chosen.append(doc)
        elif doc.document_type in CONTRIBUTOR_TYPES and period.contains(doc.issued_on):
            chosen.append(doc)
    return [AnnulledRow(doc) for doc in sorted(chosen, key=_order)]


def perception_rows(documents: Iterable[SaleDocument], period: Period) -> list[PerceptionRow]:
    return [
        PerceptionRow(row.document)
        for row in contributor_rows(documents, period)
        if row.document.perception > ZERO
    ]


def purchase_rows(purchases: Iterable[PurchaseDocument], period: Period) -> list[PurchaseRow]:
    chosen = [doc for doc in purchases if period.contains(doc.issued_on)]
    return [
        PurchaseRow(doc)
        for doc in sorted(chosen, key=lambda item: (item.issued_on, item.annex_number))
    ]


# --- Libros -------------------------------------------------------------------------------------


def _sign(document_type: str) -> Decimal:
    return Decimal("-1") if document_type == CREDIT_NOTE else Decimal("1")


def _signed(sign: Decimal, value: Decimal) -> Decimal:
    """Monto con el signo del libro, sin «-0.00» cuando es cero."""

    result = sign * money(value)
    return result if result else abs(result)


@dataclass(frozen=True)
class ContributorBookLine:
    number: int
    issued_on: date
    document_type: str
    generation_code: str
    control_number: str
    customer: str
    registry: str
    exempt: Decimal
    not_subject: Decimal
    taxed: Decimal
    vat: Decimal
    perception: Decimal
    total: Decimal


@dataclass(frozen=True)
class ConsumerBookLine:
    day: date
    first_control: str
    last_control: str
    point_of_sale: str
    exempt: Decimal
    not_subject: Decimal
    taxed: Decimal
    exports: Decimal
    total: Decimal
    third_parties: Decimal
    note: str


@dataclass(frozen=True)
class PurchaseBookLine:
    number: int
    issued_on: date
    document_type: str
    document_number: str
    registry: str
    excluded_subject_id: str
    supplier: str
    internal_exempt: Decimal
    import_exempt: Decimal
    internal_taxed: Decimal
    import_taxed: Decimal
    vat: Decimal
    perception: Decimal
    total: Decimal
    third_party_withholding: Decimal
    excluded_subjects: Decimal


def _totals(lines: Sequence[object], fields: Sequence[str]) -> dict[str, Decimal]:
    return {name: sum((getattr(line, name) for line in lines), ZERO) for name in fields}


def contributor_book(rows: Sequence[ContributorRow]) -> list[ContributorBookLine]:
    lines = []
    for index, row in enumerate(rows, start=1):
        doc = row.document
        sign = _sign(doc.document_type)
        lines.append(
            ContributorBookLine(
                number=index,
                issued_on=doc.issued_on,
                document_type=doc.document_type,
                generation_code=doc.generation_code,
                control_number=doc.control_number,
                customer=doc.receiver.name,
                registry=doc.receiver.registry,
                exempt=_signed(sign, doc.exempt),
                not_subject=_signed(sign, doc.not_subject),
                taxed=_signed(sign, doc.taxed),
                vat=_signed(sign, doc.vat),
                perception=_signed(sign, doc.perception),
                total=_signed(sign, row.total + doc.perception),
            )
        )
    return lines


def consumer_book(rows: Sequence[ConsumerRow]) -> list[ConsumerBookLine]:
    ordered = sorted(rows, key=lambda row: (row.negative, row.day, row.first_control))
    return [
        ConsumerBookLine(
            day=row.day,
            first_control=row.first_control,
            last_control=row.last_control,
            point_of_sale=row.point_of_sale,
            exempt=money(row.exempt),
            not_subject=money(row.not_subject),
            taxed=money(row.taxed),
            exports=ZERO,
            total=row.total,
            third_parties=ZERO,
            note=row.note,
        )
        for row in ordered
    ]


def purchase_book(rows: Sequence[PurchaseRow]) -> list[PurchaseBookLine]:
    lines = []
    for index, row in enumerate(rows, start=1):
        doc = row.document
        sign = _sign(doc.document_type)
        lines.append(
            PurchaseBookLine(
                number=index,
                issued_on=doc.issued_on,
                document_type=doc.document_type,
                document_number=doc.annex_number,
                registry=doc.supplier.registry,
                excluded_subject_id="",
                supplier=doc.supplier.name,
                internal_exempt=_signed(sign, row.internal_exempt),
                import_exempt=_signed(sign, row.import_exempt),
                internal_taxed=_signed(sign, row.internal_taxed),
                import_taxed=_signed(sign, row.import_taxed),
                vat=_signed(sign, doc.vat),
                perception=ZERO,
                total=_signed(sign, row.total),
                third_party_withholding=ZERO,
                excluded_subjects=ZERO,
            )
        )
    return lines


CONTRIBUTOR_TOTALS = ("exempt", "not_subject", "taxed", "vat", "perception", "total")
CONSUMER_TOTALS = ("exempt", "not_subject", "taxed", "exports", "total", "third_parties")
PURCHASE_TOTALS = (
    "internal_exempt",
    "import_exempt",
    "internal_taxed",
    "import_taxed",
    "vat",
    "perception",
    "total",
    "third_party_withholding",
    "excluded_subjects",
)


@dataclass(frozen=True)
class MonthSummary:
    """Resumen del mes: débito y crédito fiscal y percepción cobrada.

    ``balance`` es el impuesto del mes antes de remanentes, retenciones sufridas y anticipos, que
    el ERP no registra: débito - crédito + percepción cobrada.
    """

    contributor_taxed: Decimal
    contributor_vat: Decimal
    consumer_taxed_with_vat: Decimal
    consumer_vat: Decimal
    exempt_sales: Decimal
    not_subject_sales: Decimal
    debit: Decimal
    purchase_taxed: Decimal
    credit: Decimal
    perception_collected: Decimal
    balance: Decimal


def month_summary(
    contributors: Sequence[ContributorBookLine],
    consumers: Sequence[ConsumerBookLine],
    purchases: Sequence[PurchaseBookLine],
) -> MonthSummary:
    c = _totals(contributors, CONTRIBUTOR_TOTALS)
    f = _totals(consumers, CONSUMER_TOTALS)
    p = _totals(purchases, PURCHASE_TOTALS)
    consumer_vat = money(f["taxed"] * VAT_RATE / (1 + VAT_RATE))
    debit = c["vat"] + consumer_vat
    return MonthSummary(
        contributor_taxed=c["taxed"],
        contributor_vat=c["vat"],
        consumer_taxed_with_vat=f["taxed"],
        consumer_vat=consumer_vat,
        exempt_sales=c["exempt"] + f["exempt"],
        not_subject_sales=c["not_subject"] + f["not_subject"],
        debit=debit,
        purchase_taxed=p["internal_taxed"] + p["import_taxed"],
        credit=p["vat"],
        perception_collected=c["perception"],
        balance=debit - p["vat"] + c["perception"],
    )


# --- Mes completo ------------------------------------------------------------------------------


@dataclass(frozen=True)
class FiscalMonth:
    period: Period
    mode: str
    contributors: list[ContributorRow]
    consumers: list[ConsumerRow]
    annulled: list[AnnulledRow]
    perceptions: list[PerceptionRow]
    purchases: list[PurchaseRow]
    warnings: list[str] = field(default_factory=list)

    @property
    def contributor_book(self) -> list[ContributorBookLine]:
        return contributor_book(self.contributors)

    @property
    def consumer_book(self) -> list[ConsumerBookLine]:
        return consumer_book(self.consumers)

    @property
    def purchase_book(self) -> list[PurchaseBookLine]:
        return purchase_book(self.purchases)

    def summary(self) -> MonthSummary:
        return month_summary(self.contributor_book, self.consumer_book, self.purchase_book)

    @property
    def simulated(self) -> bool:
        return self.mode != "production"


def build_month(
    period: Period,
    mode: str,
    sales: Sequence[SaleDocument],
    returns: Sequence[ReturnEvent],
    purchases: Sequence[PurchaseDocument],
) -> FiscalMonth:
    contributors = contributor_rows(sales, period)
    consumers = consumer_rows(sales, returns, period)
    warnings = []
    unclassified = [
        row.document.control_number
        for row in contributors
        if row.document.renta_operation is None or row.document.renta_income is None
    ] + [
        row.first_control
        for row in consumers
        if row.renta_operation is None or row.renta_income is None
    ]
    if unclassified:
        warnings.append(
            f"{len(unclassified)} renglón(es) sin clasificación de renta: salen con 0 en las "
            "columnas de renta. Documentos: " + ", ".join(sorted(set(unclassified))[:10])
        )
    return FiscalMonth(
        period=period,
        mode=mode,
        contributors=contributors,
        consumers=consumers,
        annulled=annulled_rows(sales, period),
        perceptions=perception_rows(sales, period),
        purchases=purchase_rows(purchases, period),
        warnings=warnings,
    )


# --- CSV de carga -------------------------------------------------------------------------------

ANNEX_FILES = {
    "anexo1": ("Detalle de Ventas a Contribuyentes", "contributors"),
    "anexo2": ("Detalle Ventas a Consumidor Final", "consumers"),
    "anexo3": ("Detalle de Compras", "purchases"),
    "anexo9": ("Percepción IVA 1% efectuada por el declarante (casilla 169)", "perceptions"),
    "anulados": ("Documentos Emitidos, Anulados y Extraviados", "annulled"),
}


def annex_csv(
    rows: Iterable[ContributorRow | ConsumerRow | AnnulledRow | PerceptionRow | PurchaseRow],
) -> bytes:
    """CSV del portal: punto y coma, sin encabezados, Windows-1252, como lo guarda Excel."""

    text = "".join(";".join(row.cells()) + "\r\n" for row in rows)
    return text.encode("cp1252", errors="replace")


def annex_file_name(annex: str, period: Period, mode: str) -> str:
    """Nombre de hasta 25 caracteres en producción; fuera de ella lleva el modo y el portal lo rechaza."""

    suffix = "" if mode == "production" else f"_{'SIMULADO' if mode == 'simulated' else 'PRUEBA'}"
    return f"F07_{annex}_{period.key}{suffix}.csv"


# --- Documento del proveedor en una compra ------------------------------------------------------

PURCHASE_CLASSES = {1: ("03", "05", "06"), 3: ("12", "13"), DTE_CLASS: ("03", "05", "06")}
RENTA_OPERATIONS = (1, 2, 3, 4, 8, 9)
RENTA_CLASSIFICATIONS = (1, 2, 8, 9)
RENTA_SECTORS = (1, 2, 3, 4, 8, 9)
RENTA_COST_TYPES = (1, 2, 3, 4, 5, 6, 7, 8, 9)
MAX_NUMBER = 100
MAX_NAME = 250
SUPPLIER_ID_LENGTHS = {"nit": (14, 14), "dui": (9, 9), "nrc": (1, 14)}
_CONTROL = re.compile(r"^DTE-(03|05|06)-[A-Z0-9]{8}-\d{15}$")
_UUID = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$")


def _error(code: str, message: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


@dataclass(frozen=True)
class RentaPurchase:
    operation: int
    classification: int
    sector: int
    cost_type: int

    def validate(self) -> RentaPurchase:
        if (
            self.operation not in RENTA_OPERATIONS
            or self.classification not in RENTA_CLASSIFICATIONS
            or self.sector not in RENTA_SECTORS
            or self.cost_type not in RENTA_COST_TYPES
        ):
            raise _error(
                "fiscal_purchase_renta_invalid",
                "La clasificación de renta de la compra no está en los catálogos del F-07.",
            )
        return self


@dataclass(frozen=True)
class PurchaseFiscalData:
    """Documento que entregó el proveedor, tal como se registra para el libro de compras."""

    issued_on: date
    document_class: int
    document_type: str
    number: str
    control_number: str | None
    seal: str | None
    supplier_name: str
    supplier_id_type: str
    supplier_id: str
    renta: RentaPurchase


def validate_purchase_fiscal(data: PurchaseFiscalData, today: date) -> PurchaseFiscalData:
    """Normaliza y valida el documento del proveedor (manual F-07 V14, anexo de compras)."""

    types = PURCHASE_CLASSES.get(data.document_class)
    if types is None or data.document_type not in types:
        raise _error(
            "fiscal_purchase_document_invalid",
            "La clase y el tipo de documento no corresponden: el crédito fiscal y sus notas son de "
            "imprenta o DTE; la declaración de mercancías y el mandamiento de ingreso, «Otros».",
        )
    if data.issued_on > today:
        raise _error("fiscal_purchase_date_invalid", "La fecha del documento no puede ser futura.")
    number = data.number.strip()
    control = (data.control_number or "").strip().upper() or None
    seal = (data.seal or "").strip() or None
    if data.document_class == DTE_CLASS:
        number = number.upper()
        if not _UUID.match(number):
            raise _error(
                "fiscal_purchase_generation_code_invalid",
                "En un DTE el número es el código de generación (36 caracteres con guiones).",
            )
        if not control or not _CONTROL.match(control) or control[4:6] != data.document_type:
            raise _error(
                "fiscal_purchase_control_number_invalid",
                "El número de control del DTE no es válido o no es del tipo elegido.",
            )
        if not seal:
            raise _error("fiscal_purchase_seal_required", "Indica el sello de recepción del DTE.")
    else:
        control, seal = None, None
    if not 1 <= len(number) <= MAX_NUMBER:
        raise _error("fiscal_purchase_number_required", "Indica el número del documento.")
    name = re.sub(r"\s+", " ", data.supplier_name).strip()
    if not 1 <= len(name) <= MAX_NAME:
        raise _error("fiscal_purchase_supplier_required", "Indica el nombre del proveedor.")
    kind = data.supplier_id_type
    supplier_id = digits(data.supplier_id)
    bounds = SUPPLIER_ID_LENGTHS.get(kind)
    if bounds is None or not bounds[0] <= len(supplier_id) <= bounds[1]:
        raise _error(
            "fiscal_purchase_supplier_id_invalid",
            "El NIT lleva 14 dígitos, el DUI 9 y el NRC hasta 14, sin guiones.",
        )
    return PurchaseFiscalData(
        issued_on=data.issued_on,
        document_class=data.document_class,
        document_type=data.document_type,
        number=number,
        control_number=control,
        seal=seal,
        supplier_name=name,
        supplier_id_type=kind,
        supplier_id=supplier_id,
        renta=data.renta.validate(),
    )


def supplier_party(name: str, id_type: str, value: str) -> Party:
    return Party(
        name,
        nit=value if id_type == "nit" else None,
        nrc=value if id_type == "nrc" else None,
        dui=value if id_type == "dui" else None,
    )
