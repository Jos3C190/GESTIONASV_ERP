"""Pedido V2e: estados, entrega, condición de pago y reserva comercial."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.core.exceptions import BusinessRuleError
from app.domain.entities.sales_order import (
    DeliveryMode,
    OrderStatus,
    PaymentTerms,
    available_to_sell,
    confirm_target,
    payment_condition,
    pending_to_deliver,
    require_cancellable,
    require_delivery_place,
    require_editable,
    require_pending_authorization,
    require_promised_date,
    shortages,
)

D = Decimal
S = OrderStatus
TODAY = date(2026, 11, 16)


def test_transitions() -> None:
    require_editable(S.DRAFT)
    for status in (S.PENDING_AUTHORIZATION, S.CONFIRMED, S.CANCELLED):
        with pytest.raises(BusinessRuleError):
            require_editable(status)
    assert confirm_target(S.DRAFT, requires_authorization=False) is S.CONFIRMED
    assert confirm_target(S.DRAFT, requires_authorization=True) is S.PENDING_AUTHORIZATION
    with pytest.raises(BusinessRuleError):
        confirm_target(S.CONFIRMED, requires_authorization=False)
    require_pending_authorization(S.PENDING_AUTHORIZATION)
    with pytest.raises(BusinessRuleError):
        require_pending_authorization(S.DRAFT)


def test_cancellation_needs_open_order_without_deliveries() -> None:
    for status in (S.DRAFT, S.PENDING_AUTHORIZATION, S.CONFIRMED):
        require_cancellable(status, delivered_any=False)
    with pytest.raises(BusinessRuleError) as error:
        require_cancellable(S.CONFIRMED, delivered_any=True)
    assert error.value.code == "sales_order_has_deliveries"
    with pytest.raises(BusinessRuleError):
        require_cancellable(S.CANCELLED, delivered_any=False)


def test_delivery_place_and_date() -> None:
    require_promised_date(TODAY, TODAY)
    with pytest.raises(BusinessRuleError):
        require_promised_date(date(2026, 11, 15), TODAY)
    require_delivery_place(DeliveryMode.PICKUP, has_address=False)
    require_delivery_place(DeliveryMode.DELIVERY, has_address=True)
    with pytest.raises(BusinessRuleError) as error:
        require_delivery_place(DeliveryMode.DELIVERY, has_address=False)
    assert error.value.code == "sales_order_address_required"
    with pytest.raises(BusinessRuleError):
        require_delivery_place(DeliveryMode.PICKUP, has_address=True)


def test_payment_condition_follows_customer() -> None:
    assert payment_condition(0).terms is PaymentTerms.CASH
    credit = payment_condition(30)
    assert credit.terms is PaymentTerms.CREDIT
    assert credit.credit_days == 30
    assert payment_condition(500).credit_days == 365


def test_commercial_reservation() -> None:
    flour, sugar = uuid.uuid4(), uuid.uuid4()
    assert available_to_sell(D("10"), D("4")) == D("6")
    assert available_to_sell(D("3"), D("5")) == D("0")
    assert pending_to_deliver(D("8"), D("3")) == D("5")
    assert pending_to_deliver(D("8"), D("9")) == D("0")
    missing = shortages({flour: D("5"), sugar: D("2")}, {flour: D("6")})
    assert [(m.inventory_item_id, m.required, m.available) for m in missing] == [
        (sugar, D("2"), D("0"))
    ]
    assert shortages({flour: D("6")}, {flour: D("6")}) == []
