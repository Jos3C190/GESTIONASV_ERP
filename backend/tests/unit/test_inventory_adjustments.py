"""Pure validation checks for authorized inventory adjustment contracts."""

from decimal import Decimal
from uuid import uuid4

import pytest
from app.api.v1.schemas.inventory_adjustment import (
    InventoryAdjustmentCreateIn,
    InventoryAdjustmentLineIn,
)
from app.application.inventory_adjustments.use_cases import InventoryAdjustmentUseCases
from app.domain.entities.inventory_adjustment import InventoryAdjustmentError
from pydantic import ValidationError

pytestmark = pytest.mark.unit


def _increase(**overrides):
    values = {
        "inventory_item_id": uuid4(),
        "location_id": uuid4(),
        "direction": "increase",
        "quantity_base": "2.250000",
        "stock_status": "quarantine",
        "actual_gross_weight_kg": "1.5",
        "actual_volume_m3": "0.25",
    }
    values.update(overrides)
    return values


def test_adjustment_lines_keep_positive_quantity_and_six_decimal_precision():
    lines = InventoryAdjustmentUseCases._validate_lines([_increase()])

    assert lines[0]["quantity_base"] == Decimal("2.250000")
    assert lines[0]["line_number"] == 1

    with pytest.raises(InventoryAdjustmentError, match="positiva"):
        InventoryAdjustmentUseCases._validate_lines([_increase(quantity_base="0")])
    with pytest.raises(InventoryAdjustmentError, match="seis decimales"):
        InventoryAdjustmentUseCases._validate_lines([_increase(quantity_base="0.0000001")])


def test_adjustment_cost_is_unit_or_total_and_explicit_zero_is_valid():
    unit_cost = InventoryAdjustmentLineIn.model_validate(_increase(documented_unit_cost="0"))
    total_cost = InventoryAdjustmentLineIn.model_validate(_increase(documented_total_cost="12.50"))

    assert unit_cost.documented_unit_cost == Decimal("0")
    assert total_cost.documented_total_cost == Decimal("12.50")
    with pytest.raises(ValidationError):
        InventoryAdjustmentLineIn.model_validate(
            _increase(documented_unit_cost="3", documented_total_cost="6")
        )


def test_decrease_requires_a_real_handling_unit_and_cannot_use_a_free_transit_status():
    with pytest.raises(ValidationError):
        InventoryAdjustmentLineIn.model_validate({
            "inventory_item_id": uuid4(),
            "location_id": uuid4(),
            "direction": "decrease",
            "quantity_base": "1",
            "stock_status": "available",
        })

    with pytest.raises(ValidationError):
        InventoryAdjustmentLineIn.model_validate({
            "inventory_item_id": uuid4(),
            "location_id": uuid4(),
            "direction": "decrease",
            "quantity_base": "1",
            "stock_status": "in_transit",
            "handling_unit_id": uuid4(),
        })


def test_transfer_loss_contract_requires_linked_incident_and_detail():
    line = {
        "inventory_item_id": uuid4(),
        "location_id": uuid4(),
        "direction": "decrease",
        "quantity_base": "1",
        "stock_status": "in_transit",
        "handling_unit_id": uuid4(),
        "transfer_detail_id": uuid4(),
    }
    body = InventoryAdjustmentCreateIn.model_validate({
        "idempotency_key": "adjustment-create-001",
        "warehouse_id": uuid4(),
        "operational_date": "2026-10-19",
        "accounting_date": "2026-10-19",
        "reason": "Pérdida verificada en tránsito",
        "document_reference": "ACTA-001",
        "transfer_id": uuid4(),
        "transfer_incident_id": uuid4(),
        "lines": [line],
    })
    assert body.lines[0].transfer_detail_id == line["transfer_detail_id"]

    with pytest.raises(ValidationError):
        InventoryAdjustmentCreateIn.model_validate({
            "idempotency_key": "adjustment-create-002",
            "warehouse_id": uuid4(),
            "operational_date": "2026-10-19",
            "accounting_date": "2026-10-19",
            "reason": "Pérdida verificada en tránsito",
            "document_reference": "ACTA-002",
            "transfer_id": uuid4(),
            "transfer_incident_id": uuid4(),
            "lines": [{**line, "transfer_detail_id": None}],
        })
