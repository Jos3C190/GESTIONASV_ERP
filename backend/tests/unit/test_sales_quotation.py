"""Cotización V2d: estados, cálculo con lista, descuentos e impuestos, y regla del autorizador."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.fiscal import TaxpayerCategory
from app.domain.entities.product_fiscal import DteItemType, TaxTreatment
from app.domain.entities.sales_margin import AuthorizationReason, DiscountPolicy
from app.domain.entities.sales_quotation import (
    QuotationStatus,
    QuoteLineInput,
    calculate_quote,
    is_expired,
    issue_target,
    missing_authority,
    require_acceptable,
    require_answerable,
    require_authority,
    require_cancellable,
    require_convertible,
    require_editable,
    require_not_below_cost,
    require_price_override_allowed,
    require_rejection_reason,
    require_valid_until,
    require_validity_days,
)
from app.domain.entities.sales_tax import SalesDocumentKind, TaxParties

D = Decimal
S = QuotationStatus
INVOICE = SalesDocumentKind.INVOICE
CREDIT = SalesDocumentKind.TAX_CREDIT
CONSUMER = TaxParties(issuer_category=TaxpayerCategory.OTHER, customer_is_taxpayer=False)
TAXPAYER = TaxParties(
    issuer_category=TaxpayerCategory.OTHER,
    customer_is_taxpayer=True,
    customer_category=TaxpayerCategory.OTHER,
)
SELLER = DiscountPolicy(D("10"), D("3"))
UNLIMITED_POLICY = DiscountPolicy(D("100"), D("100"))
TODAY = date(2026, 11, 16)


def line(
    quantity: str = "1",
    list_price: str | None = "10",
    *,
    manual: str | None = None,
    discount: str = "0",
    cost: str | None = None,
    treatment: TaxTreatment = TaxTreatment.TAXED,
) -> QuoteLineInput:
    return QuoteLineInput(
        quantity=D(quantity),
        list_price=None if list_price is None else D(list_price),
        manual_price=None if manual is None else D(manual),
        discount_percent=D(discount),
        tax_treatment=treatment,
        item_type=DteItemType.GOODS,
        cost=None if cost is None else D(cost),
    )


def test_invoice_with_vat_list_and_line_discount() -> None:
    result = calculate_quote(
        INVOICE,
        True,
        [line("2", "11.30", discount="10", cost="8")],
        CONSUMER,
        D("0"),
        SELLER,
    )
    item = result.lines[0]
    assert item.net_price == D("10.17")
    assert item.effective_discount_percent == D("10.00")
    assert item.document_unit_price == D("11.30")
    assert item.discount_amount == D("2.26")
    assert item.taxed == D("20.34")
    assert item.vat_item == D("2.34")
    assert item.margin_percent == D("11.11")
    assert item.reasons == ()
    assert result.tax.summary.total_to_pay == D("20.34")
    assert not result.requires_authorization


def test_tax_credit_converts_vat_list_price() -> None:
    result = calculate_quote(
        CREDIT, True, [line("2", "11.30", discount="10")], TAXPAYER, D("0"), SELLER
    )
    item = result.lines[0]
    assert item.document_unit_price == D("10.00000000")
    assert item.discount_amount == D("2.00")
    assert item.taxed == D("18.00")
    assert item.vat_item is None
    assert result.tax.summary.vat == D("2.34")
    assert result.tax.summary.total_to_pay == D("20.34")


def test_manual_price_counts_as_discount_and_below_cost() -> None:
    result = calculate_quote(
        INVOICE, True, [line("1", "11.30", manual="9", cost="8")], CONSUMER, D("0"), SELLER
    )
    item = result.lines[0]
    assert item.price_overridden
    assert item.unit_price == D("9")
    assert item.effective_discount_percent == D("20.35")
    assert item.reasons == (AuthorizationReason.DISCOUNT_ABOVE_LIMIT,)
    assert result.requires_authorization
    # $9 con IVA son $7.96 sin IVA, bajo el costo de $8: no se puede vender así.
    assert item.below_cost
    assert result.below_cost_lines == (1,)
    with pytest.raises(BusinessRuleError) as error:
        require_not_below_cost(result)
    assert error.value.code == "sales_price_below_cost"
    assert "$7.96" in error.value.message


def test_global_discount_also_counts_against_the_cost() -> None:
    fine = calculate_quote(INVOICE, False, [line("1", "10", cost="9.60")], CONSUMER, D("0"), SELLER)
    require_not_below_cost(fine)
    # 5 % global deja la línea en $9.50 sin IVA, bajo el costo de $9.60.
    global_ = calculate_quote(
        INVOICE, False, [line("1", "10", cost="9.60")], CONSUMER, D("5"), UNLIMITED_POLICY
    )
    assert global_.lines[0].final_net_without_vat == D("9.50")
    assert global_.below_cost_lines == (1,)
    with pytest.raises(BusinessRuleError):
        require_not_below_cost(global_)


def test_manual_price_above_list_is_not_a_discount() -> None:
    result = calculate_quote(
        INVOICE, False, [line("1", "10", manual="12")], CONSUMER, D("0"), SELLER
    )
    assert result.lines[0].effective_discount_percent == D("0")
    assert not result.requires_authorization


def test_global_discount_spreads_and_checks_limit() -> None:
    result = calculate_quote(INVOICE, False, [line("1", "10")], CONSUMER, D("5"), SELLER)
    summary = result.tax.summary
    assert result.lines[0].taxed == D("11.30")
    assert summary.discount_taxed == D("0.57")
    assert summary.subtotal == D("10.73")
    assert summary.vat == D("1.23")
    assert result.reasons == (AuthorizationReason.GLOBAL_DISCOUNT_ABOVE_LIMIT,)


def test_exempt_line_in_vat_list_keeps_its_price() -> None:
    result = calculate_quote(
        INVOICE,
        True,
        [line("1", "5", treatment=TaxTreatment.EXEMPT, cost="4")],
        CONSUMER,
        D("0"),
        SELLER,
    )
    item = result.lines[0]
    assert item.exempt == D("5.00")
    assert item.taxed == D("0")
    assert item.margin_percent == D("20.00")


def test_line_without_list_price_needs_manual_price() -> None:
    with pytest.raises(BusinessRuleError) as error:
        calculate_quote(INVOICE, True, [line(list_price=None)], CONSUMER, D("0"), SELLER)
    assert error.value.code == "sales_quote_price_missing"
    manual = calculate_quote(
        INVOICE, False, [line(list_price=None, manual="4", discount="5")], CONSUMER, D("0"), SELLER
    )
    assert manual.lines[0].effective_discount_percent == D("5")


@pytest.mark.parametrize("percent", ["-1", "101"])
def test_discount_out_of_range(percent: str) -> None:
    with pytest.raises(BusinessRuleError):
        calculate_quote(INVOICE, True, [line(discount=percent)], CONSUMER, D("0"), SELLER)
    with pytest.raises(BusinessRuleError):
        calculate_quote(INVOICE, True, [line()], CONSUMER, D(percent), SELLER)


def test_authorizer_needs_own_sufficient_limit() -> None:
    quote = calculate_quote(
        INVOICE, True, [line("1", "11.30", manual="9", cost="7")], CONSUMER, D("5"), SELLER
    )
    assert missing_authority(quote, DiscountPolicy(D("25"), D("10"))) == ()
    assert missing_authority(quote, DiscountPolicy(D("20"), D("4"))) == (
        AuthorizationReason.DISCOUNT_ABOVE_LIMIT,
        AuthorizationReason.GLOBAL_DISCOUNT_ABOVE_LIMIT,
    )
    require_authority(quote, DiscountPolicy(D("25"), D("10")))
    with pytest.raises(BusinessRuleError) as error:
        require_authority(quote, SELLER)
    assert error.value.code == "sales_quote_authority_insufficient"


def test_price_override_requires_permission() -> None:
    require_price_override_allowed(line(), allowed=False)
    require_price_override_allowed(line(manual="9"), allowed=True)
    with pytest.raises(BusinessRuleError) as error:
        require_price_override_allowed(line(manual="9"), allowed=False)
    assert error.value.code == "sales_quote_price_override_forbidden"


def test_state_transitions() -> None:
    require_editable(S.DRAFT)
    for status in (S.PENDING_AUTHORIZATION, S.ISSUED, S.ACCEPTED):
        with pytest.raises(BusinessRuleError):
            require_editable(status)
    assert issue_target(S.DRAFT, requires_authorization=True) is S.PENDING_AUTHORIZATION
    assert issue_target(S.DRAFT, requires_authorization=False) is S.ISSUED
    with pytest.raises(BusinessRuleError):
        issue_target(S.ISSUED, requires_authorization=False)
    for status in (S.DRAFT, S.PENDING_AUTHORIZATION, S.ISSUED, S.ACCEPTED):
        require_cancellable(status)
    for status in (S.REJECTED, S.CANCELLED):
        with pytest.raises(BusinessRuleError):
            require_cancellable(status)
    require_convertible(S.ACCEPTED)
    with pytest.raises(BusinessRuleError):
        require_convertible(S.ISSUED)


def test_expiry_blocks_acceptance_but_not_rejection() -> None:
    yesterday = date(2026, 11, 15)
    assert is_expired(S.ISSUED, yesterday, TODAY)
    assert not is_expired(S.ACCEPTED, yesterday, TODAY)
    assert not is_expired(S.ISSUED, TODAY, TODAY)
    require_acceptable(S.ISSUED, TODAY, TODAY)
    with pytest.raises(BusinessRuleError) as error:
        require_acceptable(S.ISSUED, yesterday, TODAY)
    assert error.value.code == "sales_quote_expired"
    require_answerable(S.ISSUED)
    with pytest.raises(BusinessRuleError):
        require_answerable(S.DRAFT)
    assert require_rejection_reason("  Precio alto ") == "Precio alto"
    with pytest.raises(BusinessRuleError):
        require_rejection_reason(" ")


def test_validity_limits() -> None:
    require_validity_days(15)
    for days in (0, 366):
        with pytest.raises(BusinessRuleError):
            require_validity_days(days)
    require_valid_until(TODAY, TODAY)
    with pytest.raises(BusinessRuleError):
        require_valid_until(TODAY, date(2026, 11, 15))
    with pytest.raises(BusinessRuleError):
        require_valid_until(TODAY, date(2027, 11, 17))
