"""Motor único de cálculo fiscal de los documentos de venta.

Lo comparten la cotización, el pedido, el punto de venta y el DTE: ninguno calcula
impuestos por su cuenta.

Fuentes:
- Ley de IVA: tasa del 13 %.
- Código Tributario: retención del 1 % (art. 162) y percepción del 1 % (art. 163),
  ambas desde $100 sin IVA.
- Esquemas oficiales `fe-f-v2` (factura) y `fe-ccf-v4` (crédito fiscal): los montos por
  línea admiten 8 decimales y los del resumen, 2.
- Manual Funcional v2.0, capítulos XVIII (descuentos) y XXI (redondeo y holgura):
  redondeo con la mitad hacia arriba.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.core.exceptions import BusinessRuleError
from app.domain.entities.fiscal import TaxpayerCategory
from app.domain.entities.product_fiscal import DteItemType, TaxTreatment

VAT_RATE = Decimal("0.13")
VAT_FACTOR = Decimal("1.13")
WITHHOLDING_RATE = Decimal("0.01")
PERCEPTION_RATE = Decimal("0.01")
WITHHOLDING_THRESHOLD = Decimal("100")
LINE_PRECISION = Decimal("0.00000001")
CENT = Decimal("0.01")
ZERO = Decimal("0")

_GOODS = frozenset({DteItemType.GOODS, DteItemType.BOTH})


class SalesDocumentKind(StrEnum):
    """CAT-002. Los documentos que calcula el motor."""

    INVOICE = "01"
    TAX_CREDIT = "03"


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


def line_round(value: Decimal) -> Decimal:
    return value.quantize(LINE_PRECISION, rounding=ROUND_HALF_UP)


def cent_round(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class TaxLineInput:
    """Una línea tal como la pide el usuario.

    ``unit_price`` viene con IVA o sin él según ``price_includes_vat``; el motor lo lleva
    a la forma del documento. ``discount`` es el descuento por ítem, ya consolidado
    para toda la cantidad y expresado como el precio.
    """

    quantity: Decimal
    unit_price: Decimal
    price_includes_vat: bool
    tax_treatment: TaxTreatment
    item_type: DteItemType
    discount: Decimal = ZERO
    additional_taxes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GlobalDiscounts:
    """Descuentos globales del resumen, por naturaleza de la venta."""

    taxed: Decimal = ZERO
    exempt: Decimal = ZERO
    not_subject: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class TaxParties:
    issuer_category: TaxpayerCategory
    customer_is_taxpayer: bool
    customer_category: TaxpayerCategory | None = None
    customer_is_withholding_agent: bool = False

    @property
    def customer_withholds(self) -> bool:
        """El cliente retiene si es gran contribuyente o agente designado."""

        return self.customer_is_taxpayer and (
            self.customer_category is TaxpayerCategory.LARGE or self.customer_is_withholding_agent
        )


@dataclass(frozen=True, slots=True)
class TaxLineResult:
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    not_subject: Decimal
    exempt: Decimal
    taxed: Decimal
    vat_item: Decimal | None
    """IVA contenido en la línea (solo en la factura; el crédito fiscal no lo lleva)."""


@dataclass(frozen=True, slots=True)
class TaxSummary:
    total_not_subject: Decimal
    total_exempt: Decimal
    total_taxed: Decimal
    subtotal_sales: Decimal
    discount_not_subject: Decimal
    discount_exempt: Decimal
    discount_taxed: Decimal
    total_discount: Decimal
    subtotal: Decimal
    vat: Decimal
    """En la factura, el IVA contenido; en el crédito fiscal, el tributo 20 que se suma."""
    vat_perceived: Decimal
    vat_withheld: Decimal
    total_operation: Decimal
    total_to_pay: Decimal
    total_in_words: str


@dataclass(frozen=True, slots=True)
class TaxCalculation:
    document: SalesDocumentKind
    lines: tuple[TaxLineResult, ...]
    summary: TaxSummary


def _document_price(line: TaxLineInput, document: SalesDocumentKind) -> Decimal:
    if line.tax_treatment is not TaxTreatment.TAXED:
        if line.price_includes_vat:
            raise _rule(
                "Una línea exenta o no sujeta no lleva IVA en el precio.",
                "sales_tax_untaxed_price_with_vat",
            )
        return line.unit_price
    wants_vat = document is SalesDocumentKind.INVOICE
    if line.price_includes_vat == wants_vat:
        return line.unit_price
    if wants_vat:
        return line_round(line.unit_price * VAT_FACTOR)
    return line_round(line.unit_price / VAT_FACTOR)


def document_unit_price(line: TaxLineInput, document: SalesDocumentKind) -> Decimal:
    """Precio unitario en la forma del documento: con IVA en factura, sin IVA en crédito fiscal."""

    return _document_price(line, document)


def _check_line(index: int, line: TaxLineInput) -> None:
    position = index + 1
    if line.additional_taxes:
        raise _rule(
            f"La línea {position} tiene tributos adicionales ({', '.join(line.additional_taxes)}), "
            "que el cálculo de ventas todavía no admite.",
            "sales_tax_additional_unsupported",
        )
    if line.quantity <= ZERO:
        raise _rule(
            f"La cantidad de la línea {position} debe ser mayor que cero.",
            "sales_tax_quantity_invalid",
        )
    if line.unit_price < ZERO:
        raise _rule(
            f"El precio de la línea {position} no puede ser negativo.", "sales_tax_price_invalid"
        )
    if line.discount < ZERO:
        raise _rule(
            f"El descuento de la línea {position} no puede ser negativo.",
            "sales_tax_discount_invalid",
        )


def _calculate_line(index: int, line: TaxLineInput, document: SalesDocumentKind) -> TaxLineResult:
    _check_line(index, line)
    price = _document_price(line, document)
    discount = line_round(line.discount)
    gross = line_round(line.quantity * price)
    if discount > gross:
        raise _rule(
            f"El descuento de la línea {index + 1} supera su monto.",
            "sales_tax_discount_exceeds_line",
        )
    amount = gross - discount
    taxed = amount if line.tax_treatment is TaxTreatment.TAXED else ZERO
    vat_item: Decimal | None = None
    if document is SalesDocumentKind.INVOICE:
        vat_item = line_round(taxed - taxed / VAT_FACTOR)
    return TaxLineResult(
        quantity=line.quantity,
        unit_price=price,
        discount=discount,
        not_subject=amount if line.tax_treatment is TaxTreatment.NOT_SUBJECT else ZERO,
        exempt=amount if line.tax_treatment is TaxTreatment.EXEMPT else ZERO,
        taxed=taxed,
        vat_item=vat_item,
    )


def _check_global(discount: Decimal, total: Decimal, label: str) -> Decimal:
    value = cent_round(discount)
    if value < ZERO:
        raise _rule(
            f"El descuento global a ventas {label} no puede ser negativo.",
            "sales_tax_discount_invalid",
        )
    if value > total:
        raise _rule(
            f"El descuento global a ventas {label} supera su total.",
            "sales_tax_global_discount_exceeds",
        )
    return value


def calculate(
    document: SalesDocumentKind,
    lines: list[TaxLineInput] | tuple[TaxLineInput, ...],
    parties: TaxParties,
    discounts: GlobalDiscounts | None = None,
) -> TaxCalculation:
    """Calcula las líneas y el resumen de un documento de venta."""

    if not lines:
        raise _rule("El documento necesita al menos una línea.", "sales_tax_lines_required")
    if document is SalesDocumentKind.TAX_CREDIT and not parties.customer_is_taxpayer:
        raise _rule(
            "El comprobante de crédito fiscal solo se emite a contribuyentes de IVA.",
            "sales_tax_credit_requires_taxpayer",
        )
    globals_ = discounts or GlobalDiscounts()
    results = tuple(_calculate_line(i, line, document) for i, line in enumerate(lines))

    total_not_subject = cent_round(sum((r.not_subject for r in results), ZERO))
    total_exempt = cent_round(sum((r.exempt for r in results), ZERO))
    total_taxed = cent_round(sum((r.taxed for r in results), ZERO))
    discount_not_subject = _check_global(globals_.not_subject, total_not_subject, "no sujetas")
    discount_exempt = _check_global(globals_.exempt, total_exempt, "exentas")
    discount_taxed = _check_global(globals_.taxed, total_taxed, "gravadas")

    subtotal_sales = total_not_subject + total_exempt + total_taxed
    global_discount = discount_not_subject + discount_exempt + discount_taxed
    subtotal = subtotal_sales - global_discount
    net_taxed = total_taxed - discount_taxed

    if document is SalesDocumentKind.INVOICE:
        base_without_vat = line_round(net_taxed / VAT_FACTOR)
        vat = cent_round(net_taxed - base_without_vat)
        vat_added = ZERO
    else:
        base_without_vat = net_taxed
        vat = cent_round(net_taxed * VAT_RATE)
        vat_added = vat

    withheld = ZERO
    if (
        parties.customer_withholds
        and parties.issuer_category is not TaxpayerCategory.LARGE
        and base_without_vat >= WITHHOLDING_THRESHOLD
    ):
        withheld = cent_round(base_without_vat * WITHHOLDING_RATE)

    perceived = ZERO
    if (
        document is SalesDocumentKind.TAX_CREDIT
        and parties.issuer_category is TaxpayerCategory.LARGE
        and parties.customer_category is not TaxpayerCategory.LARGE
    ):
        goods_base = _goods_base(lines, results, total_taxed, discount_taxed)
        if goods_base >= WITHHOLDING_THRESHOLD:
            perceived = cent_round(goods_base * PERCEPTION_RATE)

    total_operation = subtotal + vat_added + perceived - withheld
    line_discounts = cent_round(sum((r.discount for r in results), ZERO))
    summary = TaxSummary(
        total_not_subject=total_not_subject,
        total_exempt=total_exempt,
        total_taxed=total_taxed,
        subtotal_sales=subtotal_sales,
        discount_not_subject=discount_not_subject,
        discount_exempt=discount_exempt,
        discount_taxed=discount_taxed,
        total_discount=line_discounts + global_discount,
        subtotal=subtotal,
        vat=vat,
        vat_perceived=perceived,
        vat_withheld=withheld,
        total_operation=total_operation,
        total_to_pay=total_operation,
        total_in_words=amount_in_words(total_operation),
    )
    return TaxCalculation(document=document, lines=results, summary=summary)


def _goods_base(
    lines: list[TaxLineInput] | tuple[TaxLineInput, ...],
    results: tuple[TaxLineResult, ...],
    total_taxed: Decimal,
    discount_taxed: Decimal,
) -> Decimal:
    """Gravada neta de las líneas de bienes: el descuento global se reparte en proporción."""

    goods = sum(
        (r.taxed for line, r in zip(lines, results, strict=True) if line.item_type in _GOODS),
        ZERO,
    )
    if total_taxed == ZERO:
        return ZERO
    return line_round(goods - discount_taxed * goods / total_taxed)


# --- total en letras ---

_UNITS = (
    "CERO", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE", "DIEZ",
    "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISÉIS", "DIECISIETE", "DIECIOCHO",
    "DIECINUEVE", "VEINTE", "VEINTIUNO", "VEINTIDÓS", "VEINTITRÉS", "VEINTICUATRO",
    "VEINTICINCO", "VEINTISÉIS", "VEINTISIETE", "VEINTIOCHO", "VEINTINUEVE",
)  # fmt: skip
_TENS = ("", "", "", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA")
_HUNDREDS = (
    "", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS",
    "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS",
)  # fmt: skip


def _below_thousand(number: int) -> str:
    if number == 100:  # noqa: PLR2004
        return "CIEN"
    hundreds, rest = divmod(number, 100)
    words = [_HUNDREDS[hundreds]] if hundreds else []
    if rest < len(_UNITS):
        if rest or not hundreds:
            words.append(_UNITS[rest])
    else:
        tens, units = divmod(rest, 10)
        words.append(_TENS[tens] + (f" Y {_UNITS[units]}" if units else ""))
    return " ".join(words)


def _apocope(words: str) -> str:
    """«UNO» delante de «MIL» o «MILLONES» se acorta: VEINTIÚN MIL, UN MILLÓN."""

    if words.endswith("VEINTIUNO"):
        return words[: -len("VEINTIUNO")] + "VEINTIÚN"
    if words.endswith("UNO"):
        return words[:-1]
    return words


def _integer_in_words(number: int) -> str:
    if number == 0:
        return "CERO"
    millions, rest = divmod(number, 1_000_000)
    thousands, units = divmod(rest, 1000)
    words: list[str] = []
    if millions:
        words.append(
            "UN MILLÓN" if millions == 1 else f"{_apocope(_integer_in_words(millions))} MILLONES"
        )
    if thousands:
        words.append("MIL" if thousands == 1 else f"{_apocope(_below_thousand(thousands))} MIL")
    if units:
        words.append(_below_thousand(units))
    return " ".join(words)


def amount_in_words(amount: Decimal) -> str:
    """Total en letras del DTE: «MIL SETENTA Y TRES 50/100 DÓLARES»."""

    value = cent_round(amount)
    if value < ZERO:
        raise _rule("El total no puede ser negativo.", "sales_tax_total_negative")
    integer = int(value)
    cents = int((value - integer) * 100)
    return f"{_integer_in_words(integer)} {cents:02d}/100 DÓLARES"
