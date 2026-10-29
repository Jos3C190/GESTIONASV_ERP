from decimal import Decimal
from uuid import uuid4

import pytest
from app.api.v1.routers.inventory_putaway_groups import _validate_lot_detail_totals
from app.api.v1.schemas.inventory_putaway_group import PutawayGroupConfirmIn
from fastapi import HTTPException
from pydantic import ValidationError


def test_group_allows_one_handling_unit_split_across_destinations() -> None:
    handling_unit_id = uuid4()
    body = PutawayGroupConfirmIn(
        idempotency_key="putaway-group-0001",
        receipt_lot_id=uuid4(),
        inventory_lot_detail_id=uuid4(),
        inventory_item_id=uuid4(),
        allocations=[
            {
                "handling_unit_id": handling_unit_id,
                "quantity_base": "12",
                "destination_location_id": uuid4(),
            },
            {
                "handling_unit_id": handling_unit_id,
                "quantity_base": "8",
                "destination_location_id": uuid4(),
            },
        ],
    )

    assert len(body.allocations) == 2
    assert all(allocation.handling_unit_id == handling_unit_id for allocation in body.allocations)


def test_group_rejects_duplicate_unit_destination_pair() -> None:
    handling_unit_id = uuid4()
    destination_location_id = uuid4()
    base = {
        "idempotency_key": "putaway-group-0002",
        "receipt_lot_id": uuid4(),
        "inventory_lot_detail_id": uuid4(),
        "inventory_item_id": uuid4(),
        "allocations": [
            {
                "handling_unit_id": handling_unit_id,
                "quantity_base": "6",
                "destination_location_id": destination_location_id,
            },
            {
                "handling_unit_id": handling_unit_id,
                "quantity_base": "4",
                "destination_location_id": destination_location_id,
            },
        ],
    }

    with pytest.raises(ValidationError, match="solo puede aparecer una vez por destino"):
        PutawayGroupConfirmIn(**base)


@pytest.mark.parametrize("quantity", ["0", "-1", "0.0000001"])
def test_group_requires_positive_quantity_at_six_decimal_precision(quantity: str) -> None:
    with pytest.raises(ValidationError):
        PutawayGroupConfirmIn(
            idempotency_key="putaway-group-0003",
            receipt_lot_id=uuid4(),
            inventory_lot_detail_id=uuid4(),
            inventory_item_id=uuid4(),
            allocations=[
                {
                    "handling_unit_id": uuid4(),
                    "quantity_base": quantity,
                    "destination_location_id": uuid4(),
                }
            ],
        )


def test_grouped_putaway_aggregates_all_accepted_lines_for_same_product() -> None:
    first_line, second_line = uuid4(), uuid4()

    _validate_lot_detail_totals(
        {first_line: Decimal("20"), second_line: Decimal("30")},
        {first_line: Decimal("20"), second_line: Decimal("30")},
        Decimal("0"),
        require_line_origin=True,
    )


def test_grouped_putaway_rejects_quantity_above_accepted_lines() -> None:
    first_line, second_line = uuid4(), uuid4()

    with pytest.raises(HTTPException) as error:
        _validate_lot_detail_totals(
            {first_line: Decimal("20"), second_line: Decimal("30")},
            {first_line: Decimal("20"), second_line: Decimal("31")},
            Decimal("0"),
            require_line_origin=True,
        )

    assert error.value.status_code == 409


def test_new_receipt_rejects_units_without_purchase_line_origin() -> None:
    with pytest.raises(HTTPException) as error:
        _validate_lot_detail_totals(
            {uuid4(): Decimal("50")},
            {},
            Decimal("1"),
            require_line_origin=True,
        )
    assert "sin vínculo a su línea" in error.value.detail


def test_historical_receipt_can_keep_units_without_line_origin() -> None:
    _validate_lot_detail_totals(
        {uuid4(): Decimal("50")},
        {},
        Decimal("50"),
        require_line_origin=False,
    )
