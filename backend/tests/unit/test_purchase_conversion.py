"""Foreign-currency receipts retain source prices and convert valuation once."""

import inspect
import uuid
from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from app.api.v1.routers.purchases import _purchase_audit_state, router
from app.api.v1.schemas.purchase import PurchaseResponse, PurchaseValuationConversionInput
from app.application.purchases import PurchaseUseCases
from app.domain.entities.inventory import InventoryItem, InventoryOperationError
from app.domain.entities.purchase import PurchaseStatus, PurchaseVerificationLine
from app.domain.entities.purchase_conversion import PurchaseValuationConversion
from app.infrastructure.repositories.inventory_valuation_repository import (
    SqlAlchemyInventoryValuationRepository,
)
from app.infrastructure.repositories.purchase_inventory_gateway import (
    SqlAlchemyPurchaseInventoryGateway,
)
from pydantic import ValidationError

from tests.unit.test_purchase_inventory_safety import (
    _FakeInventoryRepository,
    _FakeReceiptSession,
    _purchase,
)
from tests.unit.test_purchase_use_cases import (
    FakeOrderRepository,
    FakePurchaseInventoryGateway,
    FakePurchaseRepository,
    _ids,
    _order,
)
from tests.unit.test_purchase_use_cases import (
    _purchase as application_purchase,
)

pytestmark = pytest.mark.unit


def conversion(rate="500", currency="USD"):
    return PurchaseValuationConversion(
        currency, Decimal(rate), date(2026, 10, 21), "Prueba ficticia de conversión"
    )


@pytest.mark.parametrize("rate", ["0", "-1", "NaN", "Infinity", "0.0000000000001", "1000000000000"])
def test_conversion_rejects_invalid_rates(rate):
    with pytest.raises(ValueError, match="tipo de cambio"):
        conversion(rate)


def test_conversion_is_documented_round_trip_and_divides_in_the_displayed_direction():
    value = conversion()
    assert value.convert(Decimal("22000")) == Decimal("44.000000")
    assert PurchaseValuationConversion.from_dict(value.to_dict()) == value
    assert conversion("3").convert(Decimal("1")) == Decimal("0.333333")


def test_unrepresentable_target_amount_is_rejected():
    with pytest.raises(ValueError, match="máximo"):
        conversion("0.000000000001").convert(Decimal("1000000000000"))


@pytest.mark.parametrize(
    "changes",
    [{"reference": ""}, {"currency": "EURX"}, {"rate": "-1"}, {"effective_date": "no-date"}],
)
def test_http_conversion_requires_a_valid_currency_date_rate_and_reference(changes):
    value = conversion().to_dict() | changes
    with pytest.raises(ValidationError):
        PurchaseValuationConversionInput.model_validate(value)


def test_conversion_context_uses_receipt_verification_and_inventory_permissions():
    route = next(route for route in router.routes if route.path.endswith("/valuation-context"))
    codes = {
        inspect.getclosurevars(dependency.dependency).nonlocals.get("required_code")
        for dependency in route.dependencies
    }
    assert "purchases:verify" in codes
    assert "inventory:receive" in codes


@pytest.mark.asyncio
async def test_foreign_receipt_is_blocked_without_a_rate_before_any_inventory_write():
    purchase = replace(_purchase(), currency="CRC")
    session = _FakeReceiptSession(uuid.uuid4(), valuation_currency="USD")
    gateway = SqlAlchemyPurchaseInventoryGateway(session)
    gateway._inventory = _FakeInventoryRepository(None)
    with pytest.raises(InventoryOperationError) as failure:
        await gateway.post_verified_receipt(
            purchase=purchase,
            actor_id=uuid.uuid4(),
            lines=(PurchaseVerificationLine(purchase.details[0].id, Decimal("1"), uuid.uuid4()),),
        )
    assert failure.value.code == "purchase_valuation_conversion_required"
    assert "CRC" in str(failure.value)
    assert "USD" in str(failure.value)
    assert session.added == []
    assert gateway._inventory.movements == []


@pytest.mark.asyncio
async def test_foreign_receipt_splits_conserve_converted_cost_and_original_document():
    original = _purchase()
    detail = replace(original.details[0], subtotal=Decimal("1000"), unit_price=Decimal("1000"))
    purchase = replace(
        original, currency="CRC", details=(detail,), valuation_conversion=conversion()
    )
    session = _FakeReceiptSession(uuid.uuid4(), valuation_currency="USD")
    item = InventoryItem(
        uuid.uuid4(), purchase.company_id, detail.product_id, None, detail.unit_id, True
    )
    inventory = _FakeInventoryRepository(item)
    gateway = SqlAlchemyPurchaseInventoryGateway(session)
    gateway._inventory = inventory
    location = uuid.uuid4()
    await gateway.post_verified_receipt(
        purchase=purchase,
        actor_id=uuid.uuid4(),
        lines=(
            PurchaseVerificationLine(detail.id, Decimal("0.333333"), location),
            PurchaseVerificationLine(detail.id, Decimal("0.666667"), location),
        ),
    )
    lines = inventory.movements[0]["lines"]
    assert sum(line["valuation_value"] for line in lines) == Decimal("2.000000")
    assert all(line["valuation_currency"] == "USD" for line in lines)
    assert purchase.currency == "CRC"
    assert purchase.details[0].subtotal == Decimal("1000")


