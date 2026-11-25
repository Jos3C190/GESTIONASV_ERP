"""Cotización de venta: estados, cálculo y autorización (bloque V2d).

El cálculo combina tres piezas que ya existen y no se duplican aquí:
- el precio de lista o, con permiso, un precio manual;
- el descuento y su evaluación contra el tope del usuario (``sales_margin``);
- el motor fiscal (``sales_tax.calculate``).

Un precio manual por debajo de la lista cuenta como descuento ante el tope: lo que se compara
es el descuento total sobre el precio de lista.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from enum import StrEnum

from app.core.exceptions import BusinessRuleError
from app.domain.entities.product_fiscal import DteItemType, TaxTreatment
from app.domain.entities.sales_margin import (
    HUNDRED,
    AuthorizationReason,
    DiscountPolicy,
    DiscountSource,
    evaluate_global,
    is_below_cost,
    margin_percent,
    percent_round,
    without_vat,
)
from app.domain.entities.sales_tax import (
    ZERO,
    GlobalDiscounts,
    SalesDocumentKind,
    TaxCalculation,
    TaxLineInput,
    TaxLineResult,
    TaxParties,
    calculate,
    cent_round,
    document_unit_price,
    line_round,
)

ONE = Decimal("1")
MAX_VALIDITY_DAYS = 365
DEFAULT_VALIDITY_DAYS = 15
MIN_REASON_LENGTH = 3


def _rule(message: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(message, code=code)


class QuotationStatus(StrEnum):
    DRAFT = "draft"
    PENDING_AUTHORIZATION = "pending_authorization"
    ISSUED = "issued"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


STATUS_TEXT: dict[QuotationStatus, str] = {
    QuotationStatus.DRAFT: "Borrador",
    QuotationStatus.PENDING_AUTHORIZATION: "Por autorizar",
    QuotationStatus.ISSUED: "Emitida",
    QuotationStatus.ACCEPTED: "Aceptada",
    QuotationStatus.REJECTED: "Rechazada",
    QuotationStatus.CANCELLED: "Cancelada",
}


# --- Estados ---------------------------------------------------------------------------------


def _require(status: QuotationStatus, allowed: tuple[QuotationStatus, ...], action: str) -> None:
    if status not in allowed:
        raise _rule(
            f"No se puede {action} una cotización en estado {STATUS_TEXT[status]}.",
            "sales_quote_status_invalid",
        )


def require_editable(status: QuotationStatus) -> None:
    _require(status, (QuotationStatus.DRAFT,), "editar")


def is_expired(status: QuotationStatus, valid_until: date, today: date) -> bool:
    """Una cotización emitida vence cuando su vigencia pasó; los demás estados no vencen."""

    return status is QuotationStatus.ISSUED and valid_until < today


def issue_target(status: QuotationStatus, requires_authorization: bool) -> QuotationStatus:
    """Emitir un borrador: va a autorización si algo pasa el tope; si no, queda emitida."""

    _require(status, (QuotationStatus.DRAFT,), "emitir")
    if requires_authorization:
        return QuotationStatus.PENDING_AUTHORIZATION
    return QuotationStatus.ISSUED


def require_pending_authorization(status: QuotationStatus) -> None:
    _require(status, (QuotationStatus.PENDING_AUTHORIZATION,), "autorizar o devolver")


def require_answerable(status: QuotationStatus) -> None:
    """El cliente acepta o rechaza una cotización emitida (rechazar se permite aunque venza)."""

    _require(status, (QuotationStatus.ISSUED,), "registrar la respuesta del cliente en")


def require_acceptable(status: QuotationStatus, valid_until: date, today: date) -> None:
    require_answerable(status)
    if valid_until < today:
        raise _rule(
            "La cotización venció. Cópiala en una nueva para actualizar precios y vigencia.",
            "sales_quote_expired",
        )


def require_rejection_reason(reason: str | None) -> str:
    text = (reason or "").strip()
    if len(text) < MIN_REASON_LENGTH:
        raise _rule(
            "Indica por qué el cliente rechazó la cotización.", "sales_quote_reason_required"
        )
    return text


def require_cancellable(status: QuotationStatus) -> None:
    _require(
        status,
        (
            QuotationStatus.DRAFT,
            QuotationStatus.PENDING_AUTHORIZATION,
            QuotationStatus.ISSUED,
            QuotationStatus.ACCEPTED,
        ),
        "cancelar",
    )


def require_convertible(status: QuotationStatus) -> None:
    _require(status, (QuotationStatus.ACCEPTED,), "convertir en venta")


def require_validity_days(days: int) -> None:
    if not 1 <= days <= MAX_VALIDITY_DAYS:
        raise _rule(
            f"La vigencia va de 1 a {MAX_VALIDITY_DAYS} días.", "sales_quote_validity_invalid"
        )


def require_valid_until(quotation_date: date, valid_until: date) -> None:
    if valid_until < quotation_date:
        raise _rule(
            "La vigencia no puede terminar antes de la fecha de la cotización.",
            "sales_quote_validity_invalid",
        )
    if (valid_until - quotation_date).days > MAX_VALIDITY_DAYS:
        raise _rule(
            f"La vigencia no puede pasar de {MAX_VALIDITY_DAYS} días.",
            "sales_quote_validity_invalid",
        )


# --- Cálculo -----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QuoteLineInput:
    """Una línea lista para calcular.

    Los precios van en la forma de la lista: con IVA si ``prices_include_vat`` de la
    cotización es verdadero. ``cost`` es el costo unitario sin IVA en la misma unidad.
    """

    quantity: Decimal
    list_price: Decimal | None
    manual_price: Decimal | None
    discount_percent: Decimal
    tax_treatment: TaxTreatment
    item_type: DteItemType
    cost: Decimal | None = None
    suggested_discount_percent: Decimal = ZERO
    suggested_discount_source: DiscountSource = DiscountSource.NONE

    @property
    def promotion(self) -> bool:
        """El descuento lo fija la promoción de la sucursal: no pasa por el tope del rol."""

        return self.suggested_discount_source is DiscountSource.PROMOTION


@dataclass(frozen=True, slots=True)
class QuoteLineResult:
    unit_price: Decimal
    """Precio aplicado antes del descuento (lista o manual), en la forma de la lista."""
    price_overridden: bool
    discount_percent: Decimal
    effective_discount_percent: Decimal
    """Descuento total contra el precio de lista; es el que se compara con el tope."""
    net_price: Decimal
    document_unit_price: Decimal
    discount_amount: Decimal
    not_subject: Decimal
    exempt: Decimal
    taxed: Decimal
    vat_item: Decimal | None
    line_total: Decimal
    cost: Decimal | None
    margin_percent: Decimal | None
    reasons: tuple[AuthorizationReason, ...]
    below_cost: bool = False
    """El precio neto sin IVA, con el descuento de la línea y el global, queda bajo el costo."""
    final_net_without_vat: Decimal | None = None


@dataclass(frozen=True, slots=True)
class QuoteCalculation:
    lines: tuple[QuoteLineResult, ...]
    tax: TaxCalculation
    global_discount_percent: Decimal
    reasons: tuple[AuthorizationReason, ...]

    @property
    def requires_authorization(self) -> bool:
        return bool(self.reasons)

    @property
    def below_cost_lines(self) -> tuple[int, ...]:
        """Las líneas (desde 1) que quedan por debajo del costo."""

        return tuple(i for i, line in enumerate(self.lines, start=1) if line.below_cost)


def require_not_below_cost(calculation: QuoteCalculation) -> None:
    """Nunca se vende por debajo del costo del kardex, ni con descuentos (pedido del ingeniero)."""

    if not calculation.below_cost_lines:
        return
    position = calculation.below_cost_lines[0]
    line = calculation.lines[position - 1]
    raise _rule(
        f"La línea {position} queda por debajo del costo: ${line.final_net_without_vat:,.2f} sin IVA "
        f"frente a un costo de ${line.cost:,.2f}. Sube el precio o baja el descuento; no se puede "
        "vender bajo costo.",
        "sales_price_below_cost",
    )


def _check_discount(value: Decimal) -> None:
    if not ZERO <= value <= HUNDRED:
        raise _rule("El descuento va de 0 % a 100 %.", "sales_discount_percent_invalid")


def _base_price(index: int, line: QuoteLineInput) -> Decimal:
    if line.manual_price is not None:
        if line.manual_price < ZERO:
            raise _rule(
                f"El precio de la línea {index + 1} no puede ser negativo.",
                "sales_tax_price_invalid",
            )
        return line.manual_price
    if line.list_price is None:
        raise _rule(
            f"La línea {index + 1} no tiene precio en la lista de precios. "
            "Agrégalo a la lista o, si tienes permiso, escribe el precio.",
            "sales_quote_price_missing",
        )
    return line.list_price


def _line_reasons(
    effective_discount: Decimal, policy: DiscountPolicy
) -> tuple[AuthorizationReason, ...]:
    if effective_discount > policy.max_line_percent:
        return (AuthorizationReason.DISCOUNT_ABOVE_LIMIT,)
    return ()


@dataclass(frozen=True, slots=True)
class _PricedLine:
    price: Decimal
    includes_vat: bool
    effective_discount: Decimal
    net: Decimal
    tax_input: TaxLineInput
    document_price: Decimal


def _price_line(
    index: int, line: QuoteLineInput, prices_include_vat: bool, document: SalesDocumentKind
) -> _PricedLine:
    _check_discount(line.discount_percent)
    price = _base_price(index, line)
    # Lo exento y lo no sujeto no lleva IVA: su precio de lista es el precio final.
    includes_vat = prices_include_vat and line.tax_treatment is TaxTreatment.TAXED
    net = line_round(price * (1 - line.discount_percent / HUNDRED))
    effective = line.discount_percent
    if line.list_price is not None and line.list_price > ZERO:
        effective = max(ZERO, percent_round((line.list_price - net) / line.list_price * HUNDRED))
    undiscounted = TaxLineInput(
        quantity=line.quantity,
        unit_price=price,
        price_includes_vat=includes_vat,
        tax_treatment=line.tax_treatment,
        item_type=line.item_type,
    )
    document_price = document_unit_price(undiscounted, document)
    discount = line_round(
        line_round(line.quantity * document_price) * line.discount_percent / HUNDRED
    )
    return _PricedLine(
        price=price,
        includes_vat=includes_vat,
        effective_discount=effective,
        net=net,
        tax_input=replace(undiscounted, discount=discount),
        document_price=document_price,
    )


def _global_discounts(lines: tuple[TaxLineResult, ...], percent: Decimal) -> GlobalDiscounts:
    share = percent / HUNDRED

    def portion(amounts: list[Decimal]) -> Decimal:
        return cent_round(cent_round(sum(amounts, ZERO)) * share)

    return GlobalDiscounts(
        taxed=portion([r.taxed for r in lines]),
        exempt=portion([r.exempt for r in lines]),
        not_subject=portion([r.not_subject for r in lines]),
    )


def calculate_quote(
    document: SalesDocumentKind,
    prices_include_vat: bool,
    lines: list[QuoteLineInput] | tuple[QuoteLineInput, ...],
    parties: TaxParties,
    global_discount_percent: Decimal,
    policy: DiscountPolicy,
) -> QuoteCalculation:
    """Calcula precios, descuentos, impuestos y motivos de autorización de una cotización."""

    _check_discount(global_discount_percent)
    priced = [
        _price_line(index, line, prices_include_vat, document) for index, line in enumerate(lines)
    ]
    tax_inputs = [item.tax_input for item in priced]
    preliminary = calculate(document, tax_inputs, parties)
    tax = calculate(
        document,
        tax_inputs,
        parties,
        _global_discounts(preliminary.lines, global_discount_percent),
    )

    results: list[QuoteLineResult] = []
    reasons: list[AuthorizationReason] = []
    share = ONE - global_discount_percent / HUNDRED
    for line, item, result in zip(lines, priced, tax.lines, strict=True):
        line_reasons = () if line.promotion else _line_reasons(item.effective_discount, policy)
        final_net = line_round(without_vat(item.net, item.includes_vat) * share)
        reasons.extend(reason for reason in line_reasons if reason not in reasons)
        results.append(
            QuoteLineResult(
                unit_price=item.price,
                price_overridden=line.manual_price is not None,
                discount_percent=line.discount_percent,
                effective_discount_percent=item.effective_discount,
                net_price=item.net,
                document_unit_price=item.document_price,
                discount_amount=result.discount,
                not_subject=result.not_subject,
                exempt=result.exempt,
                taxed=result.taxed,
                vat_item=result.vat_item,
                line_total=result.not_subject + result.exempt + result.taxed,
                cost=line.cost,
                margin_percent=margin_percent(item.net, item.includes_vat, line.cost),
                reasons=line_reasons,
                below_cost=is_below_cost(final_net, line.cost),
                final_net_without_vat=final_net,
            )
        )
    reasons.extend(evaluate_global(global_discount_percent, policy))
    return QuoteCalculation(
        lines=tuple(results),
        tax=tax,
        global_discount_percent=global_discount_percent,
        reasons=tuple(reasons),
    )


# --- Autorización -------------------------------------------------------------------------------


def missing_authority(
    calculation: QuoteCalculation, authorizer: DiscountPolicy
) -> tuple[AuthorizationReason, ...]:
    """Motivos que el tope propio del autorizador no cubre (vacío: puede autorizar)."""

    pending: list[AuthorizationReason] = []
    for line in calculation.lines:
        if (
            line.effective_discount_percent > authorizer.max_line_percent
            and AuthorizationReason.DISCOUNT_ABOVE_LIMIT not in pending
        ):
            pending.append(AuthorizationReason.DISCOUNT_ABOVE_LIMIT)
    if calculation.global_discount_percent > authorizer.max_global_percent:
        pending.append(AuthorizationReason.GLOBAL_DISCOUNT_ABOVE_LIMIT)
    return tuple(pending)


AUTHORITY_TEXT: dict[AuthorizationReason, str] = {
    AuthorizationReason.DISCOUNT_ABOVE_LIMIT: "un descuento de línea mayor que tu tope",
    AuthorizationReason.BELOW_COST: "un precio por debajo del costo",
    AuthorizationReason.GLOBAL_DISCOUNT_ABOVE_LIMIT: "un descuento global mayor que tu tope",
}


def require_authority(calculation: QuoteCalculation, authorizer: DiscountPolicy) -> None:
    pending = missing_authority(calculation, authorizer)
    if pending:
        detail = ", ".join(AUTHORITY_TEXT[reason] for reason in pending)
        raise _rule(
            f"No puedes autorizar esta cotización: tiene {detail}. "
            "Debe autorizarla alguien con un tope suficiente.",
            "sales_quote_authority_insufficient",
        )


def require_price_override_allowed(line: QuoteLineInput, allowed: bool) -> None:
    if line.manual_price is not None and not allowed:
        raise _rule(
            "No tienes permiso para cambiar el precio de lista.",
            "sales_quote_price_override_forbidden",
        )
