"""Motor único de cálculo fiscal: casos con valores exactos."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.fiscal import TaxpayerCategory
from app.domain.entities.product_fiscal import DteItemType, TaxTreatment
from app.domain.entities.sales_tax import (
    GlobalDiscounts,
    SalesDocumentKind,
    TaxLineInput,
    TaxParties,
    amount_in_words,
    calculate,
    line_round,
)

D = Decimal
INVOICE = SalesDocumentKind.INVOICE
CREDIT = SalesDocumentKind.TAX_CREDIT
CONSUMER = TaxParties(issuer_category=TaxpayerCategory.OTHER, customer_is_taxpayer=False)
TAXPAYER = TaxParties(
    issuer_category=TaxpayerCategory.OTHER,
    customer_is_taxpayer=True,
    customer_category=TaxpayerCategory.OTHER,
)


def line(
    quantity: str,
    price: str,
    *,
    with_vat: bool = False,
    treatment: TaxTreatment = TaxTreatment.TAXED,
    item: DteItemType = DteItemType.GOODS,
    discount: str = "0",
    extra: tuple[str, ...] = (),
) -> TaxLineInput:
    return TaxLineInput(
        quantity=D(quantity),
        unit_price=D(price),
        price_includes_vat=with_vat,
        tax_treatment=treatment,
        item_type=item,
        discount=D(discount),
        additional_taxes=extra,
    )


def code(excinfo: pytest.ExceptionInfo[BusinessRuleError]) -> str:
    return excinfo.value.code


def test_same_product_in_both_documents() -> None:
    """Cuadro 1 del plan: $1.13 con IVA en la factura, $1.00 + $0.13 en el crédito fiscal."""

    invoice = calculate(INVOICE, [line("1", "1.00")], CONSUMER)
    assert invoice.lines[0].unit_price == D("1.13000000")
    assert invoice.lines[0].taxed == D("1.13000000")
    assert invoice.lines[0].vat_item == D("0.13000000")
    assert invoice.summary.total_taxed == D("1.13")
    assert invoice.summary.vat == D("0.13")
    assert invoice.summary.total_to_pay == D("1.13")

    credit = calculate(CREDIT, [line("1", "1.13", with_vat=True)], TAXPAYER)
    assert credit.lines[0].unit_price == D("1.00000000")
    assert credit.lines[0].vat_item is None
    assert credit.summary.total_taxed == D("1.00")
    assert credit.summary.vat == D("0.13")
    assert credit.summary.total_to_pay == D("1.13")
    assert credit.summary.total_in_words == "UNO 13/100 DÓLARES"


def test_official_credit_example_with_global_discount_and_withholding() -> None:
    """Manual Funcional v2.0, cap. XVIII: CCF con descuento global y retención."""

    lines = [
        line("10", "11.00", discount="10.00"),
        line("15", "5.00"),
        line("25", "21.00", discount="25.00"),
        line("5", "20.00"),
    ]
    withholding_customer = TaxParties(
        issuer_category=TaxpayerCategory.OTHER,
        customer_is_taxpayer=True,
        customer_category=TaxpayerCategory.LARGE,
    )
    result = calculate(CREDIT, lines, withholding_customer, GlobalDiscounts(taxed=D("77.50")))
    summary = result.summary
    assert [r.taxed for r in result.lines] == [D("100"), D("75"), D("500"), D("100")]
    assert summary.total_taxed == D("775.00")
    assert summary.discount_taxed == D("77.50")
    assert summary.total_discount == D("112.50")
    assert summary.subtotal == D("697.50")
    assert summary.vat == D("90.68")
    assert summary.vat_withheld == D("6.98")
    assert summary.vat_perceived == D("0")
    assert summary.total_operation == D("781.20")
    assert summary.total_in_words == "SETECIENTOS OCHENTA Y UNO 20/100 DÓLARES"


def test_exempt_and_not_subject_lines_carry_no_vat() -> None:
    result = calculate(
        INVOICE,
        [
            line("2", "3.00", treatment=TaxTreatment.EXEMPT),
            line("1", "4.50", treatment=TaxTreatment.NOT_SUBJECT),
            line("1", "2.26", with_vat=True),
        ],
        CONSUMER,
    )
    summary = result.summary
    assert summary.total_exempt == D("6.00")
    assert summary.total_not_subject == D("4.50")
    assert summary.total_taxed == D("2.26")
    assert summary.vat == D("0.26")
    assert summary.subtotal_sales == D("12.76")
    assert summary.total_to_pay == D("12.76")
    assert result.lines[0].vat_item == D("0")


def test_untaxed_price_cannot_include_vat() -> None:
    with pytest.raises(BusinessRuleError) as excinfo:
        calculate(INVOICE, [line("1", "1", with_vat=True, treatment=TaxTreatment.EXEMPT)], CONSUMER)
    assert code(excinfo) == "sales_tax_untaxed_price_with_vat"


def test_price_conversion_rounds_half_up_at_eight_decimals() -> None:
    # 1 / 1.13 = 0.884955752212... -> 0.88495575
    credit = calculate(CREDIT, [line("1", "1", with_vat=True)], TAXPAYER)
    assert credit.lines[0].unit_price == D("0.88495575")
    # novena posición 5: se sube la octava
    assert line_round(D("0.123456785")) == D("0.12345679")
    assert line_round(D("0.123456784")) == D("0.12345678")


def test_invoice_vat_on_net_of_global_discount() -> None:
    result = calculate(
        INVOICE, [line("10", "11.30", with_vat=True)], CONSUMER, GlobalDiscounts(taxed=D("11.30"))
    )
    assert result.summary.total_taxed == D("113.00")
    assert result.summary.subtotal == D("101.70")
    assert result.summary.vat == D("11.70")
    assert result.summary.total_to_pay == D("101.70")


def test_withholding_threshold_is_one_hundred_without_vat() -> None:
    agent = TaxParties(
        issuer_category=TaxpayerCategory.MEDIUM,
        customer_is_taxpayer=True,
        customer_category=TaxpayerCategory.MEDIUM,
        customer_is_withholding_agent=True,
    )
    at = calculate(CREDIT, [line("1", "100.00")], agent)
    assert at.summary.vat_withheld == D("1.00")
    assert at.summary.total_operation == D("112.00")
    below = calculate(CREDIT, [line("1", "99.99")], agent)
    assert below.summary.vat_withheld == D("0")
    large_issuer = TaxParties(
        issuer_category=TaxpayerCategory.LARGE,
        customer_is_taxpayer=True,
        customer_category=TaxpayerCategory.LARGE,
    )
    assert calculate(CREDIT, [line("1", "500")], large_issuer).summary.vat_withheld == D("0")


def test_perception_only_large_issuer_on_goods_in_credit() -> None:
    large = TaxParties(
        issuer_category=TaxpayerCategory.LARGE,
        customer_is_taxpayer=True,
        customer_category=TaxpayerCategory.OTHER,
    )
    result = calculate(
        CREDIT,
        [line("1", "150.00"), line("1", "80.00", item=DteItemType.SERVICES)],
        large,
    )
    assert result.summary.vat_perceived == D("1.50")
    assert result.summary.total_operation == D("261.40")
    services_only = calculate(CREDIT, [line("1", "500", item=DteItemType.SERVICES)], large)
    assert services_only.summary.vat_perceived == D("0")
    below = calculate(CREDIT, [line("1", "99.99")], large)
    assert below.summary.vat_perceived == D("0")
    to_large = TaxParties(
        issuer_category=TaxpayerCategory.LARGE,
        customer_is_taxpayer=True,
        customer_category=TaxpayerCategory.LARGE,
    )
    assert calculate(CREDIT, [line("1", "500")], to_large).summary.vat_perceived == D("0")


def test_perception_base_shares_the_global_discount() -> None:
    large = TaxParties(
        issuer_category=TaxpayerCategory.LARGE,
        customer_is_taxpayer=True,
        customer_category=TaxpayerCategory.MEDIUM,
    )
    result = calculate(
        CREDIT,
        [line("1", "150"), line("1", "50", item=DteItemType.SERVICES)],
        large,
        GlobalDiscounts(taxed=D("100")),
    )
    # bienes 150 de 200 gravadas: les toca 75 del descuento -> base 75, debajo del umbral
    assert result.summary.vat_perceived == D("0")


def test_validation_errors() -> None:
    cases = [
        ([], "sales_tax_lines_required"),
        ([line("0", "1")], "sales_tax_quantity_invalid"),
        ([line("1", "-1")], "sales_tax_price_invalid"),
        ([line("1", "1", discount="-1")], "sales_tax_discount_invalid"),
        ([line("1", "1", discount="2")], "sales_tax_discount_exceeds_line"),
        ([line("1", "1", extra=("D1",))], "sales_tax_additional_unsupported"),
    ]
    for lines, expected in cases:
        with pytest.raises(BusinessRuleError) as excinfo:
            calculate(INVOICE, lines, CONSUMER)
        assert code(excinfo) == expected
    with pytest.raises(BusinessRuleError) as excinfo:
        calculate(INVOICE, [line("1", "1")], CONSUMER, GlobalDiscounts(exempt=D("0.01")))
    assert code(excinfo) == "sales_tax_global_discount_exceeds"
    with pytest.raises(BusinessRuleError) as excinfo:
        calculate(CREDIT, [line("1", "1")], CONSUMER)
    assert code(excinfo) == "sales_tax_credit_requires_taxpayer"


@pytest.mark.parametrize(
    ("amount", "words"),
    [
        ("0", "CERO 00/100 DÓLARES"),
        ("1", "UNO 00/100 DÓLARES"),
        ("21", "VEINTIUNO 00/100 DÓLARES"),
        ("22", "VEINTIDÓS 00/100 DÓLARES"),
        ("100", "CIEN 00/100 DÓLARES"),
        ("101.05", "CIENTO UNO 05/100 DÓLARES"),
        ("1073.50", "MIL SETENTA Y TRES 50/100 DÓLARES"),
        ("21000", "VEINTIÚN MIL 00/100 DÓLARES"),
        ("31000", "TREINTA Y UN MIL 00/100 DÓLARES"),
        (
            "1234567.89",
            "UN MILLÓN DOSCIENTOS TREINTA Y CUATRO MIL QUINIENTOS SESENTA Y SIETE 89/100 DÓLARES",
        ),
        ("21000000", "VEINTIÚN MILLONES 00/100 DÓLARES"),
        ("5.665", "CINCO 67/100 DÓLARES"),
    ],
)
def test_amount_in_words(amount: str, words: str) -> None:
    assert amount_in_words(D(amount)) == words