@pytest.mark.asyncio
async def test_conversion_cannot_target_a_different_valuation_currency():
    purchase = replace(_purchase(), currency="CRC", valuation_conversion=conversion(currency="EUR"))
    gateway = SqlAlchemyPurchaseInventoryGateway(
        _FakeReceiptSession(uuid.uuid4(), valuation_currency="USD")
    )
    with pytest.raises(InventoryOperationError) as failure:
        await gateway._receipt_valuation_currency(purchase)
    assert failure.value.code == "purchase_valuation_currency_changed"


@pytest.mark.asyncio
async def test_application_saves_conversion_and_preserves_currency_and_prices():
    ids = _ids()
    purchase = replace(
        application_purchase(ids, received=Decimal("2"), status=PurchaseStatus.RECEIVED),
        currency="CRC",
    )
    repository = FakePurchaseRepository()
    repository.items[purchase.id] = purchase
    gateway = FakePurchaseInventoryGateway(uuid.uuid4())
    use_cases = PurchaseUseCases(repository, FakeOrderRepository(_order(ids)), gateway)
    saved = await use_cases.verify_purchase(
        ids["company"],
        purchase.id,
        actor_id=ids["user"],
        valuation_conversion=conversion(),
        lines=(PurchaseVerificationLine(purchase.details[0].id, Decimal("1"), uuid.uuid4()),),
    )
    assert saved.valuation_conversion == conversion()
    assert gateway.calls[0]["purchase"].valuation_conversion == conversion()
    assert saved.currency == "CRC"
    assert saved.details[0].unit_price == purchase.details[0].unit_price
    assert PurchaseResponse.model_validate(saved).valuation_conversion.rate == Decimal("500")
    assert _purchase_audit_state(saved)["valuation_conversion"] == conversion().to_dict()


class RetaceoSession:
    def __init__(self, company_id, purchase_id):
        self.purchase = SimpleNamespace(
            company_id=company_id,
            id=purchase_id,
            currency="CRC",
            valuation_conversion=conversion().to_dict(),
        )
        self.receipt = SimpleNamespace(
            id=uuid.uuid4(),
            quantity_base=Decimal("1"),
            source_value=Decimal("2"),
            inventory_item_id=uuid.uuid4(),
        )
        self.added = []
        self.statements = []

    async def scalar(self, statement):
        self.statements.append(statement)
        return self.purchase if "from purchases" in str(statement).lower() else None

    async def scalars(self, statement):
        return SimpleNamespace(all=lambda: [self.receipt])

    async def get(self, model, key):
        return SimpleNamespace(company_id=self.purchase.company_id)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        pass


class RetaceoValuation(SqlAlchemyInventoryValuationRepository):
    async def lock(self, company_id):
        pass

    async def settings(self, company_id):
        return SimpleNamespace(currency="USD")

    async def append(self, **values):
        return SimpleNamespace(
            id=uuid.uuid4(), source_value=values["value"], inventory_delta=values["value"]
        )


@pytest.mark.asyncio
async def test_retaceo_reuses_the_saved_rate_and_posts_only_converted_extra_cost():
    retaceo = SimpleNamespace(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        purchase_id=uuid.uuid4(),
        currency="CRC",
        code="RET-FX",
        details=[
            SimpleNamespace(
                purchase_detail_id=uuid.uuid4(),
                cost_fob=Decimal("1000"),
                total_cost=Decimal("1200"),
            )
        ],
    )
    session = RetaceoSession(retaceo.company_id, retaceo.purchase_id)
    await RetaceoValuation(session).apply_retaceo(retaceo, uuid.uuid4())
    summary = session.added[0].summary
    assert summary["currency"] == "USD"
    assert summary["source_currency"] == "CRC"
    assert summary["conversion"] == conversion().to_dict()
    assert Decimal(summary["lines"][0]["total_adjustment"]) == Decimal("0.400000")
    query = next(query for query in session.statements if "from purchases" in str(query).lower())
    assert retaceo.company_id in query.compile().params.values()


@pytest.mark.asyncio
async def test_foreign_retaceo_requires_the_original_receipts_documented_conversion():
    retaceo = SimpleNamespace(company_id=uuid.uuid4(), purchase_id=uuid.uuid4(), currency="CRC")
    session = RetaceoSession(retaceo.company_id, retaceo.purchase_id)
    session.purchase.valuation_conversion = None
    with pytest.raises(InventoryOperationError) as failure:
        await RetaceoValuation(session)._retaceo_conversion(retaceo, "USD")
    assert failure.value.code == "purchase_valuation_conversion_required"
    assert session.added == []
