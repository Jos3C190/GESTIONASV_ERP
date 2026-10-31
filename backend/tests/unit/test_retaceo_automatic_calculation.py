from dataclasses import replace
from decimal import Decimal

import pytest
from app.application.retaceos import RetaceoUseCases
from app.domain.entities.retaceo_calculation import calculate_import_taxes

from tests.unit.test_retaceo_use_cases import (
    FakePurchaseRepository,
    FakeRetaceoRepository,
    _ids,
    _purchase,
)


def test_taxes_use_customs_basis_then_add_dai_for_vat():
    assert calculate_import_taxes(
        Decimal("1000"), Decimal("100"), Decimal("10"), Decimal("13")
    ) == (Decimal("110.000000"), Decimal("157.300000"))


@pytest.mark.parametrize(
    "rate", [None, Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), Decimal("1001")]
)
def test_invalid_rates_are_rejected(rate):
    with pytest.raises(ValueError, match="porcentaje"):
        calculate_import_taxes(Decimal("1000"), Decimal("0"), rate, Decimal("13"))


def test_calculated_amounts_cannot_overflow_persisted_money_precision():
    with pytest.raises(ValueError, match="máximo"):
        calculate_import_taxes(
            Decimal("999999999999.999999"), Decimal("0"), Decimal("1000"), Decimal("13")
        )


async def test_automatic_creation_uses_net_receipt_and_ignores_submitted_tax_amounts():
    ids = _ids()
    purchase = _purchase(ids)
    repository = FakeRetaceoRepository()
    use_cases = RetaceoUseCases(repository, FakePurchaseRepository(purchase))
    item = await use_cases.create_draft(
        company_id=ids["company"],
        created_by_id=ids["user"],
        purchase_id=purchase.id,
        total_freight=Decimal("100"),
        total_expenses=Decimal("0"),
        total_dai=Decimal("1"),
        import_vat=Decimal("2"),
        calculation_mode="automatic",
        dai_rate=Decimal("10"),
        vat_rate=Decimal("13"),
    )
    assert item.total_fob == Decimal("55780")
    assert item.total_dai == Decimal("5588")
    assert item.import_vat == Decimal("7990.84")
    assert item.total_cost == Decimal("61468")
    assert sum(line.total_cost for line in item.details) == item.total_cost
    assert item.calculation_mode == "automatic"
    assert item.dai_rate == Decimal("10")
    assert item.vat_rate == Decimal("13")
    assert await use_cases.get_retaceo(ids["company"], item.id) == item
    updated = await use_cases.update_draft(
        company_id=ids["company"],
        retaceo_id=item.id,
        total_freight=Decimal("200"),
        total_expenses=Decimal("0"),
        total_dai=Decimal("0"),
        import_vat=Decimal("0"),
    )
    assert updated.total_dai == Decimal("5598")
    assert updated.import_vat == Decimal("8005.14")
    assert updated.dai_rate == item.dai_rate


async def test_automatic_fob_prorates_accepted_quantity_and_excludes_rejected_lines():
    ids = _ids()
    purchase = _purchase(ids)
    purchase = replace(
        purchase,
        details=(
            replace(
                purchase.details[0],
                quantity_accepted=Decimal("25"),
                inventory_location_id=ids["warehouse"],
            ),
            replace(purchase.details[1], quantity_accepted=Decimal("0")),
        ),
    )
    use_cases = RetaceoUseCases(FakeRetaceoRepository(), FakePurchaseRepository(purchase))
    item = await use_cases.create_draft(
        company_id=ids["company"],
        created_by_id=ids["user"],
        purchase_id=purchase.id,
        total_freight=Decimal("100"),
        total_expenses=Decimal("0"),
        total_dai=Decimal("0"),
        import_vat=Decimal("0"),
        calculation_mode="automatic",
        dai_rate=Decimal("10"),
        vat_rate=Decimal("13"),
    )
    assert len(item.details) == 1
    assert item.total_fob == Decimal("7250")
    assert item.total_dai == Decimal("735")
    assert item.import_vat == Decimal("1051.05")
    assert item.details[0].unit_cost == Decimal("323.4")
